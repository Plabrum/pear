import { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { View, Text, Pressable, TextInput } from '@/lib/tw';
import { Button } from '@/components/Button';

const LINE = 'rgba(31,27,22,0.10)';
const INK3 = '#8B8170';

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

  function handleSend(withNote: boolean) {
    onSend(withNote && note.trim().length > 0 ? note.trim() : null);
    setNote('');
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onDismiss}>
      <View className="flex-1" style={{ backgroundColor: 'rgba(31,27,22,0.45)' }}>
        <Pressable className="flex-1" onPress={onDismiss} />
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={{ position: 'absolute', bottom: 0, left: 0, right: 0 }}
        >
          <View
            className="bg-canvas"
            style={{
              borderTopLeftRadius: 24,
              borderTopRightRadius: 24,
              paddingHorizontal: 20,
              paddingTop: 14,
              paddingBottom: insets.bottom + 24,
            }}
          >
            <View
              style={{
                alignSelf: 'center',
                width: 40,
                height: 4,
                borderRadius: 2,
                backgroundColor: LINE,
                marginBottom: 14,
              }}
            />
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
              className="bg-surface text-ink"
              style={{
                width: '100%',
                minHeight: 90,
                borderWidth: 1,
                borderColor: LINE,
                borderRadius: 14,
                padding: 12,
                fontSize: 14,
                textAlignVertical: 'top',
              }}
              placeholder={`e.g. they're obsessed with that pottery studio…`}
              placeholderTextColor={INK3}
              multiline
              value={note}
              onChangeText={setNote}
            />
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 14 }}>
              <View style={{ flex: 1 }}>
                <Button block variant="secondary" onPress={() => handleSend(false)}>
                  Skip & send
                </Button>
              </View>
              <View style={{ flex: 1 }}>
                <Button block onPress={() => handleSend(true)}>
                  Add note & send
                </Button>
              </View>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}
