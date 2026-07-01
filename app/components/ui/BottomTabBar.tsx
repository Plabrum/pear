import type { BottomTabBarProps } from '@react-navigation/bottom-tabs';
import { BlurView } from 'expo-blur';
import { Platform, StyleSheet } from 'react-native';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Pressable, Text, View } from '@/lib/tw';
import { PearMark } from './PearMark';

type Role = 'dater' | 'winger';

type IconProps = { color: string; filled?: boolean };

const CardsIcon = ({ color }: IconProps) => (
  <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
    <Rect x="3" y="3" width="7" height="7" rx="1.5" stroke={color} strokeWidth={1.8} />
    <Rect x="14" y="3" width="7" height="7" rx="1.5" stroke={color} strokeWidth={1.8} />
    <Rect x="3" y="14" width="7" height="7" rx="1.5" stroke={color} strokeWidth={1.8} />
    <Rect x="14" y="14" width="7" height="7" rx="1.5" stroke={color} strokeWidth={1.8} />
  </Svg>
);

const HeartIcon = ({ color }: IconProps) => (
  <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
    <Path
      d="M20.84 4.6a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.07a5.5 5.5 0 0 0-7.78 7.78l1.06 1.07L12 21.23l7.78-7.78 1.06-1.07a5.5 5.5 0 0 0 0-7.78z"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const ChatIcon = ({ color }: IconProps) => (
  <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
    <Path
      d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z"
      stroke={color}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const UserIcon = ({ color }: IconProps) => (
  <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
    <Path
      d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"
      stroke={color}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Circle cx={12} cy={7} r={4} stroke={color} strokeWidth={1.8} />
  </Svg>
);

const SparkleIcon = ({ color }: IconProps) => (
  <Svg width={22} height={22} viewBox="0 0 24 24" fill={color}>
    <Path d="M12 2l1.7 5.3L19 9l-5.3 1.7L12 16l-1.7-5.3L5 9l5.3-1.7L12 2zM19 14l.8 2.5L22 17l-2.2.5L19 20l-.8-2.5L16 17l2.2-.5L19 14zM5 15l.6 2L7 17.5l-1.4.5L5 20l-.6-2L3 17.5 4.4 17 5 15z" />
  </Svg>
);

const PearIcon = ({ color, filled }: IconProps) =>
  filled ? (
    <PearMark size={22} color={color} variant="flat" />
  ) : (
    <PearMark size={22} color={color} variant="outline" />
  );

type TabDef = {
  /** The expo-router route name this tab maps to. */
  route: string;
  label: string;
  Icon: (p: IconProps) => React.ReactElement;
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
  { route: 'scout', label: 'Scout', Icon: CardsIcon },
  { route: 'activity', label: 'Activity', Icon: SparkleIcon },
  { route: 'me', label: 'Me', Icon: PearIcon, fillWhenActive: true },
];

const ACTIVE_COLOR = '#5A8C3A'; // --color-primary (leaf)
const INACTIVE_COLOR = '#8b8170'; // --color-foreground-subtle

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
          style={[StyleSheet.absoluteFillObject, { backgroundColor: 'rgba(251,248,241,0.7)' }]}
        />
      )}
      {Platform.OS !== 'ios' && (
        <View style={[StyleSheet.absoluteFillObject, { backgroundColor: '#fbf8f1' }]} />
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
