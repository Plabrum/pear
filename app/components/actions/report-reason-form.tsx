// Registered form for `dating_profile_swipe_actions__report` — the two-step
// confirm → reason flow a dater uses to report a profile from the swipe deck.
// Conforms to the action-registry render contract; collects only the reason text
// (the executor records the report). Ported verbatim from the former inline modal
// in discover.tsx so the look is unchanged.
import { useState } from 'react';

import { Modal, ModalView, View, Text, Pressable, TextInput } from '@/lib/tw';

type ReportStep = 'confirm' | 'reason';

const INK = '#1F1B16';
const INK_MUTED = '#4A4338';
const INK_SUBTLE = '#8B8170';
const PAPER = '#FBF8F1';
const LINE = 'rgba(31,27,22,0.10)';
const PASS_RED = '#C44';

export function ReportReasonForm({
  onSubmit,
  onClose,
  isSubmitting,
  isOpen,
}: {
  objectData?: unknown;
  onSubmit: (data: { reason: string }) => void;
  onClose: () => void;
  isSubmitting: boolean;
  isOpen: boolean;
}) {
  const [step, setStep] = useState<ReportStep>('confirm');
  const [reason, setReason] = useState('');

  const submit = () => {
    if (!reason.trim() || isSubmitting) return;
    onSubmit({ reason: reason.trim() });
  };

  return (
    <Modal visible={isOpen} transparent animationType="fade" onRequestClose={onClose}>
      <ModalView
        backgroundColor="rgba(0,0,0,0.5)"
        style={{ justifyContent: 'center', alignItems: 'center', padding: 24 }}
      >
        <View
          style={{
            backgroundColor: PAPER,
            borderRadius: 22,
            padding: 24,
            width: '100%',
            maxWidth: 360,
            gap: 16,
          }}
        >
          {step === 'confirm' ? (
            <>
              <View style={{ gap: 6 }}>
                <Text style={{ fontFamily: 'DMSerifDisplay', fontSize: 22, color: INK }}>
                  Report profile?
                </Text>
                <Text style={{ fontSize: 14, color: INK_MUTED, lineHeight: 20 }}>
                  Something feel off? Let us know and we&apos;ll look into it.
                </Text>
              </View>
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <Pressable
                  onPress={onClose}
                  style={{
                    flex: 1,
                    paddingVertical: 13,
                    borderRadius: 14,
                    borderWidth: 1,
                    borderColor: LINE,
                    alignItems: 'center',
                  }}
                >
                  <Text style={{ fontSize: 15, fontWeight: '600', color: INK_MUTED }}>
                    No, cancel
                  </Text>
                </Pressable>
                <Pressable
                  onPress={() => setStep('reason')}
                  style={{
                    flex: 1,
                    paddingVertical: 13,
                    borderRadius: 14,
                    backgroundColor: PASS_RED,
                    alignItems: 'center',
                  }}
                >
                  <Text style={{ fontSize: 15, fontWeight: '600', color: PAPER }}>Yes, report</Text>
                </Pressable>
              </View>
            </>
          ) : (
            <>
              <View style={{ gap: 6 }}>
                <Text style={{ fontFamily: 'DMSerifDisplay', fontSize: 22, color: INK }}>
                  What&apos;s the issue?
                </Text>
                <Text style={{ fontSize: 14, color: INK_MUTED, lineHeight: 20 }}>
                  Describe the problem so we can review it.
                </Text>
              </View>
              <TextInput
                value={reason}
                onChangeText={setReason}
                placeholder="Describe the issue…"
                placeholderTextColor={INK_SUBTLE}
                multiline
                maxLength={500}
                style={{
                  backgroundColor: 'white',
                  borderWidth: 1,
                  borderColor: LINE,
                  borderRadius: 14,
                  padding: 14,
                  fontSize: 14,
                  color: INK,
                  minHeight: 100,
                  textAlignVertical: 'top',
                }}
              />
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <Pressable
                  onPress={onClose}
                  style={{
                    flex: 1,
                    paddingVertical: 13,
                    borderRadius: 14,
                    borderWidth: 1,
                    borderColor: LINE,
                    alignItems: 'center',
                  }}
                >
                  <Text style={{ fontSize: 15, fontWeight: '600', color: INK_MUTED }}>Cancel</Text>
                </Pressable>
                <Pressable
                  onPress={submit}
                  disabled={!reason.trim() || isSubmitting}
                  style={{
                    flex: 1,
                    paddingVertical: 13,
                    borderRadius: 14,
                    backgroundColor: PASS_RED,
                    alignItems: 'center',
                    opacity: !reason.trim() || isSubmitting ? 0.4 : 1,
                  }}
                >
                  <Text style={{ fontSize: 15, fontWeight: '600', color: PAPER }}>
                    {isSubmitting ? 'Sending…' : 'Send'}
                  </Text>
                </Pressable>
              </View>
            </>
          )}
        </View>
      </ModalView>
    </Modal>
  );
}
