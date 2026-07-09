import { View, StyleSheet } from 'react-native';
import { CrossfadeImage } from './CrossfadeImage';

type Props = {
  uri: string | null;
  ratio?: number;
  blur?: boolean;
  style?: object;
};

export function PhotoRect({ uri, ratio = 4 / 5, blur = false, style }: Props) {
  return (
    <View style={[styles.container, { aspectRatio: ratio }, style]}>
      {uri ? (
        <CrossfadeImage
          uri={uri}
          style={StyleSheet.absoluteFill}
          resizeMode="cover"
          blurRadius={blur ? 20 : 0}
        />
      ) : (
        <View style={[StyleSheet.absoluteFill, styles.placeholder]} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#f1f0ee',
    overflow: 'hidden',
    borderRadius: 12,
  },
  placeholder: {
    backgroundColor: '#ebebf0',
  },
});
