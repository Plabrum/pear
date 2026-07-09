import Ionicons from 'react-native-vector-icons/Ionicons';

import { View, Text, Pressable } from '@/lib/tw';
import { colors } from '@/constants/theme';

type PromptCardProps = {
  question: string | null;
  answer: string;
  sent: boolean;
  onOpen: () => void;
};

export function PromptCard({ question, answer, sent, onOpen }: PromptCardProps) {
  return (
    <View
      style={{
        backgroundColor: colors.white,
        borderWidth: 1,
        borderColor: colors.divider,
        borderRadius: 18,
        padding: 14,
      }}
    >
      {question != null && (
        <Text
          style={{
            color: colors.inkDim,
            fontSize: 10.5,
            textTransform: 'uppercase',
            letterSpacing: 1.4,
            marginBottom: 4,
            fontWeight: '700',
          }}
        >
          {question}
        </Text>
      )}
      <Text
        style={{
          color: colors.ink,
          fontFamily: 'DMSerifDisplay',
          fontSize: 19,
          lineHeight: 24,
          letterSpacing: -0.3,
        }}
      >
        “{answer}”
      </Text>

      <View style={{ marginTop: 10 }}>
        {sent ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="checkmark" size={14} color={colors.leaf} />
            <Text style={{ color: colors.primary, fontSize: 12.5, fontWeight: '600' }}>
              Reply sent
            </Text>
          </View>
        ) : (
          <Pressable onPress={onOpen} hitSlop={6}>
            <Text style={{ color: colors.primary, fontSize: 13, fontWeight: '600' }}>
              Reply to this prompt →
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}
