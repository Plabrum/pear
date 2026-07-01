import { useEffect } from 'react';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withSequence,
  withTiming,
  withDelay,
} from 'react-native-reanimated';
import { View } from '@/lib/tw';
import { colors } from '@/constants/theme';

function PulseDot({ delay, color }: { delay: number; color: string }) {
  const opacity = useSharedValue(0.25);

  useEffect(() => {
    opacity.value = withDelay(
      delay,
      withRepeat(
        withSequence(withTiming(0.95, { duration: 600 }), withTiming(0.25, { duration: 600 })),
        -1,
        false
      )
    );
  }, [delay, opacity]);

  const style = useAnimatedStyle(() => ({ opacity: opacity.value }));

  return (
    <Animated.View
      style={[
        { width: 8, height: 8, borderRadius: 5, backgroundColor: color, marginHorizontal: 4 },
        style,
      ]}
    />
  );
}

interface Props {
  color?: string;
}

export default function PulseSpinner({ color = colors.primary }: Props) {
  return (
    <View className="flex-row items-center justify-center">
      <PulseDot delay={0} color={color} />
      <PulseDot delay={180} color={color} />
      <PulseDot delay={360} color={color} />
    </View>
  );
}
