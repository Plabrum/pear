import { useCssElement } from 'react-native-css';
import React from 'react';
import {
  View as RNView,
  Text as RNText,
  Pressable as RNPressable,
  ScrollView as RNScrollView,
  TextInput as RNTextInput,
  Modal as RNModal,
} from 'react-native';
import { SafeAreaView as RNSafeAreaView } from 'react-native-safe-area-context';
import Animated from 'react-native-reanimated';

export const View = (props: React.ComponentProps<typeof RNView> & { className?: string }) =>
  useCssElement(RNView, props, { className: 'style' });
View.displayName = 'CSS(View)';

export const Text = (props: React.ComponentProps<typeof RNText> & { className?: string }) =>
  useCssElement(RNText, props, { className: 'style' });
Text.displayName = 'CSS(Text)';

export const Pressable = (
  props: React.ComponentProps<typeof RNPressable> & { className?: string }
) => useCssElement(RNPressable, props, { className: 'style' });
Pressable.displayName = 'CSS(Pressable)';

export const ScrollView = (
  props: React.ComponentProps<typeof RNScrollView> & {
    className?: string;
    contentContainerClassName?: string;
  }
) =>
  useCssElement(RNScrollView, props, {
    className: 'style',
    contentContainerClassName: 'contentContainerStyle',
  });
ScrollView.displayName = 'CSS(ScrollView)';

export const TextInput = (
  props: React.ComponentProps<typeof RNTextInput> & { className?: string }
) => useCssElement(RNTextInput, props, { className: 'style' });
TextInput.displayName = 'CSS(TextInput)';

export const SafeAreaView = (
  props: React.ComponentProps<typeof RNSafeAreaView> & { className?: string }
) => useCssElement(RNSafeAreaView, props, { className: 'style' });
SafeAreaView.displayName = 'CSS(SafeAreaView)';

export const AnimatedView = Animated.createAnimatedComponent(View);

// ── Modal / ModalView ──────────────────────────────────────────────────────────
//
// NativeWind v5 (Tailwind v4) resolves color tokens as CSS custom properties
// (e.g. `bg-black` → `var(--color-black)`). React Native's <Modal> renders
// into a separate native window layer where those CSS variables are NOT
// injected, so className color classes on the root View inside a Modal are
// silently dropped — the background appears transparent even though the class
// looks correct.
//
// Layout-only classes (flex-1, justify-center, p-6, etc.) resolve to plain CSS
// values and work fine inside a Modal. Only CSS-variable-backed values (colors,
// shadows, ring widths, etc.) are affected.
//
// Rule: never rely on className for backgroundColor (or any CSS-variable-backed
// style) on the root View inside a Modal. Use the `backgroundColor` prop on
// ModalView instead — it is applied via the `style` prop, bypassing the issue.

export { RNModal as Modal };

type ModalViewProps = React.ComponentProps<typeof RNView> & {
  className?: string;
  /** Applied via style prop — safe to use inside a Modal (see note above). */
  backgroundColor?: string;
};

export function ModalView({ backgroundColor = 'black', style, ...props }: ModalViewProps) {
  // backgroundColor is intentionally applied via style, NOT className.
  return useCssElement(
    RNView,
    { style: [{ flex: 1, backgroundColor }, style], ...props },
    { className: 'style' }
  );
}
ModalView.displayName = 'ModalView';
