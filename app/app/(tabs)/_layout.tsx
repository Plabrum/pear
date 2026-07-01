import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

import { PearMark } from '@/components/ui/PearMark';
import { tabScreenOptions } from '@/components/ui/tabBar';

export default function TabLayout() {
  return (
    <Tabs screenOptions={tabScreenOptions}>
      <Tabs.Screen
        name="discover"
        options={{
          title: 'Discover',
          tabBarIcon: ({ color }) => <Ionicons name="albums-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="matches"
        options={{
          title: 'Matches',
          tabBarIcon: ({ color }) => <Ionicons name="heart-outline" size={22} color={color} />,
        }}
      />
      <Tabs.Screen
        name="messages"
        options={{
          title: 'Messages',
          tabBarIcon: ({ color }) => <Ionicons name="chatbubble-outline" size={22} color={color} />,
          popToTopOnBlur: true,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, focused }) => (
            <PearMark size={22} color={color} variant={focused ? 'flat' : 'outline'} />
          ),
        }}
      />
    </Tabs>
  );
}
