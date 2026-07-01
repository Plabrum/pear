import { Stack } from 'expo-router';

export default function AuthLayout() {
  return (
    <Stack>
      <Stack.Screen name="login" options={{ headerShown: false }} />
      <Stack.Screen
        name="sms"
        options={{
          presentation: 'formSheet',
          headerShown: true,
          title: 'Phone Number',
          sheetGrabberVisible: true,
          sheetAllowedDetents: [0.65, 1.0],
        }}
      />
    </Stack>
  );
}
