import { useState } from 'react';

import { addPhoto } from '@/lib/api/actions';
import { uploadMedia } from '@/lib/photos';
import { toastError } from '@/lib/api/error-toast';

const CONTENT_TYPE = 'image/jpeg';

// Unified profile-photo upload flow over the media domain. Uploads the resized
// JPEG via the three-step media handshake (presigned PUT -> uploaded), then
// writes the profile_photos row pinned to the returned media id. Works for both
// self-uploads and wingperson suggestions — the action route authorizes the
// dater-owner or an active wingperson. Owns its own pending state and error
// toast; callsites await `upload(...)` and branch on the boolean.
export function useUploadProfilePhoto() {
  const [isPending, setIsPending] = useState(false);

  const upload = async (
    datingProfileId: string,
    uri: string,
    filename: string,
    displayOrder: number
  ): Promise<boolean> => {
    setIsPending(true);
    try {
      const mediaId = await uploadMedia(uri, filename, CONTENT_TYPE);
      await addPhoto({ datingProfileId, mediaId, displayOrder });
      return true;
    } catch (err) {
      toastError(err, 'Failed to upload photo. Please try again.');
      return false;
    } finally {
      setIsPending(false);
    }
  };

  return { upload, isPending };
}
