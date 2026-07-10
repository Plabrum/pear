import { useId, useState } from 'react';
import { KeyboardAvoidingView, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Portal } from '@rn-primitives/portal';

import { View, Text, Pressable, TextInput } from '@/lib/tw';
import { Button } from '@/components/Button';
import { colors } from '@/constants/theme';

export function NoteModal({
  visible,
  daterFirstName,
  subjectName,
  onSend,
  onDismiss,
}: {
  visible: boolean;
  daterFirstName: string;
  subjectName: string;
  onSend: (note: string | null) => void;
  onDismiss: () => void;
}) {
  const insets = useSafeAreaInsets();
  const [note, setNote] = useState('');
  const portalName = useId();

  function handleSend(withNote: boolean) {
    onSend(withNote && note.trim().length > 0 ? note.trim() : null);
    setNote('');
  }

  if (!visible) return null;

  return (
    <Portal name={portalName}>
      {/* backgroundColor via style, not className: an ink-tinted color at a
          one-off opacity has no plain utility — NativeWind can't reliably
          compute fractional opacity against a CSS-variable-backed color. */}
      <View className="absolute inset-0" style={{ backgroundColor: colors.inkAlpha45 }}>
        <Pressable className="flex-1" onPress={onDismiss} />
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ position: 'absolute', bottom: 0, left: 0, right: 0 }}
        >
          <View
            className="bg-canvas rounded-tl-[24px] rounded-tr-[24px] px-5 pt-3.5"
            style={{ paddingBottom: insets.bottom + 24 }}
          >
            <View className="self-center w-10 h-1 rounded-full bg-border mb-3.5" />
            <Text
              className="font-serif text-ink"
              style={{ fontSize: 24, letterSpacing: -0.4, lineHeight: 28 }}
            >
              Add a note for {daterFirstName || 'them'}?
            </Text>
            <Text className="text-ink-dim" style={{ fontSize: 13, marginTop: 6, marginBottom: 14 }}>
              Why is {subjectName} a good pick? {daterFirstName || 'They'} will see this with the
              suggestion.
            </Text>
            <TextInput
              className="bg-surface text-ink border border-border rounded-[14px] p-3"
              style={{ width: '100%', minHeight: 90, fontSize: 14, textAlignVertical: 'top' }}
              placeholder={`e.g. they're obsessed with that pottery studio…`}
              placeholderTextColor={colors.inkDim}
              multiline
              value={note}
              onChangeText={setNote}
            />
            <View className="flex-row gap-2.5 mt-3.5">
              <View className="flex-1">
                <Button block variant="secondary" onPress={() => handleSend(false)}>
                  Skip & send
                </Button>
              </View>
              <View className="flex-1">
                <Button block onPress={() => handleSend(true)}>
                  Add note & send
                </Button>
              </View>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Portal>
  );
}
