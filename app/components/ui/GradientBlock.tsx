import type { ReactNode } from 'react';
import { LinearGradient } from 'expo-linear-gradient';
import type { ViewStyle } from 'react-native';
import { View, Text } from '@/lib/tw';

const GRAD_PALETTES: readonly (readonly [string, string])[] = [
  ['#F4C77B', '#E89B5A'],
  ['#A8C99B', '#5E8E5A'],
  ['#E8B4B4', '#C77878'],
  ['#C4B8E0', '#8C7BB8'],
  ['#B8D4D9', '#6E9CA3'],
  ['#E8D5A0', '#B89860'],
  ['#D9B8B8', '#A37070'],
  ['#B5C7B0', '#7A9070'],
  ['#E0C4D6', '#A87099'],
  ['#C9D4B8', '#8AA070'],
];

export function gradientFor(seed: string = 'A'): readonly [string, string] {
  const code = String(seed)
    .split('')
    .reduce((a, c) => a + c.charCodeAt(0), 0);
  return GRAD_PALETTES[code % GRAD_PALETTES.length];
}

type Props = {
  name?: string;
  size?: number;
  width?: number | string;
  height?: number | string;
  ratio?: number;
  radius?: number;
  showInitial?: boolean;
  className?: string;
  children?: ReactNode;
};

export function GradientBlock({
  name = 'A',
  size,
  width,
  height,
  ratio,
  radius = 12,
  showInitial = false,
  className,
  children,
}: Props) {
  const [c1, c2] = gradientFor(name);
  const initial = String(name).trim().charAt(0).toUpperCase();
  const w = size ?? width ?? '100%';
  const h = size ?? height ?? (ratio ? undefined : '100%');
  const initialFontSize = typeof w === 'number' ? Math.round(w * 0.42) : 64;

  const style: ViewStyle = {
    width: w as ViewStyle['width'],
    height: h as ViewStyle['height'],
    aspectRatio: ratio,
    borderRadius: radius,
    overflow: 'hidden',
  };

  return (
    <View className={className} style={style}>
      <LinearGradient
        colors={[c1, c2]}
        start={{ x: 0.15, y: 0 }}
        end={{ x: 0.85, y: 1 }}
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
      />
      <View
        pointerEvents="none"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(255,255,255,0.08)',
        }}
      />
      {showInitial ? (
        <View className="absolute bottom-1 left-3">
          <Text
            className="font-serif text-white"
            style={{ fontSize: initialFontSize, lineHeight: initialFontSize, letterSpacing: -1 }}
          >
            {initial}
          </Text>
        </View>
      ) : null}
      {children}
    </View>
  );
}
