// Raw hex values for escape-hatch use: SVG stroke, dynamic borderColor,
// animated style props, and legacy StyleSheet usage.
// For new static styles, prefer className from @/lib/tw instead.
//
// Hex values are approximations of the Pear redesign tokens defined in
// global.css (which uses oklch for the brand colors). Keep these in sync
// when the design tokens change.

// Legacy Fonts — used by onboarding screens for fontFamily in StyleSheet.
// New components should use font-serif / font-sans className instead.
import { Platform } from 'react-native';

export const colors = {
  // Brand (leaf green / pear)
  primary: '#3F6E48',
  primarySoft: '#DDEBDC',

  // Foreground
  ink: '#1F1B16',
  inkMid: '#4A4338',
  inkDim: '#8B8170',
  inkGhost: 'rgba(31,27,22,0.30)',

  // Surfaces
  canvas: '#F5F1E8',
  muted: '#EDE6D6',

  // Borders / status
  divider: 'rgba(31,27,22,0.10)',
  green: '#4FAF6A',
  white: '#FBF8F1',
} as const;

export const Fonts = Platform.select({
  ios: { serif: 'DMSerifDisplay', sans: 'Geist' },
  default: { serif: 'DMSerifDisplay', sans: 'Geist' },
});

// Legacy light/dark Colors used by collapsible.tsx
export const Colors = {
  light: {
    text: '#1F1B16',
    background: '#FBF8F1',
    tint: '#3F6E48',
    icon: '#4A4338',
    tabIconDefault: '#8B8170',
    tabIconSelected: '#3F6E48',
  },
  dark: {
    text: '#ECEDEE',
    background: '#151718',
    tint: '#fff',
    icon: '#9BA1A6',
    tabIconDefault: '#9BA1A6',
    tabIconSelected: '#fff',
  },
};
