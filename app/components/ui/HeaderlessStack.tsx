import { Stack } from 'expo-router';

// A nested headerless Stack — the canonical layout for a tab whose detail
// screens push as cards (messages, profile, friends). Shared so the
// per-directory _layout files stay one line and can't drift.
export default function HeaderlessStack() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
