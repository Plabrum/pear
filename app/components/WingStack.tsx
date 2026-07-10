import { Text as RNText } from 'react-native';
import { View } from '@/lib/tw';
import { colors } from '@/constants/theme';
import { FaceAvatar } from './FaceAvatar';

export type WingStackItem = {
  name: string;
  photoUri?: string | null;
};

type Props = {
  items: WingStackItem[];
  size?: number;
  max?: number;
  label?: string;
};

export function WingStack({ items, size = 28, max = 3, label }: Props) {
  if (items.length === 0) return null;
  const shown = items.slice(0, max);
  const extra = items.length - shown.length;
  const overlap = Math.round(size * 0.32);

  return (
    <View className="flex-row items-center">
      <View className="flex-row">
        {shown.map((item, i) => (
          <View key={i} style={{ marginLeft: i === 0 ? 0 : -overlap, zIndex: i }}>
            <FaceAvatar name={item.name} size={size} photoUri={item.photoUri} ring={2} />
          </View>
        ))}
        {extra > 0 ? (
          <View
            style={{
              marginLeft: -overlap,
              width: size,
              height: size,
              borderRadius: size / 2,
              zIndex: shown.length,
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: colors.muted,
            }}
          >
            <RNText
              style={{
                fontSize: Math.round(size * 0.36),
                fontWeight: '600',
                color: colors.inkMid,
              }}
            >
              +{extra}
            </RNText>
          </View>
        ) : null}
      </View>
      {label ? (
        <RNText style={{ marginLeft: 8, fontSize: 12.5, fontWeight: '500', color: colors.inkDim }}>
          {label}
        </RNText>
      ) : null}
    </View>
  );
}
