import { View, Text, SafeAreaView } from '@/lib/tw';
import { WingerActivityFeed } from '@/features/wingpeople/WingerActivityFeed';

function ActivityContent() {
  return (
    <>
      <View className="px-4 pt-2 pb-1">
        <Text className="font-serif text-fg" style={{ fontSize: 28, letterSpacing: -0.5 }}>
          Activity
        </Text>
      </View>
      <Text className="px-4 pb-3 text-sm text-fg-muted">Track your contributions.</Text>
      <WingerActivityFeed />
    </>
  );
}

export default function ActivityScreen() {
  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top']}>
      <ActivityContent />
    </SafeAreaView>
  );
}
