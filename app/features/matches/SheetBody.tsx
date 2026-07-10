import { useState } from 'react';

import { View, Text } from '@/lib/tw';
import { colors } from '@/constants/theme';
import {
  useGetApiMatchesMatchIdSheetSuspense,
  getGetApiMatchesMatchIdSheetQueryKey,
} from '@/lib/api/generated/matches/matches';
import type { MatchSummary } from '@/lib/api/generated/model';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import { useActionFormRenderer } from '@/hooks/actions/use-action-form-renderer';
import type { ActionDTO } from '@/lib/actions/types';
import { FaceAvatar } from '@/components/FaceAvatar';
import { ReplyPromptCard } from './PromptCard';

// The matched person's reply to a prompt — a top-level create on prompt_response_actions.
const ADD_RESPONSE: ActionDTO = {
  action: 'prompt_response_actions__create',
  label: 'Reply',
  action_group_type: 'prompt_response_actions',
};

export function SheetBody({ match }: { match: MatchSummary }) {
  const { data } = useGetApiMatchesMatchIdSheetSuspense(match.matchId);
  const { wingNote, prompts } = data;
  const [sentPrompts, setSentPrompts] = useState<ReadonlySet<string>>(() => new Set());
  const [respondingTo, setRespondingTo] = useState<{ id: string; question: string | null } | null>(
    null
  );

  // The prompt-response create tags (/prompt-responses, /profile-prompts) don't
  // cover this match's sheet, so refresh it explicitly via onInvalidate.
  const executor = useActionExecutor({
    actionGroup: 'prompt_response_actions',
    onInvalidate: (qc) => {
      void qc.invalidateQueries({ queryKey: getGetApiMatchesMatchIdSheetQueryKey(match.matchId) });
    },
  });
  // The prompt-response form is pulled from the action registry; objectData is the prompt.
  const renderResponseForm = useActionFormRenderer(respondingTo ?? undefined);

  return (
    <View style={{ paddingHorizontal: 20, gap: 16, paddingTop: 16 }}>
      {wingNote != null && (
        <View
          style={{
            backgroundColor: colors.leafSoft,
            borderRadius: 16,
            padding: 14,
            flexDirection: 'row',
            gap: 10,
            alignItems: 'flex-start',
          }}
        >
          <FaceAvatar name={wingNote.winger?.chosenName ?? 'Wing'} size={28} />
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text
              style={{
                color: colors.primary,
                fontSize: 11,
                fontWeight: '700',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
              }}
            >
              {wingNote.winger?.chosenName ?? 'Your wing'} says
            </Text>
            <Text style={{ color: colors.ink, fontSize: 13, lineHeight: 18, marginTop: 2 }}>
              “{wingNote.note}”
            </Text>
          </View>
        </View>
      )}

      {prompts.map((prompt) => (
        <ReplyPromptCard
          key={prompt.id}
          question={prompt.template?.question ?? null}
          answer={prompt.answer}
          sent={sentPrompts.has(prompt.id)}
          onOpen={() =>
            setRespondingTo({ id: prompt.id, question: prompt.template?.question ?? null })
          }
        />
      ))}

      {respondingTo &&
        renderResponseForm({
          action: ADD_RESPONSE,
          onSubmit: (body) => {
            const promptId = respondingTo.id;
            // silent: the optimistic "Reply sent" tag is our feedback; executor still
            // invalidates the sheet + error-toasts.
            void executor
              .executeAction(ADD_RESPONSE, body, { silent: true })
              .then(() => setSentPrompts((prev) => new Set(prev).add(promptId)))
              .catch(() => {});
            setRespondingTo(null);
          },
          onClose: () => setRespondingTo(null),
          isSubmitting: executor.isExecuting,
          isOpen: true,
          actionLabel: ADD_RESPONSE.label,
        })}
    </View>
  );
}
