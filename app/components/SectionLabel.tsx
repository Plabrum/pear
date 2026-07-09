import type { TextStyle } from 'react-native';

import { Text, View } from '@/lib/tw';

// Uppercase section heading used to group list/form rows. Pass `style` to
// override per-screen padding (some screens inset to 16, others 24).
// Empty children render a small spacer.
export function SectionLabel({ children, style }: { children: string; style?: TextStyle }) {
  if (!children) return <View style={{ height: 8 }} />;
  return (
    <Text
      className="text-ink-dim"
      style={[
        {
          fontSize: 11,
          letterSpacing: 1.4,
          textTransform: 'uppercase',
          fontWeight: '600',
          paddingHorizontal: 16,
          paddingTop: 16,
          paddingBottom: 8,
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}
