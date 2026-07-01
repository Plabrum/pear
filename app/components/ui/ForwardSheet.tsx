import { useState } from 'react';
import { StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { WingingForRow } from '@/lib/api/generated/model';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import { useActionFormRenderer } from '@/hooks/actions/use-action-form-renderer';
import type { ActionDTO } from '@/lib/actions/types';
import { View, Text, Pressable } from '@/lib/tw';
import { Sheet } from '@/components/ui/Sheet';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { colors } from '@/constants/theme';

// Suggest is an object action on the target DatingProfile; the sheet collects the
// note and the chosen dater, so the body is built per-send (daterId varies).
const SUGGEST: ActionDTO = {
  action: 'dating_profile_swipe_actions__suggest',
  label: 'Suggest',
  action_group_type: 'dating_profile_swipe_actions',
};

const INK = colors.ink;
const INK_SUBTLE = colors.inkDim;
const LINE = colors.divider;

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
  const [pendingDater, setPendingDater] = useState<{ id: string; name: string } | null>(null);

  const executor = useActionExecutor({ actionGroup: 'dating_profile_swipe_actions' });
  const renderSuggestForm = useActionFormRenderer(
    pendingDater
      ? {
          daterFirstName: pendingDater.name.split(' ')[0] || pendingDater.name,
          subjectName: recipientName ?? 'they',
        }
      : undefined
  );

  const targets = wingingFor.filter(
    (r) => r.dater?.id !== excludeDaterId && r.dater?.id !== recipientId
  );

  async function handleNoteSend(note: string | null) {
    if (!pendingDater) return;
    const ok = await executor
      .executeAction(
        SUGGEST,
        { action: SUGGEST.action, data: { daterId: pendingDater.id, note } },
        { objectId: recipientProfileId, silent: true }
      )
      .then(() => true)
      .catch(() => false);
    if (!ok) return; // the executor already surfaced the error toast
    setPendingDater(null);
    onClose();
  }

  function handleClose() {
    setPendingDater(null);
    onClose();
  }

  return (
    <>
      <Sheet
        visible={visible && pendingDater === null}
        onClose={handleClose}
        title="Forward to"
        subtitle="Suggest this profile to someone you're winging for."
      >
        {targets.length === 0 ? (
          <Text style={{ fontSize: 14, color: INK_SUBTLE, paddingVertical: 20, textAlign: 'center' }}>
            No one else to forward to right now.
          </Text>
        ) : (
          targets.map((row) => {
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
                  paddingVertical: 14,
                  borderBottomWidth: StyleSheet.hairlineWidth,
                  borderBottomColor: LINE,
                }}
              >
                <FaceAvatar
                  name={dater.chosenName ?? '?'}
                  size={38}
                  photoUri={dater.avatarUrl ?? null}
                />
                <Text
                  style={{ flex: 1, fontSize: 16, fontWeight: '500', color: INK, marginLeft: 12 }}
                >
                  {dater.chosenName ?? 'Unnamed'}
                </Text>
                <Ionicons name="chevron-forward" size={18} color={INK_SUBTLE} />
              </Pressable>
            );
          })
        )}
      </Sheet>

      {pendingDater &&
        renderSuggestForm({
          action: SUGGEST,
          onSubmit: (body) => handleNoteSend((body.data?.note ?? null) as string | null),
          onClose: () => setPendingDater(null),
          isSubmitting: executor.isExecuting,
          isOpen: true,
          actionLabel: SUGGEST.label,
        })}
    </>
  );
}
