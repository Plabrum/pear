import { useState } from 'react';
import { toast } from 'sonner-native';

import { addPhoto, getPhotoUploadUrl } from '@/lib/api/actions';

const CONTENT_TYPE = 'image/jpeg';

// Unified profile-photo upload flow (S3 presigned PUT).
// Asks the API for a presigned upload URL (the server picks the storage key —
// owner for self-uploads, dater folder for wingperson suggestions — and gates
// the write), `PUT`s the resized JPEG bytes straight to S3, then writes the
// profile_photos metadata row with `storageUrl = key` (the DB stores the S3 KEY,
// never a URL). Owns its own pending state and error toast — callsites await
// `upload(...)` and branch on the boolean.
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
      const { uploadUrl, key } = await getPhotoUploadUrl({
        datingProfileId,
        filename,
        contentType: CONTENT_TYPE,
      });
      // Raw PUT straight to S3 — NO Authorization header, the presigned URL IS the
      // grant. The image bytes never transit our API box.
      const blob = await fetch(uri).then((r) => r.blob());
      const putRes = await fetch(uploadUrl, {
        method: 'PUT',
        body: blob,
        headers: { 'Content-Type': CONTENT_TYPE },
      });
      if (!putRes.ok) throw new Error(`S3 PUT failed: ${putRes.status}`);
      // Persist the KEY as the photo's storageUrl; reads issue a presigned GET URL.
      await addPhoto({ datingProfileId, storageUrl: key, displayOrder });
      return true;
    } catch {
      toast.error('Failed to upload photo. Please try again.');
      return false;
    } finally {
      setIsPending(false);
    }
  };

  return { upload, isPending };
}
