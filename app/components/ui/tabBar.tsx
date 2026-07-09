import { Platform, StyleSheet } from 'react-native';
import { BlurView } from '@react-native-community/blur';

import { colors } from '@/constants/theme';

// Shared tab-bar chrome for both role shells — (tabs) and (winger-tabs).
// Keeping this in one place prevents the two layouts from drifting.

const ACTIVE = colors.leaf;
const INACTIVE = colors.inkDim;

const tabBarBackground =
  Platform.OS === 'ios'
    ? () => (
        <BlurView
          blurAmount={40}
          blurType="light"
          style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(251,248,241,0.7)' }]}
        />
      )
    : undefined;

export const tabScreenOptions = {
  headerShown: false,
  tabBarActiveTintColor: ACTIVE,
  tabBarInactiveTintColor: INACTIVE,
  tabBarStyle: {
    backgroundColor: Platform.OS === 'ios' ? 'transparent' : colors.white,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.divider,
  },
  tabBarBackground,
  tabBarItemStyle: {
    paddingTop: 4,
    paddingBottom: 0,
  },
  tabBarLabelStyle: {
    fontFamily: 'Geist',
    fontSize: 10.5,
    letterSpacing: -0.1,
  },
} as const;
