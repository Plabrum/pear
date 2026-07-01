import { useState } from 'react';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Text, View } from '@/lib/tw';
import { gradientFor } from './GradientBlock';

type Props = {
  name: string;
  size?: number;
  photoUri?: string | null;
  /** Width in px of a leaf-coloured ring around the avatar. */
  ring?: number;
};

const RING_COLOR = '#5A8C3A';

export function FaceAvatar({ name, size = 40, photoUri, ring }: Props) {
  const [failedUri, setFailedUri] = useState<string | null>(null);
  const ringStyle = ring ? { borderWidth: ring, borderColor: RING_COLOR } : undefined;

  if (photoUri && photoUri !== failedUri) {
    return (
      <Image
        source={{ uri: photoUri }}
        style={[{ width: size, height: size, borderRadius: size / 2 }, ringStyle]}
        contentFit="cover"
        onError={() => setFailedUri(photoUri)}
      />
    );
  }

  const [c1, c2] = gradientFor(name);
  const initial = String(name).trim().charAt(0).toUpperCase() || 'A';
  const fontSize = Math.round(size * 0.42);

  return (
    <View
      className="items-center justify-center overflow-hidden"
      style={[{ width: size, height: size, borderRadius: size / 2 }, ringStyle]}
    >
      <LinearGradient
        colors={[c1, c2]}
        start={{ x: 0.15, y: 0 }}
        end={{ x: 0.85, y: 1 }}
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
      />
      <Text
        className="font-serif text-white"
        style={{
          fontSize,
          lineHeight: fontSize * 1.2,
          letterSpacing: -0.5,
          includeFontPadding: false,
        }}
      >
        {initial}
      </Text>
    </View>
  );
}
