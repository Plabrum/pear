import { useState } from 'react';
import {
  Alert,
  Dimensions,
  NativeScrollEvent,
  NativeSyntheticEvent,
  StyleSheet,
} from 'react-native';
import { toast } from 'sonner-native';
import type { UseFormReturn } from 'react-hook-form';
import { Ionicons } from '@expo/vector-icons';

import type { OwnDatingProfileResponse, OwnPromptResponse } from '@/lib/api/generated/model';
import {
  deleteApiProfilePromptsId,
  deleteApiPromptResponsesId,
  postApiPromptResponsesIdApprove,
} from '@/lib/api/generated/prompts/prompts';

import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { ScrollView, Text, View, Pressable } from '@/lib/tw';
import { Sprout } from '@/components/ui/Sprout';
import { AddPromptModal } from './AddPromptModal';

const LINE = 'rgba(31,27,22,0.10)';
const LEAF = '#5A8C3A';

// screen width minus paddings: outer padding 16 + inner card padding 14
const SLIDE_WIDTH = Dimensions.get('window').width - 16 * 2 - 14 * 2;
const PEEK = 20;
const SNAP_INTERVAL = SLIDE_WIDTH - PEEK + 8;

type ApprovedResponse = OwnPromptResponse;

function FieldLabel({ children }: { children: string }) {
  return (
    <Text
      className="text-ink-dim"
      style={{
        fontSize: 10.5,
        letterSpacing: 1.4,
        textTransform: 'uppercase',
        fontWeight: '600',
        marginBottom: 6,
      }}
    >
      {children}
    </Text>
  );
}

function ApprovedResponsesCarousel({ responses }: { responses: ApprovedResponse[] }) {
  const [activeIdx, setActiveIdx] = useState(0);

  const handleScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    setActiveIdx(Math.round(e.nativeEvent.contentOffset.x / SNAP_INTERVAL));
  };

  return (
    <View
      style={{
        marginTop: 12,
        paddingTop: 12,
        borderTopWidth: StyleSheet.hairlineWidth,
        borderTopColor: LINE,
      }}
    >
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        decelerationRate="fast"
        snapToInterval={SNAP_INTERVAL}
        onMomentumScrollEnd={handleScroll}
        contentContainerStyle={{ paddingRight: PEEK }}
      >
        {responses.map((r, i) => (
          <View
            key={r.id}
            style={{
              width: SLIDE_WIDTH - PEEK,
              marginRight: i < responses.length - 1 ? 8 : 0,
              flexDirection: 'row',
              gap: 10,
            }}
          >
            <FaceAvatar
              name={r.author?.chosenName ?? ''}
              size={26}
              photoUri={r.author?.avatarUrl ?? null}
            />
            <View style={{ flex: 1 }}>
              <Text
                className="text-ink-dim"
                style={{ fontSize: 11.5, fontWeight: '600', marginBottom: 2 }}
              >
                {r.author?.chosenName ?? 'Wingperson'}
              </Text>
              <Text className="text-ink-mid" style={{ fontSize: 14, lineHeight: 20 }}>
                {r.message}
              </Text>
            </View>
          </View>
        ))}
      </ScrollView>
      {responses.length > 1 ? (
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'center',
            gap: 6,
            marginTop: 10,
          }}
        >
          {responses.map((_, i) => (
            <View
              key={i}
              style={{
                width: i === activeIdx ? 14 : 6,
                height: 6,
                borderRadius: 3,
                backgroundColor: i === activeIdx ? LEAF : 'rgba(31,27,22,0.20)',
              }}
            />
          ))}
        </View>
      ) : null}
    </View>
  );
}

interface Props {
  form: UseFormReturn<NonNullable<OwnDatingProfileResponse>>;
  onRefresh: () => void;
}

