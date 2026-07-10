import { createNativeStackNavigator } from '@react-navigation/native-stack';

import type { FriendsStackParamList } from './types';
import FriendsListScreen from '../features/friends/index';
import FriendDetailScreen from '../features/friends/[id]/index';
import FriendScoutScreen from '../features/friends/[id]/scout';

const Stack = createNativeStackNavigator<FriendsStackParamList>();

export function FriendsStackNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="FriendsList" component={FriendsListScreen} />
      <Stack.Screen name="FriendDetail" component={FriendDetailScreen} />
      <Stack.Screen name="FriendScout" component={FriendScoutScreen} />
    </Stack.Navigator>
  );
}
