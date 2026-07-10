import { useState } from 'react';
import { Image, StyleSheet } from 'react-native';
import type { ImageProps, ImageResizeMode, ImageStyle, StyleProp } from 'react-native';
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';

type Props = {
  uri: string;
  style?: StyleProp<ImageStyle>;
  resizeMode?: ImageResizeMode;
  blurRadius?: number;
  /** Crossfade duration in ms. Matches expo-image's default `transition` feel. */
  duration?: number;
  onError?: ImageProps['onError'];
};

/**
 * Hand-rolled replacement for expo-image's `transition` (crossfade-on-load).
 * Stacks the previous source (still visible) under the incoming one, then
 * fades the incoming source in once its `onLoad` fires. The incoming image is
 * keyed by its own uri so a source change always mounts a fresh fade-in
 * animation instead of imperatively resetting shared state during render.
 */
export function CrossfadeImage({
  uri,
  style,
  resizeMode = 'cover',
  blurRadius,
  duration = 200,
  onError,
}: Props) {
  const [prevUri, setPrevUri] = useState<string | null>(null);
  const [currentUri, setCurrentUri] = useState(uri);

  if (uri !== currentUri) {
    // Source changed mid-lifetime: keep the old one visible underneath while
    // the new one loads and fades in. (Render-phase state derivation is an
    // accepted React pattern for "reset state when a prop changes".)
    setPrevUri(currentUri);
    setCurrentUri(uri);
  }

  return (
    <>
      {prevUri ? (
        <Image
          source={{ uri: prevUri }}
          style={[StyleSheet.absoluteFill, style]}
          resizeMode={resizeMode}
          blurRadius={blurRadius}
        />
      ) : null}
      <FadeInImage
        key={currentUri}
        uri={currentUri}
        style={style}
        resizeMode={resizeMode}
        blurRadius={blurRadius}
        duration={duration}
        onError={onError}
        onFadeComplete={() => setPrevUri(null)}
      />
    </>
  );
}

function FadeInImage({
  uri,
  style,
  resizeMode,
  blurRadius,
  duration,
  onError,
  onFadeComplete,
}: {
  uri: string;
  style?: StyleProp<ImageStyle>;
  resizeMode?: ImageResizeMode;
  blurRadius?: number;
  duration: number;
  onError?: ImageProps['onError'];
  onFadeComplete: () => void;
}) {
  const opacity = useSharedValue(0);
  const animatedStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));

  function handleLoad() {
    // reanimated shared values are mutated through `.value` by design; the
    // React Compiler immutability rule can't model this and false-positives.
    // eslint-disable-next-line react-hooks/immutability
    opacity.value = withTiming(1, { duration }, (finished) => {
      if (finished) runOnJS(onFadeComplete)();
    });
  }

  return (
    <Animated.Image
      source={{ uri }}
      style={[StyleSheet.absoluteFill, style, animatedStyle]}
      resizeMode={resizeMode}
      blurRadius={blurRadius}
      onLoad={handleLoad}
      onError={onError}
    />
  );
}
