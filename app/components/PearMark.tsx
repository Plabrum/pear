import type { ColorValue } from 'react-native';
import Svg, {
  Defs,
  Ellipse as SvgEllipse,
  Path as SvgPath,
  RadialGradient,
  Stop,
} from 'react-native-svg';
import { cssInterop } from 'nativewind';
import { colors } from '@/constants/theme';

// react-native-svg's fill/stroke props aren't RN style props, so Ellipse/Path
// need explicit cssInterop wiring to accept className for the static,
// internal-only decorative colors below (shadow/highlight accents). Keyed off
// `color` (via `text-*` classNames), not `fill`/`stroke` — NativeWind doesn't
// reliably parse those as real CSS properties in this Tailwind v3 setup.
// `color`/`leaf`/`stem` stay plain JS props — PearMark is a caller-colorable
// icon (any hex a caller passes in), which a static className can't express.
// `Stop` (gradient metadata, not an actual rendered view) isn't wired the same
// way — cssInterop intercepts props right before a real native view mounts,
// and Stop never mounts one, so its className was silently dropped (leaving
// stopColor at SVG's default black). It keeps a plain `stopColor` prop.
const Ellipse = cssInterop(SvgEllipse, {
  className: { target: false, nativeStyleToProp: { color: 'fill' } },
});
const Path = cssInterop(SvgPath, {
  className: { target: false, nativeStyleToProp: { color: 'stroke' } },
});

type Variant = 'soft' | 'flat' | 'outline';

type Props = {
  size?: number;
  color?: ColorValue;
  leaf?: string;
  stem?: string;
  variant?: Variant;
};

const BODY =
  'M16 30.0c-4.6 0-7.6-3.6-7.6-7.8 0-3.0 1.2-5.6 3.0-7.5 1.5-1.6 2.8-3.0 3.4-4.7.4-1.1.5-2.3.7-3.0.2-.7.7-1.0 1.4-1.1.2 0 .4 0 .6 0s.4 0 .6 0c.7.1 1.2.4 1.4 1.1.2.7.3 1.9.7 3.0.6 1.7 1.9 3.1 3.4 4.7 1.8 1.9 3.0 4.5 3.0 7.5 0 4.2-3.0 7.8-7.6 7.8z';
const STEM = 'M15.8 6.2c.4-1.0 1.2-2.0 2.2-2.6';
const LEAF = 'M17.4 4.0c2.6-1.8 5.8-1.6 7.4.2-.8 2.4-3.6 3.8-6.4 3.6-1.2-.1-2.0-2.4-1.0-3.8z';
const LEAF_VEIN = 'M18.2 4.6c1.8.0 4.0-.2 5.8-.8';

export function PearMark({ size = 28, color = colors.leaf, leaf, stem, variant = 'soft' }: Props) {
  const leafColor = leaf ?? color;
  const stemColor = stem ?? (variant === 'outline' ? color : colors.pearMarkStem);
  const shadow = <Ellipse cx="16" cy="30.6" rx="4.6" ry="0.7" className="text-pearmark-shadow" />;

  if (variant === 'outline') {
    return (
      <Svg width={size} height={size} viewBox="0 0 32 32" fill="none">
        {shadow}
        <Path d={BODY} stroke={color} strokeWidth={1.7} strokeLinejoin="round" fill="none" />
        <Path d={STEM} stroke={color} strokeWidth={1.7} strokeLinecap="round" fill="none" />
        <Path d={LEAF} stroke={color} strokeWidth={1.7} strokeLinejoin="round" fill="none" />
      </Svg>
    );
  }

  if (variant === 'flat') {
    return (
      <Svg width={size} height={size} viewBox="0 0 32 32" fill="none">
        {shadow}
        <Path d={BODY} fill={color} />
        <Path d={STEM} stroke={stemColor} strokeWidth={2} strokeLinecap="round" fill="none" />
        <Path d={LEAF} fill={leafColor} />
      </Svg>
    );
  }

  const gradId = `pg-${size}`;
  return (
    <Svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <Defs>
        <RadialGradient id={gradId} cx="38%" cy="44%" r="62%">
          <Stop offset="0%" stopColor={colors.trueWhite} stopOpacity={0.34} />
          <Stop offset="55%" stopColor={colors.trueWhite} stopOpacity={0} />
        </RadialGradient>
      </Defs>
      {shadow}
      <Path d={BODY} fill={color} />
      <Path d={BODY} fill={`url(#${gradId})`} />
      <Ellipse
        cx="11.8"
        cy="20.6"
        rx="2.4"
        ry="3.6"
        className="text-pearmark-highlight"
        transform="rotate(-18 11.8 20.6)"
      />
      <Path d={STEM} stroke={stemColor} strokeWidth={2} strokeLinecap="round" fill="none" />
      <Path d={LEAF} fill={leafColor} />
      <Path
        d={LEAF_VEIN}
        className="text-pearmark-highlight-border"
        strokeWidth={0.7}
        strokeLinecap="round"
        fill="none"
      />
    </Svg>
  );
}
