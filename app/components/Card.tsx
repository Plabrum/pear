import type { ReactNode } from 'react';
import type { StyleProp, ViewStyle } from 'react-native';

import { cn } from '@/lib/cn';
import { View } from '@/lib/tw';

// Surface container used throughout discover / matches / profile. A rounded
// paper panel with a subtle border. Override or extend via `className`/`style`.
export function Card({
  children,
  className,
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View className={cn('bg-surface rounded-2xl border border-border', className)} style={style}>
      {children}
    </View>
  );
}
