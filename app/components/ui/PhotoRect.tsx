import { View, StyleSheet } from 'react-native';
import { Image } from 'expo-image';

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
        <Image
          source={{ uri }}
          style={StyleSheet.absoluteFillObject}
          contentFit="cover"
          blurRadius={blur ? 20 : 0}
          transition={200}
        />
      ) : (
        <View style={[StyleSheet.absoluteFillObject, styles.placeholder]} />
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
