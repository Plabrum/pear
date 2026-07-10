import { StyleSheet } from 'react-native';
import { View, Text, Pressable, ScrollView } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { colors } from '@/constants/theme';

type Props = {
  tabs: string[];
  active: number;
  setActive: (i: number) => void;
  badges?: Record<number, number>;
};

export function TextTabBar({ tabs, active, setActive, badges }: Props) {
  return (
    <View
      style={{ borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.divider }}
    >
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerClassName="px-5 flex-row gap-7"
      >
        {tabs.map((tab, i) => {
          const badgeCount = badges?.[i] ?? 0;
          return (
            <Pressable key={tab} onPress={() => setActive(i)} className="pb-2.5 pt-1 items-center">
              <View className="flex-row items-center gap-1.5">
                <Text
                  className={cn(
                    'text-sm font-medium text-fg-muted',
                    i === active && 'text-fg font-semibold'
                  )}
                >
                  {tab}
                </Text>
                {badgeCount > 0 && (
                  <View className="bg-accent rounded-lg min-w-[18px] h-[18px] justify-center items-center px-1">
                    <Text className="text-white text-xs font-bold leading-[13px]">
                      {badgeCount}
                    </Text>
                  </View>
                )}
              </View>
              {i === active && (
                <View className="h-0.5 bg-primary rounded-[1px] absolute bottom-0 left-0 right-0" />
              )}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
