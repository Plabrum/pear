import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { PearMark } from '@/components/ui/PearMark';
import { tabScreenOptions } from '@/components/ui/tabBar';
import type { WingerTabParamList } from './types';
import { FriendsStackNavigator } from './FriendsStackNavigator';
import ActivityScreen from '../app/(winger-tabs)/activity';
import MeScreen from '../app/(winger-tabs)/me';

const Tab = createBottomTabNavigator<WingerTabParamList>();

export function WingerTabsNavigator() {
  return (
    <Tab.Navigator screenOptions={tabScreenOptions}>
      <Tab.Screen
        name="Friends"
        component={FriendsStackNavigator}
        options={{
          title: 'Friends',
          tabBarIcon: ({ color }) => <Ionicons name="people-outline" size={22} color={color} />,
        }}
      />
      <Tab.Screen
        name="Activity"
        component={ActivityScreen}
        options={{
          title: 'Activity',
          tabBarIcon: ({ color }) => <Ionicons name="sparkles" size={22} color={color} />,
        }}
      />
      <Tab.Screen
        name="Me"
        component={MeScreen}
        options={{
          title: 'Me',
          tabBarIcon: ({ color, focused }) => (
            <PearMark size={22} color={color} variant={focused ? 'flat' : 'outline'} />
          ),
        }}
      />
    </Tab.Navigator>
  );
}
