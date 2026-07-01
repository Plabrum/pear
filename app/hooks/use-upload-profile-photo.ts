import { useState } from 'react';
import { toast } from 'sonner-native';

import { postApiPhotos, postApiPhotosUploadUrl } from '@/lib/api/generated/photos/photos';
import { supabase } from '@/lib/supabase';

// Unified profile-photo upload flow. Asks the API for a signed upload token
// (server picks the storage folder — owner for self-uploads, dater for
// wingperson suggestions), uploads the file body, then writes the
// profile_photos metadata row. On metadata-write failure, best-effort removes
// the storage object to avoid orphans. Owns its own pending state and error
// toast — callsites await `upload(...)` and branch on the boolean.
export function useUploadProfilePhoto() {
  const [isPending, setIsPending] = useState(false);

  const upload = async (
    datingProfileId: string,
    uri: string,
    filename: string,
    displayOrder: number
  ): Promise<boolean> => {
    setIsPending(true);
    let uploadedPath: string | null = null;
    try {
      const { path, uploadToken } = await postApiPhotosUploadUrl({
        datingProfileId,
        filename,
      });
      const arrayBuffer = await fetch(uri).then((r) => r.arrayBuffer());
      const { error: upErr } = await supabase.storage
        .from('profile-photos')
        .uploadToSignedUrl(path, uploadToken, arrayBuffer, { contentType: 'image/jpeg' });
      if (upErr) throw upErr;
      uploadedPath = path;
      await postApiPhotos({ datingProfileId, storageUrl: path, displayOrder });
      return true;
    } catch {
      if (uploadedPath) {
        await supabase.storage
          .from('profile-photos')
          .remove([uploadedPath])
          .catch(() => {});
      }
      toast.error('Failed to upload photo. Please try again.');
      return false;
    } finally {
      setIsPending(false);
    }
  };

  return { upload, isPending };
}
