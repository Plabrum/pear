import type { ReactNode } from 'react';
import { ActivityIndicator } from 'react-native';
import { Pressable, Text, View } from '@/lib/tw';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'accent' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

type Props = {
  children: ReactNode;
  onPress?: () => void;
  variant?: Variant;
  size?: Size;
  block?: boolean;
  icon?: ReactNode;
  disabled?: boolean;
  loading?: boolean;
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: 'h-9 px-3.5 rounded-[18px]',
  md: 'h-12 px-5 rounded-[24px]',
  lg: 'h-14 px-6 rounded-[28px]',
};

const TEXT_SIZE_CLASSES: Record<Size, string> = {
  sm: 'text-[13px]',
  md: 'text-[15px]',
  lg: 'text-[17px]',
};

const VARIANT_BG: Record<Variant, string> = {
  primary: 'bg-primary border border-primary active:bg-accent-press',
  secondary: 'bg-surface border border-border active:bg-surface-muted',
  accent: 'bg-accent border border-transparent active:opacity-90',
  ghost: 'bg-transparent border border-transparent active:bg-surface-muted',
  danger: 'bg-transparent border border-border active:bg-surface-muted',
};

const VARIANT_FG: Record<Variant, string> = {
  primary: 'text-primary-foreground',
  secondary: 'text-foreground',
  accent: 'text-accent-foreground',
  ghost: 'text-foreground',
  danger: 'text-destructive',
};

const SPINNER_COLOR: Record<Variant, string> = {
  primary: '#FBF8F1',
  secondary: '#1F1B16',
  accent: '#1F1B16',
  ghost: '#1F1B16',
  danger: '#C77878',
};

export function Sprout({
  children,
  onPress,
  variant = 'primary',
  size = 'md',
  block = false,
  icon,
  disabled = false,
  loading = false,
}: Props) {
  const isInteractive = !disabled && !loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={!isInteractive}
      className={cn(
        'flex-row items-center justify-center',
        SIZE_CLASSES[size],
        VARIANT_BG[variant],
        block && 'w-full',
        (disabled || loading) && 'opacity-50'
      )}
    >
      {loading ? (
        <ActivityIndicator size="small" color={SPINNER_COLOR[variant]} />
      ) : (
        <>
          {icon ? <View className="mr-2">{icon}</View> : null}
          <Text className={cn('font-semibold', TEXT_SIZE_CLASSES[size], VARIANT_FG[variant])}>
            {children}
          </Text>
        </>
      )}
    </Pressable>
  );
}
