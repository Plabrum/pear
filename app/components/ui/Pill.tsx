import type { ReactNode } from 'react';
import { Text, View } from '@/lib/tw';
import { cn } from '@/lib/cn';

type Tone = 'cream' | 'leaf' | 'skin' | 'outline' | 'ink';
type Size = 'sm' | 'md';

type Props = {
  label?: string;
  children?: ReactNode;
  tone?: Tone;
  size?: Size;
};

const TONE_BG: Record<Tone, string> = {
  cream: 'bg-surface-muted border border-transparent',
  leaf: 'bg-primary-soft border border-transparent',
  skin: 'bg-accent border border-transparent',
  outline: 'bg-transparent border border-border',
  ink: 'bg-foreground border border-transparent',
};

const TONE_FG: Record<Tone, string> = {
  cream: 'text-fg-muted',
  leaf: 'text-primary',
  skin: 'text-foreground',
  outline: 'text-fg-muted',
  ink: 'text-surface',
};

const SIZE_BOX: Record<Size, string> = {
  sm: 'h-6 px-2.5',
  md: 'h-[30px] px-3',
};

const SIZE_TEXT: Record<Size, string> = {
  sm: 'text-[11px]',
  md: 'text-[12.5px]',
};

export function Pill({ label, children, tone = 'cream', size = 'md' }: Props) {
  return (
    <View
      className={cn(
        'self-start flex-row items-center justify-center rounded-full',
        SIZE_BOX[size],
        TONE_BG[tone]
      )}
    >
      <Text className={cn('font-medium', SIZE_TEXT[size], TONE_FG[tone])}>{label ?? children}</Text>
    </View>
  );
}
