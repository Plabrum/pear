import { Tabs } from 'expo-router';
import { Platform, StyleSheet } from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';

import { PearMark } from '@/components/ui/PearMark';

const ACTIVE = '#5A8C3A';
const INACTIVE = '#8b8170';

const tabBarBackground =
  Platform.OS === 'ios'
    ? () => (
        <BlurView
          intensity={40}
          tint="light"
          style={[StyleSheet.absoluteFillObject, { backgroundColor: 'rgba(251,248,241,0.7)' }]}
        />
      )
    : undefined;

const sharedScreenOptions = {
  headerShown: false,
  tabBarActiveTintColor: ACTIVE,
  tabBarInactiveTintColor: INACTIVE,
  tabBarStyle: {
    backgroundColor: Platform.OS === 'ios' ? 'transparent' : '#fbf8f1',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(31,27,22,0.10)',
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

export default function WingerTabLayout() {
  return (
    <Tabs screenOptions={sharedScreenOptions}>
      <Tabs.Screen
        name="friends"
        options={{
          title: 'Friends',
          tabBarIcon: ({ color }) => <Ionicons name="people-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="scout"
        options={{
          title: 'Scout',
          tabBarIcon: ({ color }) => <Ionicons name="albums-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="activity"
        options={{
          title: 'Activity',
          tabBarIcon: ({ color }) => <Ionicons name="sparkles" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="me"
        options={{
          title: 'Me',
          tabBarIcon: ({ color, focused }) => (
            <PearMark size={22} color={color} variant={focused ? 'flat' : 'outline'} />
          ),
        }}
      />
    </Tabs>
  );
}
