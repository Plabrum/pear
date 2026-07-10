import { cssInterop } from 'nativewind';
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

// View, Text, Pressable, ScrollView, TextInput, and SafeAreaView already get
// className→style interop for free from NativeWind's jsx pragma (see
// babel.config.js's jsxImportSource: 'nativewind') — these are plain
// re-exports so every existing `import { View, Text } from '@/lib/tw'`
// callsite keeps working unchanged.
export const View = RNView;
export const Text = RNText;
export const Pressable = RNPressable;
export const ScrollView = RNScrollView;
export const TextInput = RNTextInput;
export const SafeAreaView = RNSafeAreaView;

// Animated.createAnimatedComponent produces a new component type that isn't
// one of NativeWind's auto-registered core components, so it needs an
// explicit cssInterop registration.
export const AnimatedView = Animated.createAnimatedComponent(RNView);
cssInterop(AnimatedView, { className: 'style' });

// ── Modal / ModalView ──────────────────────────────────────────────────────────
//
// NativeWind resolves color tokens as CSS custom properties (e.g. `bg-black`
// → `var(--color-black)`). React Native's <Modal> renders into a separate
// native window layer where those CSS variables are NOT injected, so
// className color classes on the root View inside a Modal are silently
// dropped — the background appears transparent even though the class looks
// correct.
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
  return <RNView style={[{ flex: 1, backgroundColor }, style]} {...props} />;
}
ModalView.displayName = 'ModalView';
