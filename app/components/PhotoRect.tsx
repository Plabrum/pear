import { StyleSheet } from 'react-native';
import { View } from '@/lib/tw';
import { CrossfadeImage } from './CrossfadeImage';

type Props = {
  uri: string | null;
  ratio?: number;
  blur?: boolean;
  style?: object;
};

export function PhotoRect({ uri, ratio = 4 / 5, blur = false, style }: Props) {
  return (
    <View
      className="bg-skeleton-base overflow-hidden rounded-[12px]"
      style={[{ aspectRatio: ratio }, style]}
    >
      {uri ? (
        <CrossfadeImage
          uri={uri}
          style={StyleSheet.absoluteFill}
          resizeMode="cover"
          blurRadius={blur ? 20 : 0}
        />
      ) : (
        <View className="absolute inset-0 bg-skeleton-highlight" />
      )}
    </View>
  );
}
