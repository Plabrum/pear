import type { BottomTabBarProps } from 'expo-router/js-tabs';
import { BlurView } from 'expo-blur';
import { Platform, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/constants/theme';
import { Pressable, Text, View } from '@/lib/tw';
import {
  CardsIcon,
  ChatIcon,
  HeartIcon,
  PearIcon,
  SparkleIcon,
  UserIcon,
  type IconProps,
} from '@/components/ui/icons';

type Role = 'dater' | 'winger';

type TabDef = {
  /** The expo-router route name this tab maps to. */
  route: string;
  label: string;
  Icon: (p: IconProps & { filled?: boolean }) => React.ReactElement;
  /** When active, render the icon as filled (used for the Pear logo). */
  fillWhenActive?: boolean;
};

const DATER_TABS: TabDef[] = [
  { route: 'discover', label: 'Discover', Icon: CardsIcon },
  { route: 'matches', label: 'Matches', Icon: HeartIcon },
  { route: 'messages', label: 'Messages', Icon: ChatIcon },
  { route: 'profile', label: 'Profile', Icon: PearIcon, fillWhenActive: true },
];

// Phase E will wire winger-specific routes; this set is here so callers can
// pass `role="winger"` once those routes exist. Today only the dater set
// renders against real screens.
const WINGER_TABS: TabDef[] = [
  { route: 'friends', label: 'Friends', Icon: UserIcon },
  { route: 'activity', label: 'Activity', Icon: SparkleIcon },
  { route: 'me', label: 'Me', Icon: PearIcon, fillWhenActive: true },
];

const ACTIVE_COLOR = colors.leaf; // --color-leaf
const INACTIVE_COLOR = colors.inkDim; // --color-foreground-subtle

type Props = BottomTabBarProps & { role?: Role };

export function BottomTabBar({ state, descriptors, navigation, role = 'dater' }: Props) {
  const insets = useSafeAreaInsets();
  const tabs = role === 'winger' ? WINGER_TABS : DATER_TABS;
  const activeRouteName = state.routes[state.index]?.name;

  return (
    <View
      className="absolute bottom-0 left-0 right-0 border-t border-border"
      style={{ paddingBottom: Math.max(insets.bottom, 8), paddingTop: 6 }}
    >
      {Platform.OS === 'ios' && (
        <BlurView
          intensity={40}
          tint="light"
          style={[StyleSheet.absoluteFill, { backgroundColor: 'rgba(251,248,241,0.7)' }]}
        />
      )}
      {Platform.OS !== 'ios' && (
        <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.white }]} />
      )}
      <View className="flex-row justify-around">
        {tabs.map((tab) => {
          const route = state.routes.find((r) => r.name === tab.route);
          if (!route) return null;
          const descriptor = descriptors[route.key];

          const isActive = activeRouteName === tab.route;
          const color = isActive ? ACTIVE_COLOR : INACTIVE_COLOR;
          const onPress = () => {
            const event = navigation.emit({
              type: 'tabPress',
              target: route.key,
              canPreventDefault: true,
            });
            if (!isActive && !event.defaultPrevented) {
              navigation.navigate(route.name, route.params);
            }
          };

          return (
            <Pressable
              key={route.key}
              accessibilityRole="button"
              accessibilityState={isActive ? { selected: true } : {}}
              accessibilityLabel={descriptor.options.tabBarAccessibilityLabel ?? tab.label}
              onPress={onPress}
              className="items-center px-3.5 py-1.5"
              style={{ gap: 3 }}
            >
              <tab.Icon color={color} filled={isActive && tab.fillWhenActive} />
              <Text
                className="font-sans"
                style={{
                  color,
                  fontSize: 10.5,
                  fontWeight: isActive ? '600' : '500',
                  letterSpacing: -0.1,
                }}
              >
                {tab.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
