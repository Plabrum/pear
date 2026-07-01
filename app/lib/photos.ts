import * as ImagePicker from 'expo-image-picker';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { toast } from 'sonner-native';

import { supabase } from '@/lib/supabase';
import { patchApiProfilesMe } from '@/lib/api/generated/profiles/profiles';

export async function pickAndResizePhoto(opts?: {
  width?: number;
  aspect?: [number, number];
}): Promise<string | null> {
  const { width = 1200, aspect } = opts ?? {};

  const { granted } = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!granted) {
    toast.error('Allow photo access in Settings.');
    return null;
  }
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    allowsEditing: true,
    aspect,
    quality: 1,
  });
  if (result.canceled || !result.assets[0]) return null;

  const ctx = ImageManipulator.manipulate(result.assets[0].uri);
  ctx.resize({ width });
  const imageRef = await ctx.renderAsync();
  const saved = await imageRef.saveAsync({ compress: 0.8, format: SaveFormat.JPEG });
  return saved.uri;
}

export async function uploadAvatar(userId: string, uri: string): Promise<void> {
  const path = `${userId}.jpg`;
  const arrayBuffer = await fetch(uri).then((res) => res.arrayBuffer());

  const { error: uploadError } = await supabase.storage
    .from('avatars')
    .upload(path, arrayBuffer, { contentType: 'image/jpeg', upsert: true });

  if (uploadError) throw uploadError;

  const { data } = supabase.storage.from('avatars').getPublicUrl(path);
  await patchApiProfilesMe({ avatarUrl: `${data.publicUrl}?t=${Date.now()}` });
}

export function getPhotoUrl(storagePath: string | null): string | null {
  if (!storagePath) return null;
  if (storagePath.startsWith('http')) return storagePath;
  const { data } = supabase.storage.from('profile-photos').getPublicUrl(storagePath);
  return data.publicUrl;
}
