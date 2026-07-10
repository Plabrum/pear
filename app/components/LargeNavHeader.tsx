import type { ReactNode } from 'react';
import Ionicons from 'react-native-vector-icons/Ionicons';
import { View, Text, Pressable } from '@/lib/tw';
import { colors } from '@/constants/theme';

type Props = {
  back: boolean;
  onBack: () => void;
  title: ReactNode;
  right?: ReactNode;
};

export function LargeNavHeader({ back, onBack, title, right }: Props) {
  return (
    <View
      className="flex-row items-center"
      style={{ paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, gap: 4 }}
    >
      {back ? (
        <Pressable onPress={onBack} hitSlop={12} style={{ padding: 8, marginLeft: -4 }}>
          <Ionicons name="chevron-back" size={22} color={colors.ink} />
        </Pressable>
      ) : null}
      <Text className="font-serif text-fg" style={{ fontSize: 26, letterSpacing: -0.4, flex: 1 }}>
        {title}
      </Text>
      {right ?? null}
    </View>
  );
}
