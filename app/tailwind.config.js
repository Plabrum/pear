/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './App.tsx',
    './navigation/**/*.{js,jsx,ts,tsx}',
    './features/**/*.{js,jsx,ts,tsx}',
    './components/**/*.{js,jsx,ts,tsx}',
    './lib/**/*.{js,jsx,ts,tsx}',
    './hooks/**/*.{js,jsx,ts,tsx}',
    './context/**/*.{js,jsx,ts,tsx}',
    './constants/**/*.{js,jsx,ts,tsx}',
  ],
  presets: [require('nativewind/preset')],
  theme: {
    extend: {
      colors: {
        background: 'var(--color-background)',
        surface: 'var(--color-surface)',
        'surface-muted': 'var(--color-surface-muted)',

        foreground: 'var(--color-foreground)',
        'foreground-muted': 'var(--color-foreground-muted)',
        'foreground-subtle': 'var(--color-foreground-subtle)',

        primary: {
          DEFAULT: 'var(--color-primary)',
          foreground: 'var(--color-primary-foreground)',
          soft: 'var(--color-primary-soft)',
        },

        leaf: {
          DEFAULT: 'var(--color-leaf)',
          soft: 'var(--color-leaf-soft)',
        },

        'pass-red': 'var(--color-pass-red)',

        accent: {
          DEFAULT: 'var(--color-accent)',
          foreground: 'var(--color-accent-foreground)',
          muted: 'var(--color-accent-muted)',
          press: 'var(--color-accent-press)',
        },

        destructive: 'var(--color-destructive)',

        border: {
          DEFAULT: 'var(--color-border)',
          subtle: 'var(--color-border-subtle)',
        },

        // Transitional aliases — see global.css
        fg: {
          DEFAULT: 'var(--color-fg)',
          muted: 'var(--color-fg-muted)',
          subtle: 'var(--color-fg-subtle)',
          ghost: 'var(--color-fg-ghost)',
        },
        ink: {
          DEFAULT: 'var(--color-ink)',
          mid: 'var(--color-ink-mid)',
          dim: 'var(--color-ink-dim)',
        },
        page: 'var(--color-page)',
        canvas: 'var(--color-canvas)',
        muted: 'var(--color-muted)',
        separator: 'var(--color-separator)',
        error: 'var(--color-error)',
        green: 'var(--color-green)',

        'skeleton-base': 'var(--color-skeleton-base)',
        'skeleton-highlight': 'var(--color-skeleton-highlight)',

        'pearmark-shadow': 'var(--color-pearmark-shadow)',
        'pearmark-highlight': 'var(--color-pearmark-highlight)',
        'pearmark-highlight-border': 'var(--color-pearmark-highlight-border)',
      },
      fontFamily: {
        serif: 'var(--font-serif)',
        sans: 'var(--font-sans)',
      },
    },
  },
  plugins: [],
};
