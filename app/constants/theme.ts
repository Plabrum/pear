// Raw hex values for escape-hatch use: SVG stroke, dynamic borderColor,
// animated style props, and other contexts that need a plain JS color value
// instead of a className. For static styles, use className from @/lib/tw.
//
// Hex values are approximations of the Pear redesign tokens defined in
// global.css (which uses oklch for the brand colors). Keep these in sync
// when the design tokens change.

export const colors = {
  // Brand (leaf green / pear)
  primary: '#3F6E48',
  primarySoft: '#DDEBDC',

  // Leaf — brighter swipe/affirmative green (distinct from primary CTA leaf)
  leaf: '#5A8C3A',
  leafSoft: '#E5EFD8',
  // Leaf-tinted borders/fills at specific opacities (wing-pick cards, suggestion chips)
  leafBorder12: 'rgba(90,140,58,0.12)',
  leafBorder15: 'rgba(90,140,58,0.15)',

  // Pass — swipe-decline red
  passRed: '#CC4444',
  // Danger — softer red for destructive-button chrome (spinner/text), distinct from passRed
  dangerSoft: '#C77878',
  // Danger ink — transparent red used by destructive dialogs/icons
  dangerInk: '#A33',
  dangerTint: 'rgba(170,51,51,0.12)',

  // Foreground
  ink: '#1F1B16',
  inkMid: '#4A4338',
  inkDim: '#8B8170',
  inkGhost: 'rgba(31,27,22,0.30)',
  // Ink-tinted text/border overlays at specific opacities — keep each distinct,
  // don't round to a shared value.
  inkAlpha20: 'rgba(31,27,22,0.20)',
  inkAlpha35: 'rgba(31,27,22,0.35)',
  inkAlpha40: 'rgba(31,27,22,0.40)',
  inkAlpha45: 'rgba(31,27,22,0.45)',
  inkAlpha50: 'rgba(31,27,22,0.50)',
  inkAlpha55: 'rgba(31,27,22,0.55)',

  // Surfaces
  canvas: '#F5F1E8',
  muted: '#EDE6D6',

  // Borders / status
  divider: 'rgba(31,27,22,0.10)',
  green: '#4FAF6A',
  white: '#FBF8F1',
  // True white — distinct from `white` above (which is the off-white surface
  // tone); for PearMark's gradient stops (Stop isn't a rendered view, so it
  // can't take className — see PearMark.tsx).
  trueWhite: '#FFFFFF',

  // Black-scrim overlays (photo captions, action-icon chips) — each opacity is
  // a distinct in-use value, not rounded to a shared one. (Pure-black scrims at
  // a literal Tailwind color, e.g. a Portal backdrop, use `bg-black/NN` className
  // instead — see DateInput.native.tsx.)
  scrim35: 'rgba(0,0,0,0.35)',
  scrim45: 'rgba(0,0,0,0.45)',
  scrim55: 'rgba(0,0,0,0.55)',
  scrim65: 'rgba(0,0,0,0.65)',
  scrim70: 'rgba(0,0,0,0.7)',

  // White overlays (photo scrims, translucent chrome) — each opacity distinct.
  overlayWhite08: 'rgba(255,255,255,0.08)',
  overlayWhite22: 'rgba(255,255,255,0.22)',
  overlayWhite40: 'rgba(255,255,255,0.4)',
  overlayWhite85: 'rgba(255,255,255,0.85)',
  overlayWhite90: 'rgba(255,255,255,0.9)',
  overlayWhite95: 'rgba(255,255,255,0.95)',
  // Translucent surface tint (tab-bar blur chrome) — `white` at 70% opacity.
  surfaceOverlay70: 'rgba(251,248,241,0.7)',

  // PearMark stem default — a caller-overridable prop fallback, not a static
  // style, so it stays a plain JS value (see PearMark.tsx).
  pearMarkStem: '#6B4A2B',

  // Decorative PearMark tints — login hero cluster + onboarding role illustrations
  decorativeLeaf: '#7BAE52',
  decorativeSkin: '#E8C77A',
  decorativeBlush: '#E9A6A0',
  decorativeSage: '#A8C99B',
  decorativeRose: '#E8B4B4',
} as const;
