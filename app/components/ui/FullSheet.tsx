// FullSheet — full-screen multi-field form overlay. RN translation of the
// designer's Pear kit `FullSheet`. Header carries a back affordance + an optional
// mono step counter; a sticky footer hosts the primary action.
//
// COLOR CAVEAT: chrome colors via `style` (see lib/tw.tsx); className layout-only.
import type { ReactNode } from 'react';
import { KeyboardAvoidingView, Modal, Platform, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { View, Text, Pressable, ScrollView } from '@/lib/tw';
import { colors } from '@/constants/theme';

type Props = {
  visible: boolean;
  onClose: () => void;
  onBack?: () => void;
  title?: string;
  /** Mono uppercase step counter, e.g. "Step 2 of 3". */
  step?: string;
  footer?: ReactNode;
  scrollable?: boolean;
  onShow?: () => void;
  children?: ReactNode;
};

export function FullSheet({
  visible,
  onClose,
  onBack,
  title,
  step,
  footer,
  scrollable = true,
  onShow,
  children,
}: Props) {
  const insets = useSafeAreaInsets();

  return (
    <Modal
      visible={visible}
      animationType="slide"
      onRequestClose={onBack ?? onClose}
      onShow={onShow}
    >
      <View style={{ flex: 1, backgroundColor: colors.canvas }}>
        <View
          style={{
            paddingTop: insets.top + 8,
            paddingHorizontal: 12,
            paddingBottom: 12,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Pressable onPress={onBack ?? onClose} hitSlop={8} style={{ padding: 6, marginLeft: -4 }}>
            <Ionicons name="chevron-back" size={24} color={colors.ink} />
          </Pressable>
          <View style={{ flex: 1 }}>
            {step ? (
              <Text
                style={{
                  fontSize: 10.5,
                  letterSpacing: 1.4,
                  textTransform: 'uppercase',
                  color: colors.inkDim,
                  fontWeight: '600',
                }}
              >
                {step}
              </Text>
            ) : null}
            {title ? (
              <Text
                style={{
                  fontFamily: 'DMSerifDisplay',
                  fontSize: 22,
                  letterSpacing: -0.4,
                  color: colors.ink,
                  lineHeight: 26,
                }}
              >
                {title}
              </Text>
            ) : null}
          </View>
        </View>

        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          {scrollable ? (
            <ScrollView
              style={{ flex: 1 }}
              contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 8, paddingBottom: 20 }}
              keyboardShouldPersistTaps="handled"
            >
              {children}
            </ScrollView>
          ) : (
            <View style={{ flex: 1, paddingHorizontal: 20, paddingTop: 8 }}>{children}</View>
          )}

          {footer ? (
            <View
              style={{
                paddingHorizontal: 20,
                paddingTop: 12,
                paddingBottom: insets.bottom + 12,
                borderTopWidth: StyleSheet.hairlineWidth,
                borderTopColor: colors.divider,
                backgroundColor: colors.white,
              }}
            >
              {footer}
            </View>
          ) : null}
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}
