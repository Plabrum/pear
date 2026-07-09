// Unified time + name helpers — single source of truth for relative-time
// formatting so the whole app reads consistently.

/** Parse an ISO string that may use a space separator (Postgres-style). */
function parseIso(isoString: string): number {
  return new Date(isoString.replace(' ', 'T')).getTime();
}

/**
 * Compact relative time: "now", "5m", "3h", "2d", then a short date.
 * Used by the messages list and the winger activity feed.
 */
export function relativeTime(isoString: string): string {
  const then = parseIso(isoString);
  if (Number.isNaN(then)) return '';
  const mins = Math.floor((Date.now() - then) / 60_000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(then).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Time-of-day label for a chat message, e.g. "9:41 AM". */
export function formatTimestamp(isoString: string): string {
  return new Date(parseIso(isoString)).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  });
}

/** Human "matched N ago" label for a match record. */
export function matchedAgo(createdAt: string): string {
  const days = Math.max(0, Math.floor((Date.now() - parseIso(createdAt)) / 86_400_000));
  if (days === 0) return 'matched today';
  if (days === 1) return 'matched 1 day ago';
  if (days < 30) return `matched ${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? 'matched 1 month ago' : `matched ${months} months ago`;
}
