// Sheet — the workhorse bottom slide-up overlay. Rendered through the SAME in-tree
// @rn-primitives portal as Dialog (PortalHost lives inside the app providers in
// app/_layout.tsx), so it sizes to its content automatically (it's a normal view —
// no snap points, no measurement) and NativeWind className tokens resolve.
//
// gorhom/bottom-sheet was tried but its dynamic content sizing relies on a reanimated
// shared-value→derivedValue path that doesn't propagate on this RN-Fabric / reanimated
// v4 stack (present() no-ops with no resolvable detent). This portal approach avoids
// that entirely. Open/close is a reanimated translateY animation; the grab handle
// carries a pan gesture for swipe-down-to-dismiss.
import * as React from 'react';
import { StyleSheet, useWindowDimensions } from 'react-native';
import { useReanimatedKeyboardAnimation } from 'react-native-keyboard-controller';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import {
  interpolate,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import { Ionicons } from '@expo/vector-icons';
import { Portal } from '@rn-primitives/portal';

import { View, Text, Pressable, ScrollView, AnimatedView } from '@/lib/tw';
import { colors } from '@/constants/theme';

const OPEN = { duration: 300 } as const;
const CLOSE = { duration: 220 } as const;

type Props = {
  visible: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  /** Sticky bottom action bar (paper bg, top border, safe-area inset). */
  footer?: React.ReactNode;
  /** Tap-scrim / swipe-down to close + show the close button. Default true. */
  dismissable?: boolean;
  /** 'auto' sizes to content (capped at 90%); 'full' fills to a tall card. */
  size?: 'auto' | 'full';
  /** Optional fixed height (e.g. '70%') — a scrollable card of that height. */
  maxHeight?: number | `${number}%`;
  showHandle?: boolean;
  /** Kept for API compatibility (KeyboardAvoidingView is always on). */
  keyboardAvoiding?: boolean;
  /** Set false when the caller owns a FlatList/native picker (no inner ScrollView). */
  scrollable?: boolean;
  onShow?: () => void;
  children?: React.ReactNode;
};

export function Sheet({
  visible,
  onClose,
  title,
  subtitle,
  footer,
  dismissable = true,
  size = 'auto',
  maxHeight,
  showHandle = true,
  scrollable = true,
  onShow,
  children,
}: Props) {
  const insets = useSafeAreaInsets();
  const { height: winH } = useWindowDimensions();
  // Animated keyboard height (negative when open) — lifts the card above the keyboard.
  const { height: kb } = useReanimatedKeyboardAnimation();
  const portalName = React.useId();

  // Kept mounted through the close animation; unmounts when it finishes.
  const [mounted, setMounted] = React.useState(false);
  const translateY = useSharedValue(winH);

  React.useEffect(() => {
    if (visible) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMounted(true);
      onShow?.();
      translateY.value = winH;
      translateY.value = withTiming(0, OPEN);
    } else if (mounted) {
      translateY.value = withTiming(winH, CLOSE, (finished) => {
        if (finished) runOnJS(setMounted)(false);
      });
    }
    // animation lifecycle keys off `visible`; onShow excluded intentionally.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, mounted, winH]);

  const cardStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value + kb.value }],
  }));
  const backdropStyle = useAnimatedStyle(() => ({
    opacity: interpolate(translateY.value, [0, winH], [0.45, 0]),
  }));

  // Swipe-down-to-dismiss lives on the grab handle (not the whole card) so it never
  // fights an inner ScrollView.
  const pan = Gesture.Pan()
    .enabled(dismissable)
    .onUpdate((e) => {
      // eslint-disable-next-line react-hooks/immutability
      translateY.value = Math.max(0, e.translationY);
    })
    .onEnd((e) => {
      if (e.translationY > 110 || e.velocityY > 800) {
        runOnJS(onClose)();
      } else {
        // eslint-disable-next-line react-hooks/immutability
        translateY.value = withSpring(0, { damping: 22, stiffness: 240 });
      }
    });

  if (!mounted) return null;

  // 'full' / explicit maxHeight → a fixed-height, scrollable card. 'auto' → natural
  // content height, capped at 90% (overflow clipped — use 'full' for long content).
  const fixedHeight = size === 'full' ? '90%' : (maxHeight ?? null);

  const handle = (
    <GestureDetector gesture={pan}>
      <View className="items-center pt-2.5 pb-1">
        {showHandle ? (
          <View
            style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: colors.divider }}
          />
        ) : null}
      </View>
    </GestureDetector>
  );

  const header =
    title || dismissable ? (
      <View className="flex-row items-start px-5 pt-1 pb-1.5" style={{ gap: 12 }}>
        <View className="flex-1 min-w-0">
          {title ? (
            <Text
              className="font-serif text-foreground"
              style={{ fontSize: 26, lineHeight: 28, letterSpacing: -0.5 }}
            >
              {title}
            </Text>
          ) : null}
          {subtitle ? (
            <Text
              className="text-foreground-subtle"
              style={{ fontSize: 13.5, lineHeight: 20, marginTop: 6 }}
            >
              {subtitle}
            </Text>
          ) : null}
        </View>
        {dismissable ? (
          <Pressable
            onPress={onClose}
            hitSlop={8}
            className="w-[30px] h-[30px] rounded-[15px] items-center justify-center bg-surface-muted"
          >
            <Ionicons name="close" size={16} color={colors.inkMid} />
          </Pressable>
        ) : null}
      </View>
    ) : null;

  const bodyInner = <View className="px-5 pt-3">{children}</View>;
  const footerBlock = footer ? (
    <View
      className="bg-surface px-5 pt-3"
      style={{
        paddingBottom: insets.bottom + 12,
        borderTopWidth: StyleSheet.hairlineWidth,
        borderTopColor: colors.divider,
      }}
    >
      {footer}
    </View>
  ) : null;

  return (
    <Portal name={portalName}>
      <View style={StyleSheet.absoluteFill}>
        <AnimatedView
          style={[StyleSheet.absoluteFill, { backgroundColor: colors.ink }, backdropStyle]}
        />
        <Pressable style={StyleSheet.absoluteFill} onPress={dismissable ? onClose : undefined} />
        <AnimatedView
          className="bg-background"
          style={[
            {
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 0,
              borderTopLeftRadius: 26,
              borderTopRightRadius: 26,
              overflow: 'hidden',
              maxHeight: '90%',
              ...(fixedHeight != null ? { height: fixedHeight } : null),
            },
            cardStyle,
          ]}
        >
          {handle}
          {scrollable && fixedHeight != null ? (
            <>
              {header}
              <ScrollView
                style={{ flex: 1 }}
                contentContainerStyle={{ paddingBottom: footer ? 0 : insets.bottom + 16 }}
                keyboardShouldPersistTaps="handled"
              >
                {bodyInner}
              </ScrollView>
              {footerBlock}
            </>
          ) : (
            <>
              {header}
              {bodyInner}
              {footer ? footerBlock : <View style={{ height: insets.bottom + 16 }} />}
            </>
          )}
        </AnimatedView>
      </View>
    </Portal>
  );
}
