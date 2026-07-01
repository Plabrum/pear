import * as ImagePicker from 'expo-image-picker';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { toast } from 'sonner-native';

import { getAvatarUploadUrl, updateMyProfile } from '@/lib/api/actions';

const AVATAR_CONTENT_TYPE = 'image/jpeg';

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

// Avatar upload (S3 presigned PUT, public-read key).
// Asks the API for a presigned upload URL rooted in the caller's own id, `PUT`s
// the resized JPEG bytes straight to S3, then PATCHes the profile with
// `avatarUrl = key` (the DB stores the S3 KEY; reads resolve it to the stable
// public URL). `userId` is the caller's own profile id (Profile.id === userId).
export async function uploadAvatar(userId: string, uri: string): Promise<void> {
  const { uploadUrl, key } = await getAvatarUploadUrl({
    filename: `${userId}.jpg`,
    contentType: AVATAR_CONTENT_TYPE,
  });
  // Raw PUT straight to S3 — NO Authorization header, the presigned URL IS the grant.
  const blob = await fetch(uri).then((res) => res.blob());
  const putRes = await fetch(uploadUrl, {
    method: 'PUT',
    body: blob,
    headers: { 'Content-Type': AVATAR_CONTENT_TYPE },
  });
  if (!putRes.ok) throw new Error(`S3 PUT failed: ${putRes.status}`);
  // Persist the KEY; the avatar resolves to its stable public URL on reads.
  await updateMyProfile(userId, { avatarUrl: key });
}

// Read endpoints already return ready-to-load URLs in `storageUrl` (a short-lived
// presigned GET for photos; a stable public URL for avatars), so this is now a
// thin pass-through. Kept so callsites don't have to special-case null.
export function getPhotoUrl(storageUrl: string | null): string | null {
  return storageUrl ?? null;
}
