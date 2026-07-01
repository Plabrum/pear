import Svg, { Defs, Ellipse, Path, RadialGradient, Stop } from 'react-native-svg';

type Variant = 'soft' | 'flat' | 'outline';

type Props = {
  size?: number;
  color?: string;
  leaf?: string;
  stem?: string;
  variant?: Variant;
};

const BODY =
  'M16 30.0c-4.6 0-7.6-3.6-7.6-7.8 0-3.0 1.2-5.6 3.0-7.5 1.5-1.6 2.8-3.0 3.4-4.7.4-1.1.5-2.3.7-3.0.2-.7.7-1.0 1.4-1.1.2 0 .4 0 .6 0s.4 0 .6 0c.7.1 1.2.4 1.4 1.1.2.7.3 1.9.7 3.0.6 1.7 1.9 3.1 3.4 4.7 1.8 1.9 3.0 4.5 3.0 7.5 0 4.2-3.0 7.8-7.6 7.8z';
const STEM = 'M15.8 6.2c.4-1.0 1.2-2.0 2.2-2.6';
const LEAF = 'M17.4 4.0c2.6-1.8 5.8-1.6 7.4.2-.8 2.4-3.6 3.8-6.4 3.6-1.2-.1-2.0-2.4-1.0-3.8z';
const LEAF_VEIN = 'M18.2 4.6c1.8.0 4.0-.2 5.8-.8';

const DEFAULT_LEAF = '#5A8C3A';

export function PearMark({ size = 28, color = DEFAULT_LEAF, leaf, stem, variant = 'soft' }: Props) {
  const leafColor = leaf ?? color;
  const stemColor = stem ?? (variant === 'outline' ? color : '#6B4A2B');
  const shadow = <Ellipse cx="16" cy="30.6" rx="4.6" ry="0.7" fill="rgba(31,27,22,.16)" />;

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
          <Stop offset="0%" stopColor="#fff" stopOpacity={0.34} />
          <Stop offset="55%" stopColor="#fff" stopOpacity={0} />
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
        fill="rgba(255,255,255,.24)"
        transform="rotate(-18 11.8 20.6)"
      />
      <Path d={STEM} stroke={stemColor} strokeWidth={2} strokeLinecap="round" fill="none" />
      <Path d={LEAF} fill={leafColor} />
      <Path
        d={LEAF_VEIN}
        stroke="rgba(255,255,255,.42)"
        strokeWidth={0.7}
        strokeLinecap="round"
        fill="none"
      />
    </Svg>
  );
}
