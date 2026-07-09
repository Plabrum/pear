// Uses MaterialIcons on every platform (previously Android/web only; SF Symbols via
// expo-symbols were dropped in favor of a single uniform icon set on iOS too).

import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import { ComponentProps } from 'react';
import { OpaqueColorValue, type StyleProp, type TextStyle } from 'react-native';

type IconMapping = Record<string, ComponentProps<typeof MaterialIcons>['name']>;
type IconSymbolName = keyof typeof MAPPING;

/**
 * Add your SF Symbols to Material Icons mappings here.
 * - see Material Icons in the [Icons Directory](https://icons.expo.fyi).
 * - see SF Symbols in the [SF Symbols](https://developer.apple.com/sf-symbols/) app.
 */
const MAPPING = {
  'house.fill': 'home',
  'paperplane.fill': 'send',
  'chevron.left.forwardslash.chevron.right': 'code',
  'chevron.left': 'chevron-left',
  'chevron.right': 'chevron-right',
  // MaterialIcons has no true Apple logo; 'apple' is its closest brand-icon glyph.
  applelogo: 'apple',
  'envelope.fill': 'email',
} as IconMapping;

/**
 * An icon component that uses Material Icons on every platform, for a consistent
 * look and a single icon set to maintain. Icon `name`s follow SF Symbols naming
 * and require manual mapping to Material Icons.
 */
export function IconSymbol({
  name,
  size = 24,
  color,
  style,
}: {
  name: IconSymbolName;
  size?: number;
  color: string | OpaqueColorValue;
  style?: StyleProp<TextStyle>;
}) {
  return <MaterialIcons color={color} size={size} name={MAPPING[name]} style={style} />;
}
