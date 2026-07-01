import { View, Text } from '@/lib/tw';
import { PearMark } from '@/components/ui/PearMark';
import PulseSpinner from '@/components/ui/PulseSpinner';

const LEAF = '#5A8C3A';

interface Props {
  variant?: 'branded' | 'spinner';
}

export default function Splash({ variant = 'branded' }: Props) {
  return (
    <View className="absolute inset-0 bg-background">
      {variant === 'branded' && (
        <>
          <View className="absolute" style={{ top: 80, left: -30, opacity: 0.1 }}>
            <View style={{ transform: [{ rotate: '-12deg' }] }}>
              <PearMark size={240} color={LEAF} />
            </View>
          </View>
          <View className="absolute" style={{ bottom: 120, right: -40, opacity: 0.07 }}>
            <View style={{ transform: [{ rotate: '20deg' }] }}>
              <PearMark size={300} color={LEAF} />
            </View>
          </View>
          <View className="absolute" style={{ top: 320, right: 30, opacity: 0.08 }}>
            <PearMark size={80} color={LEAF} />
          </View>

          <View className="flex-1 items-center justify-center px-8">
            <PearMark size={108} />
            <View className="items-center mt-6">
              <Text
                className="text-foreground"
                style={{
                  fontFamily: 'DMSerifDisplay',
                  fontSize: 64,
                  lineHeight: 64,
                  letterSpacing: -2,
                }}
              >
                Pear
              </Text>
              <Text
                className="text-foreground-muted mt-2"
                style={{
                  fontFamily: 'DMSerifDisplay',
                  fontStyle: 'italic',
                  fontSize: 18,
                  letterSpacing: -0.2,
                }}
              >
                dating, with a second opinion
              </Text>
            </View>
          </View>

          <View className="absolute left-0 right-0" style={{ bottom: 56 }}>
            <Text
              className="text-foreground-subtle text-center"
              style={{ fontSize: 10.5, letterSpacing: 2.4 }}
            >
              A GARDEN, EST. 2026
            </Text>
          </View>
        </>
      )}

      <View className="absolute left-0 right-0" style={{ bottom: 110 }}>
        <PulseSpinner color={LEAF} />
      </View>
    </View>
  );
}
