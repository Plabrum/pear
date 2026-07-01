import { File, UploadType } from 'expo-file-system';
import * as ImagePicker from 'expo-image-picker';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';
import { toast } from 'sonner-native';

import { updateMyProfile } from '@/lib/api/actions';
import { postApiMediaUploadUrl, postApiMediaUploaded } from '@/lib/api/generated/media/media';

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

// Three-step media upload. Mints a presigned PUT from the media domain, streams
// the already-resized bytes straight to object storage (no Authorization header —
// the presigned URL is the grant), then marks the row uploaded so the backend
// enqueues async WebP processing. Returns the media id the caller pins to a photo
// row or an avatar. The image never transits our API box.
export async function uploadMedia(
  uri: string,
  fileName: string,
  contentType: string
): Promise<string> {
  const { mediaId, uploadUrl } = await postApiMediaUploadUrl({ fileName, contentType });

  // Stream the local file straight to the presigned URL via the native upload task.
  // Don't go through fetch().blob() — Expo's winter fetch can't build a Blob from a
  // file URI's ArrayBuffer, which throws at runtime.
  const putRes = await new File(uri).upload(uploadUrl, {
    httpMethod: 'PUT',
    uploadType: UploadType.BINARY_CONTENT,
    headers: { 'Content-Type': contentType },
  });
  if (putRes.status < 200 || putRes.status >= 300) {
    throw new Error(`Upload PUT failed: ${putRes.status}`);
  }

  // Flips the row toward processing; the response state is still PENDING here.
  await postApiMediaUploaded(mediaId);
  return mediaId;
}

// Avatar upload. Uploads the resized JPEG via the media domain, then PATCHes the
// caller's profile with `avatarMediaId`. `userId` is the caller's own profile id
// (Profile.id === userId). Reads resolve the avatar field to a presigned URL.
export async function uploadAvatar(userId: string, uri: string): Promise<void> {
  const mediaId = await uploadMedia(uri, `${userId}.jpg`, AVATAR_CONTENT_TYPE);
  await updateMyProfile(userId, { avatarMediaId: mediaId });
}