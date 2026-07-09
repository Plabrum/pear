import { Tabs } from 'expo-router';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { PearMark } from '@/components/ui/PearMark';
import { tabScreenOptions } from '@/components/ui/tabBar';

export default function WingerTabLayout() {
  return (
    <Tabs screenOptions={tabScreenOptions}>
      <Tabs.Screen
        name="friends"
        options={{
          title: 'Friends',
          tabBarIcon: ({ color }) => <Ionicons name="people-outline" size={22} color={color} />,
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