export function PromptsTab({ form, onRefresh }: Props) {
  const [modalVisible, setModalVisible] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const prompts = form.watch('prompts');
  const usedTemplateIds = new Set(prompts.map((p) => p.template.id));

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const handleApproveResponse = async (promptId: string, responseId: string) => {
    const prev = prompts;
    form.setValue(
      'prompts',
      prompts.map((p) =>
        p.id === promptId
          ? {
              ...p,
              responses: p.responses.map((r) =>
                r.id === responseId ? { ...r, isApproved: true } : r
              ),
            }
          : p
      )
    );
    try {
      await postApiPromptResponsesIdApprove(responseId);
    } catch {
      form.setValue('prompts', prev);
      toast.error('Could not approve comment.');
    }
  };

  const handleRejectResponse = async (promptId: string, responseId: string) => {
    const prev = prompts;
    form.setValue(
      'prompts',
      prompts.map((p) =>
        p.id === promptId ? { ...p, responses: p.responses.filter((r) => r.id !== responseId) } : p
      )
    );
    try {
      await deleteApiPromptResponsesId(responseId);
    } catch {
      form.setValue('prompts', prev);
      toast.error('Could not reject comment.');
    }
  };

  const handleDeletePrompt = async (promptId: string) => {
    const prev = prompts;
    form.setValue(
      'prompts',
      prompts.filter((p) => p.id !== promptId)
    );
    try {
      await deleteApiProfilePromptsId(promptId);
    } catch {
      form.setValue('prompts', prev);
      toast.error('Could not remove prompt.');
    }
  };

  return (
    <ScrollView
      contentContainerStyle={{ padding: 16, paddingBottom: 48, gap: 10 }}
      showsVerticalScrollIndicator={false}
    >
      {prompts.length === 0 ? (
        <View
          className="bg-surface"
          style={{
            borderRadius: 18,
            borderWidth: 1,
            borderColor: LINE,
            padding: 24,
            alignItems: 'center',
          }}
        >
          <Text className="text-ink" style={{ fontSize: 14, fontWeight: '600' }}>
            No prompts yet.
          </Text>
          <Text
            className="text-ink-dim"
            style={{ fontSize: 13, marginTop: 6, textAlign: 'center' }}
          >
            Add one to give people something to connect with.
          </Text>
        </View>
      ) : null}

      {prompts.map((prompt) => {
        const pendingR = prompt.responses.filter((r) => !r.isApproved);
        const approvedR = prompt.responses.filter((r) => r.isApproved);
        const isExpanded = expanded.has(prompt.id);

        return (
          <View
            key={prompt.id}
            className="bg-surface"
            style={{
              borderRadius: 18,
              borderWidth: 1,
              borderColor: LINE,
              padding: 14,
            }}
          >
            <FieldLabel>{prompt.template.question}</FieldLabel>
            <Text
              className="font-serif text-ink"
              style={{
                fontSize: 18,
                lineHeight: 24,
                fontStyle: 'italic',
              }}
            >
              {prompt.answer}
            </Text>

            {approvedR.length > 0 ? <ApprovedResponsesCarousel responses={approvedR} /> : null}

            {pendingR.length > 0 ? (
              <>
                <Pressable
                  onPress={() => toggle(prompt.id)}
                  className="flex-row items-center"
                  style={{
                    gap: 6,
                    marginTop: 12,
                    paddingTop: 12,
                    borderTopWidth: StyleSheet.hairlineWidth,
                    borderTopColor: LINE,
                  }}
                >
                  <Text
                    className="text-primary"
                    style={{ flex: 1, fontSize: 13, fontWeight: '600' }}
                  >
                    {pendingR.length} wingperson comment{pendingR.length > 1 ? 's' : ''} waiting
                  </Text>
                  <Ionicons
                    name={isExpanded ? 'chevron-up' : 'chevron-down'}
                    size={12}
                    color={LEAF}
                  />
                </Pressable>
                {isExpanded
                  ? pendingR.map((r) => (
                      <View key={r.id} style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                        <FaceAvatar
                          name={r.author?.chosenName ?? ''}
                          size={26}
                          photoUri={r.author?.avatarUrl ?? null}
                        />
                        <View style={{ flex: 1 }}>
                          <Text className="text-ink-mid" style={{ fontSize: 14, lineHeight: 20 }}>
                            {r.message}
                          </Text>
                          <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                            <Sprout
                              size="sm"
                              onPress={() => handleApproveResponse(prompt.id, r.id)}
                            >
                              Approve
                            </Sprout>
                            <Sprout
                              size="sm"
                              variant="secondary"
                              onPress={() => handleRejectResponse(prompt.id, r.id)}
                            >
                              Reject
                            </Sprout>
                          </View>
                        </View>
                      </View>
                    ))
                  : null}
              </>
            ) : null}

            <Pressable
              onPress={() =>
                Alert.alert('Remove prompt?', 'This cannot be undone.', [
                  { text: 'Cancel', style: 'cancel' },
                  {
                    text: 'Remove',
                    style: 'destructive',
                    onPress: () => handleDeletePrompt(prompt.id),
                  },
                ])
              }
              style={{
                marginTop: 12,
                paddingTop: 12,
                borderTopWidth: StyleSheet.hairlineWidth,
                borderTopColor: LINE,
              }}
            >
              <Text className="text-destructive" style={{ fontSize: 13, fontWeight: '500' }}>
                Remove prompt
              </Text>
            </Pressable>
          </View>
        );
      })}

      <Pressable
        onPress={() => setModalVisible(true)}
        className="flex-row items-center justify-center"
        style={{
          gap: 8,
          paddingVertical: 14,
          borderRadius: 18,
          borderWidth: 1.5,
          borderStyle: 'dashed',
          borderColor: LEAF,
          minHeight: 52,
          marginTop: 4,
        }}
      >
        <Ionicons name="add" size={18} color={LEAF} />
        <Text className="text-primary" style={{ fontSize: 14, fontWeight: '600' }}>
          Add prompt
        </Text>
      </Pressable>

      <AddPromptModal
        visible={modalVisible}
        onClose={() => setModalVisible(false)}
        usedTemplateIds={usedTemplateIds}
        onAdded={onRefresh}
      />
    </ScrollView>
  );
}
