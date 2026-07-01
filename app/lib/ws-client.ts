// Single shared WebSocket transport for realtime. Connects to the backend `/ws`
// endpoint, authenticating via the session cookie sent on the handshake (the RN
// WebSocket carries it automatically; SessionAuth runs on the upgrade). One
// process-wide connection is multiplexed across every subscriber (per-pair
// presence, the messages-list presence set, typing, and the new-message stream).
// The hooks in `hooks/*` and `lib/messages-realtime.ts` consume this manager.

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

// ws(s)://<api-host>/ws — derive from the http(s) API URL. Auth is the session
// cookie on the handshake, so no query param / header is appended.
function wsUrl(): string {
  const base = API_URL.replace(/^http/, 'ws').replace(/\/+$/, '');
  return `${base}/ws`;
}

// Server -> client frame shapes.
type ReadyFrame = { type: 'ready' };
type SubscribedFrame = { type: 'subscribed'; channel: string };
type UnsubscribedFrame = { type: 'unsubscribed'; channel: string };
type ErrorFrame = { type: 'error'; message: string; channel?: string };
type PongFrame = { type: 'pong' };
type MessageFrame = { type: 'message'; channel: string; payload: unknown };
type PresencePairFrame = { type: 'presence'; channel: string; online: boolean };
type PresenceListFrame = { type: 'presence'; channel: string; onlineIds: string[] };
type TypingFrame = {
  type: 'typing';
  channel: string;
  payload: { userId: string; ts: number };
};

type ServerFrame =
  | ReadyFrame
  | SubscribedFrame
  | UnsubscribedFrame
  | ErrorFrame
  | PongFrame
  | MessageFrame
  | PresencePairFrame
  | PresenceListFrame
  | TypingFrame;

// What a per-channel subscriber receives. `subscribed`/`error` are lifecycle
// acks; everything else is a data frame for that channel.
export type ChannelEvent = Exclude<ServerFrame, ReadyFrame | PongFrame>;

type ChannelListener = (event: ChannelEvent) => void;

const WS_CLOSE_UNAUTHENTICATED = 4401;
const PING_INTERVAL_MS = 25_000;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 15_000;

type ConnState = 'idle' | 'connecting' | 'open' | 'closed';

class WsManager {
  private socket: WebSocket | null = null;
  private state: ConnState = 'idle';
  private ready = false;

  // channel -> set of listeners. The channel is "joined" on the server while at
  // least one listener exists; the last leaver triggers an unsubscribe frame.
  private listeners = new Map<string, Set<ChannelListener>>();

  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;

  // --- Public API consumed by the hooks ---------------------------------

  // Join a channel and receive its events. Returns an unsubscribe function.
  // Connecting lazily on first subscriber keeps the socket cost off the login
  // path and tears it down when nothing is listening.
  subscribe(channel: string, listener: ChannelListener): () => void {
    let set = this.listeners.get(channel);
    const isFirst = !set || set.size === 0;
    if (!set) {
      set = new Set();
      this.listeners.set(channel, set);
    }
    set.add(listener);

    this.ensureConnected();

    // Only the first listener for a channel sends the join frame; the server
    // ack is idempotent so a duplicate would be harmless regardless.
    if (isFirst && this.ready) {
      this.send({ type: 'subscribe', channel });
    }

    return () => this.removeListener(channel, listener);
  }

  // Fire a transient typing event. The server stamps userId + ts and fans out
  // to the sorted pair. No-op until the socket is ready.
  sendTyping(channel: string): void {
    if (this.ready) this.send({ type: 'typing', channel });
  }

  // --- Internal ----------------------------------------------------------

  private removeListener(channel: string, listener: ChannelListener): void {
    const set = this.listeners.get(channel);
    if (!set) return;
    set.delete(listener);
    if (set.size === 0) {
      this.listeners.delete(channel);
      if (this.ready) this.send({ type: 'unsubscribe', channel });
    }
    if (this.listeners.size === 0) this.teardown();
  }

  private ensureConnected(): void {
    if (this.state === 'connecting' || this.state === 'open') return;
    this.connect();
  }

  private connect(): void {
    if (this.state === 'connecting' || this.state === 'open') return;

    this.state = 'connecting';
    this.ready = false;

    // The session cookie authenticates the handshake; SessionAuth runs on the
    // upgrade and rejects unauthenticated connections (close 4401).
    const socket = new WebSocket(wsUrl());
    this.socket = socket;

    socket.onopen = () => {
      this.state = 'open';
      // Wait for the server `ready` frame before sending subscribe frames.
    };

    socket.onmessage = (ev) => this.onMessage(ev);

    socket.onclose = (ev) => this.onClose(ev.code);

    socket.onerror = () => {
      // RN surfaces errors then a close; the close handler drives reconnect.
    };
  }

  private onMessage(ev: WebSocketMessageEvent): void {
    let frame: ServerFrame;
    try {
      frame = JSON.parse(String(ev.data)) as ServerFrame;
    } catch {
      return;
    }

    switch (frame.type) {
      case 'ready':
        this.ready = true;
        this.reconnectAttempts = 0;
        this.startPing();
        // (Re)join every channel that currently has listeners.
        for (const channel of this.listeners.keys()) {
          this.send({ type: 'subscribe', channel });
        }
        return;
      case 'pong':
        return;
      case 'subscribed':
      case 'unsubscribed':
      case 'error':
      case 'message':
      case 'presence':
      case 'typing':
        this.dispatch(frame);
        return;
      default:
        return;
    }
  }

  private dispatch(frame: ChannelEvent): void {
    // `error` frames may be channel-less (e.g. "Unknown channel"); fan those
    // out to every listener so the channel-specific subscriber can react.
    if (frame.type === 'error' && !frame.channel) {
      for (const set of this.listeners.values()) {
        for (const l of set) l(frame);
      }
      return;
    }
    const channel = frame.channel;
    if (!channel) return;
    const set = this.listeners.get(channel);
    if (!set) return;
    for (const l of set) l(frame);
  }

  private onClose(code: number): void {
    this.stopPing();
    this.ready = false;
    this.socket = null;
    this.state = 'closed';

    if (this.listeners.size === 0) {
      this.state = 'idle';
      return;
    }

    if (code === WS_CLOSE_UNAUTHENTICATED) {
      // The session cookie is missing/expired → effectively logged out. There's
      // no token to refresh; stay idle so we don't hammer the upgrade. A future
      // subscribe (after a fresh login restores the cookie) reconnects.
      this.state = 'idle';
      return;
    }

    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    const delay = Math.min(
      RECONNECT_BASE_MS * 2 ** this.reconnectAttempts,
      RECONNECT_MAX_MS,
    );
    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.listeners.size > 0) this.connect();
      else this.state = 'idle';
    }, delay);
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      if (this.ready) this.send({ type: 'ping' });
    }, PING_INTERVAL_MS);
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private teardown(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopPing();
    this.ready = false;
    this.reconnectAttempts = 0;
    const socket = this.socket;
    this.socket = null;
    this.state = 'idle';
    if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  }

  private send(frame: Record<string, unknown>): void {
    const socket = this.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify(frame));
  }
}

// Process-wide singleton. All hooks share this one connection.
export const wsClient = new WsManager();
