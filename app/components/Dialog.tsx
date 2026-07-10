// Dialog — centered confirm / alert / destructive overlay, built on the headless
// @rn-primitives/dialog (the react-native-reusables / Radix-style primitive). It
// renders through @rn-primitives/portal — an IN-TREE host mounted inside the app's
// providers (app/_layout.tsx) — NOT a native <Modal> window. So NativeWind
// className color tokens resolve normally here (no style-color workaround needed),
// and Query/Auth/Theme context is available to portaled content.
import * as React from 'react';
import { StyleSheet } from 'react-native';
import * as DialogPrimitive from '@rn-primitives/dialog';
import Animated, { FadeIn, FadeOut, ZoomIn } from 'react-native-reanimated';

import { View, Text, Pressable } from '@/lib/tw';
import { Button } from '@/components/Button';
import { colors } from '@/constants/theme';

/** Design danger ink — transparent red used by destructive dialogs/icons. */
export const DIALOG_DANGER = colors.dangerInk;

type ButtonVariant = 'primary' | 'secondary' | 'accent' | 'ghost' | 'danger';

type DialogAction = {
  label: string;
  variant?: ButtonVariant;
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
};

type Props = {
  visible: boolean;
  onClose: () => void;
  title?: string;
  /** Supporting copy under the title. `subtitle` is an alias for `body`. */
  body?: string;
  subtitle?: string;
  icon?: React.ReactNode;
  tone?: 'default' | 'danger';
  actions?: DialogAction[];
  dismissable?: boolean;
  onShow?: () => void;
  children?: React.ReactNode;
};

export function Dialog({
  visible,
  onClose,
  title,
  body,
  subtitle,
  icon,
  tone = 'default',
  actions = [],
  dismissable = true,
  onShow,
  children,
}: Props) {
  const text = body ?? subtitle;

  // Fire onShow when the dialog transitions into view (parity with the old
  // Modal `onShow`; used by createTypedForm to reset the form on open).
  const wasVisible = React.useRef(false);
  React.useEffect(() => {
    if (visible && !wasVisible.current) onShow?.();
    wasVisible.current = visible;
  }, [visible, onShow]);

  return (
    <DialogPrimitive.Root
      open={visible}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          closeOnPress={dismissable}
          style={[
            StyleSheet.absoluteFill,
            {
              backgroundColor: colors.inkAlpha50,
              alignItems: 'center',
              justifyContent: 'center',
              padding: 28,
            },
          ]}
        >
          <Animated.View entering={FadeIn.duration(120)} exiting={FadeOut.duration(120)}>
            <DialogPrimitive.Content>
              {/* No-op Pressable absorbs taps so pressing the card doesn't bubble
                  to the scrim and dismiss. */}
              <Pressable onPress={() => {}}>
                <Animated.View entering={ZoomIn.springify().damping(18)}>
                  <View
                    className="w-full bg-background rounded-[24px] px-[22px] pt-6 pb-[18px]"
                    style={{ maxWidth: 320 }}
                  >
                    {icon ? (
                      <View
                        className={
                          tone === 'danger'
                            ? 'w-[52px] h-[52px] rounded-[26px] items-center justify-center self-center mb-3.5'
                            : 'w-[52px] h-[52px] rounded-[26px] items-center justify-center self-center mb-3.5 bg-primary-soft'
                        }
                        style={
                          tone === 'danger' ? { backgroundColor: colors.dangerTint } : undefined
                        }
                      >
                        {icon}
                      </View>
                    ) : null}

                    {title ? (
                      <DialogPrimitive.Title asChild>
                        <Text
                          className="font-serif text-foreground text-center"
                          style={{ fontSize: 24, lineHeight: 26, letterSpacing: -0.4 }}
                        >
                          {title}
                        </Text>
                      </DialogPrimitive.Title>
                    ) : null}

                    {text ? (
                      <DialogPrimitive.Description asChild>
                        <Text
                          className="text-foreground-muted text-center"
                          style={{ fontSize: 14, lineHeight: 21, marginTop: 8 }}
                        >
                          {text}
                        </Text>
                      </DialogPrimitive.Description>
                    ) : null}

                    {children ? <View className="mt-4">{children}</View> : null}

                    {actions.length > 0 ? (
                      <View className="mt-5" style={{ gap: 8 }}>
                        {actions.map((a, i) => {
                          const variant: ButtonVariant =
                            a.variant ??
                            (tone === 'danger' && i === 0
                              ? 'danger'
                              : i === 0
                                ? 'primary'
                                : 'secondary');
                          return (
                            <Button
                              key={a.label}
                              block
                              variant={variant}
                              onPress={a.onClick}
                              loading={a.loading}
                              disabled={a.disabled}
                            >
                              {a.label}
                            </Button>
                          );
                        })}
                      </View>
                    ) : null}
                  </View>
                </Animated.View>
              </Pressable>
            </DialogPrimitive.Content>
          </Animated.View>
        </DialogPrimitive.Overlay>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
