import RNBlobUtil from 'react-native-blob-util';
import ImagePicker from 'react-native-image-crop-picker';
import ImageResizer from '@bam.tech/react-native-image-resizer';
import { toast } from 'sonner-native';

import { updateMyProfile } from '@/lib/api/actions';
import { postApiMediaUploadUrl, postApiMediaUploaded } from '@/lib/api/generated/media/media';

const AVATAR_CONTENT_TYPE = 'image/jpeg';
const COMPRESS_QUALITY = 0.8;

// react-native-image-resizer fits within a width x height box (aspect ratio preserved)
// rather than scaling off a single axis like expo-image-manipulator did. We only ever
// want to cap by width, so pass a height large enough that width stays the binding
// constraint for any realistic camera-roll aspect ratio.
const UNBOUNDED_HEIGHT = 10000;

export async function pickAndResizePhoto(opts: {
  aspect: [number, number];
  width?: number;
}): Promise<string | null> {
  const { width = 1200, aspect } = opts;
  const [aspectW, aspectH] = aspect;

  // react-native-image-crop-picker prompts for photo-library permission itself
  // (no separate requestMediaLibraryPermissionsAsync-style call) and rejects the
  // returned promise on cancel (E_PICKER_CANCELLED) or on permission denial —
  // treat both as a plain "no photo picked" outcome rather than a thrown error.
  // `cropping: true` always locks to the given width/height ratio — there is no
  // free-form-crop equivalent on this library, so every caller passes the
  // aspect ratio it actually displays at.
  const image = await ImagePicker.openPicker({
    cropping: true,
    width: Math.round(width * aspectW),
    height: Math.round(width * aspectH),
    mediaType: 'photo',
    compressImageQuality: 1,
  }).catch((error: { code?: string }) => {
    if (error?.code !== 'E_PICKER_CANCELLED') {
      toast.error('Allow photo access in Settings.');
    }
    return null;
  });
  if (!image) return null;

  const { uri } = await ImageResizer.createResizedImage(
    image.path,
    width,
    UNBOUNDED_HEIGHT,
    'JPEG',
    Math.round(COMPRESS_QUALITY * 100)
  );
  return uri;
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

  // Stream the local file straight to the presigned URL via native code. Don't go
  // through fetch().blob() — Expo's winter fetch can't build a Blob from a file
  // URI's ArrayBuffer, which throws at runtime. RNBlobUtil.wrap() hands fetch a
  // file-path token that its native layer reads and streams directly, sidestepping
  // the JS Blob polyfill entirely.
  const putRes = await RNBlobUtil.fetch(
    'PUT',
    uploadUrl,
    { 'Content-Type': contentType },
    RNBlobUtil.wrap(uri)
  );
  const status = putRes.respInfo.status;
  if (status < 200 || status >= 300) {
    throw new Error(`Upload PUT failed: ${status}`);
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
