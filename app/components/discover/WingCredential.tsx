import { Text, View } from '@/lib/tw';
import { WingStack } from '@/components/ui/WingStack';

export function WingCredential({
  suggesterName,
  note,
}: {
  suggesterName: string;
  note: string | null;
}) {
  return (
    <View
      className="bg-leaf-soft flex-row gap-3 items-start"
      style={{
        borderWidth: 1,
        borderColor: 'rgba(90,140,58,0.15)',
        borderRadius: 14,
        padding: 12,
      }}
    >
      <WingStack items={[{ name: suggesterName }]} size={30} />
      <View className="flex-1 min-w-0">
        <Text
          className="text-primary"
          style={{
            fontSize: 10.5,
            fontWeight: '700',
            letterSpacing: 1.2,
            textTransform: 'uppercase',
            marginBottom: 3,
          }}
        >
          Hand-picked
        </Text>
        {note != null ? (
          <Text className="text-ink" style={{ fontSize: 13, lineHeight: 18 }}>
            “{note}”{' '}
            <Text className="text-ink-dim" style={{ fontStyle: 'italic' }}>
              — {suggesterName}
            </Text>
          </Text>
        ) : (
          <Text className="text-ink" style={{ fontSize: 13, lineHeight: 18 }}>
            <Text style={{ fontWeight: '700' }}>Hand-picked</Text> by {suggesterName}
          </Text>
        )}
      </View>
    </View>
  );
}
