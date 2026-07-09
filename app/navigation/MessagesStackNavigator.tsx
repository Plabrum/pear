import { createNativeStackNavigator } from '@react-navigation/native-stack';

import type { MessagesStackParamList } from './types';
import MessagesListScreen from '../app/(tabs)/messages/index';
import MessageThreadScreen from '../app/(tabs)/messages/[matchId]';

const Stack = createNativeStackNavigator<MessagesStackParamList>();

export function MessagesStackNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="MessagesList" component={MessagesListScreen} />
      <Stack.Screen name="MessageThread" component={MessageThreadScreen} />
    </Stack.Navigator>
  );
}
