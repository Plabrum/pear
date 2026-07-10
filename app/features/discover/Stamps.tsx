import Animated, {
  Extrapolation,
  interpolate,
  useAnimatedStyle,
  type SharedValue,
} from 'react-native-reanimated';

import { Text } from '@/lib/tw';
import { colors } from '@/constants/theme';
import { SWIPE_THRESHOLD } from './constants';

export function PassStamp({ swipeX }: { swipeX: SharedValue<number> }) {
  const style = useAnimatedStyle(() => ({
    opacity: interpolate(swipeX.value, [-SWIPE_THRESHOLD, -20, 0], [1, 0, 0], Extrapolation.CLAMP),
  }));
  return (
    <Animated.View
      style={[
        {
          position: 'absolute',
          top: 24,
          right: 18,
          transform: [{ rotate: '14deg' }],
          borderWidth: 3,
          borderColor: colors.passRed,
          paddingVertical: 4,
          paddingHorizontal: 12,
          borderRadius: 8,
          backgroundColor: colors.overlayWhite85,
        },
        style,
      ]}
    >
      <Text className="text-pass-red" style={{ fontSize: 18, fontWeight: '700', letterSpacing: 2 }}>
        PASS
      </Text>
    </Animated.View>
  );
}

export function LikeStamp({ swipeX }: { swipeX: SharedValue<number> }) {
  const style = useAnimatedStyle(() => ({
    opacity: interpolate(swipeX.value, [0, 20, SWIPE_THRESHOLD], [0, 0, 1], Extrapolation.CLAMP),
  }));
  return (
    <Animated.View
      style={[
        {
          position: 'absolute',
          top: 24,
          left: 18,
          transform: [{ rotate: '-14deg' }],
          borderWidth: 3,
          borderColor: colors.leaf,
          paddingVertical: 4,
          paddingHorizontal: 12,
          borderRadius: 8,
          backgroundColor: colors.overlayWhite85,
        },
        style,
      ]}
    >
      <Text className="text-leaf" style={{ fontSize: 18, fontWeight: '700', letterSpacing: 2 }}>
        LIKE
      </Text>
    </Animated.View>
  );
}
