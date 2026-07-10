import { Component, type ReactNode } from 'react';
import { View, Text, ScrollView } from '@/lib/tw';
import Splash from '@/components/Splash';
import { Button } from '@/components/Button';
import { isApiError } from '@/lib/api/errors';
import { API_BASE } from '@/lib/api/http';

interface Props {
  children: ReactNode;
  onRetry?: () => void;
}

interface State {
  error: Error | null;
}

export default class ScreenErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  handleRetry = () => {
    this.props.onRetry?.();
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    // A 401 means the session just died; the HTTP layer has invalidated the
    // session query and the gate is about to redirect to login. Show the neutral
    // loading skeleton during that handoff rather than a scary error screen.
    if (isApiError(error) && error.isUnauthorized) return <Splash variant="spinner" />;

    // An unreachable backend is recoverable — offer a clearly "offline" state and
    // a retry, not a generic "something broke" screen.
    const offline = isApiError(error) && error.isNetworkError;
    const title = offline ? "Can't reach the server" : 'Something went wrong.';
    const body = offline ? 'Check your connection and try again.' : undefined;

    return (
      <View className="flex-1 items-center justify-center gap-3 px-6 bg-background">
        <Text className="text-foreground text-18 font-sans text-center">{title}</Text>
        {body && (
          <Text className="text-foreground-muted text-15 font-sans text-center">{body}</Text>
        )}
        <View className="mt-2">
          <Button onPress={this.handleRetry}>Try again</Button>
        </View>
        <DebugPanel error={error} />
      </View>
    );
  }
}

// TEMPORARY — verbose on-device diagnostics for the "can't reach server" TestFlight
// investigation. Shows exactly what the client tried to hit and why it failed,
// since TestFlight builds have no attached console. Remove once resolved.
function DebugPanel({ error }: { error: Error }) {
  const rows: Array<[string, string]> = [
    ['API_BASE (resolved)', API_BASE],
    ['process.env.APP_PUBLIC_API_URL', String(process.env.APP_PUBLIC_API_URL)],
    ['error.name', error.name],
    ['error.message', error.message],
  ];
  if (isApiError(error)) {
    rows.push(['error.kind', error.kind]);
    rows.push(['error.status', String(error.status)]);
    rows.push(['error.userMessage', String(error.userMessage)]);
  }
  if (error.stack) rows.push(['error.stack', error.stack]);

  return (
    <ScrollView
      className="mt-4 max-h-64 w-full self-stretch mx-4 rounded-14 border border-border bg-surface-muted"
      contentContainerClassName="p-3 gap-2"
    >
      <Text className="text-foreground-subtle text-11 font-sans">DEBUG (remove me)</Text>
      {rows.map(([label, value]) => (
        <View key={label} className="gap-0.5">
          <Text className="text-foreground-subtle text-11 font-sans">{label}</Text>
          <Text selectable className="text-foreground text-13 font-sans">
            {value}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}
