import { View, Text } from '@/lib/tw';

type Props = {
  title: string;
  right?: React.ReactNode;
};

export function LargeHeader({ title, right }: Props) {
  return (
    <View className="flex-row items-center justify-between px-5 pt-2 pb-3">
      <Text className="text-4xl font-bold text-fg font-serif">{title}</Text>
      {right != null && <View>{right}</View>}
    </View>
  );
}
