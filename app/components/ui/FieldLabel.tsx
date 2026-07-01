import type { TextStyle } from 'react-native';

import { Text } from '@/lib/tw';

// Small uppercase label above a form field. Canonical version of the copy that
// previously lived in PhotosTab / PromptsTab / AboutMeTab. Pass `style` to tweak
// per-callsite spacing (e.g. marginBottom) without redefining the primitive.
export function FieldLabel({ children, style }: { children: string; style?: TextStyle }) {
  return (
    <Text
      className="text-ink-dim"
      style={[
        {
          fontSize: 10.5,
          letterSpacing: 1.4,
          textTransform: 'uppercase',
          fontWeight: '600',
          marginBottom: 8,
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}
