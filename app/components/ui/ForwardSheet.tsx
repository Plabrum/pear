import { useState } from 'react';
import { Modal, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { toast } from 'sonner-native';
import { suggest } from '@/lib/api/actions';
import type { WingingForRow } from '@/lib/api/generated/model';
import { View, Text, Pressable } from '@/lib/tw';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { NoteModal } from '@/components/ui/NoteModal';

const INK = '#1F1B16';
const INK_SUBTLE = '#8B8170';
const PAPER = '#FBF8F1';
const LINE = 'rgba(31,27,22,0.10)';

type Props = {
  visible: boolean;
  // User id of the profile being forwarded — used to keep a dater from being
  // suggested to themselves.
  recipientId: string;
  // Dating-profile id of the profile being forwarded — the suggest action target.
  recipientProfileId: string;
  recipientName?: string;
  wingingFor: WingingForRow[];
  excludeDaterId?: string;
  onClose: () => void;
};

export function ForwardSheet({
  visible,
  recipientId,
  recipientProfileId,
  recipientName,
  wingingFor,
  excludeDaterId,
  onClose,
}: Props) {
  const insets = useSafeAreaInsets();
  const [pendingDater, setPendingDater] = useState<{ id: string; name: string } | null>(null);

  const targets = wingingFor.filter(
    (r) => r.dater?.id !== excludeDaterId && r.dater?.id !== recipientId
  );

  async function handleNoteSend(note: string | null) {
    if (!pendingDater) return;
    const result = await suggest(recipientProfileId, {
      daterId: pendingDater.id,
      note,
      decision: null,
    }).catch(() => null);
    if (result == null) {
      toast.error("Couldn't forward this profile. Try again.");
      return;
    }
    setPendingDater(null);
    onClose();
  }

  function handleClose() {
    setPendingDater(null);
    onClose();
  }

  return (
    <>
      <Modal
        visible={visible && pendingDater === null}
        animationType="slide"
        transparent
        onRequestClose={handleClose}
      >
        <View style={{ flex: 1, backgroundColor: 'rgba(31,27,22,0.45)' }}>
          <Pressable style={{ flex: 1 }} onPress={handleClose} />
          <View
            style={{
              backgroundColor: PAPER,
              borderTopLeftRadius: 24,
              borderTopRightRadius: 24,
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
                marginBottom: 16,
              }}
            />
            <Text
              style={{
                fontFamily: 'DMSerifDisplay',
                fontSize: 22,
                letterSpacing: -0.3,
                color: INK,
                paddingHorizontal: 20,
                marginBottom: 6,
              }}
            >
              Forward to
            </Text>
            <Text
              style={{
                fontSize: 13,
                color: INK_SUBTLE,
                paddingHorizontal: 20,
                marginBottom: 4,
              }}
            >
              Suggest this profile to someone you{"'"}re winging for.
            </Text>

            {targets.length === 0 ? (
              <Text
                style={{
                  fontSize: 14,
                  color: INK_SUBTLE,
                  paddingHorizontal: 20,
                  paddingVertical: 20,
                  textAlign: 'center',
                }}
              >
                No one else to forward to right now.
              </Text>
            ) : (
              targets.map((row, i) => {
                const dater = row.dater;
                if (!dater) return null;
                return (
                  <Pressable
                    key={row.id}
                    onPress={() =>
                      setPendingDater({
                        id: dater.id,
                        name: dater.chosenName ?? '',
                      })
                    }
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      paddingHorizontal: 20,
                      paddingVertical: 14,
                      borderTopWidth: StyleSheet.hairlineWidth,
                      borderTopColor: LINE,
                      marginTop: i === 0 ? 10 : 0,
                    }}
                  >
                    <FaceAvatar
                      name={dater.chosenName ?? '?'}
                      size={38}
                      photoUri={dater.avatarUrl ?? null}
                    />
                    <Text
                      style={{
                        flex: 1,
                        fontSize: 16,
                        fontWeight: '500',
                        color: INK,
                        marginLeft: 12,
                      }}
                    >
                      {dater.chosenName ?? 'Unnamed'}
                    </Text>
                    <Ionicons name="chevron-forward" size={18} color={INK_SUBTLE} />
                  </Pressable>
                );
              })
            )}
          </View>
        </View>
      </Modal>

      <NoteModal
        visible={pendingDater !== null}
        daterFirstName={pendingDater?.name.split(' ')[0] ?? ''}
        subjectName={recipientName ?? 'they'}
        onSend={handleNoteSend}
        onDismiss={() => setPendingDater(null)}
      />
    </>
  );
}
