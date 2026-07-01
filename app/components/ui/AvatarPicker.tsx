import { useState } from 'react';
import { toast } from 'sonner-native';
import { useQueryClient } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';

import { View, Pressable } from '@/lib/tw';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { getGetApiProfilesMeQueryKey } from '@/lib/api/generated/profiles/profiles';
import { pickAndResizePhoto, uploadAvatar } from '@/lib/photos';
import { colors } from '@/constants/theme';

type AvatarPickerProps = {
  name: string | null;
  avatarUrl: string | null;
  size: number;
  userId: string;
};

export function AvatarPicker({ name, avatarUrl, size, userId }: AvatarPickerProps) {
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);

  const handlePick = async () => {
    const uri = await pickAndResizePhoto({ width: 400, aspect: [1, 1] });
    if (!uri) return;

    setUploading(true);
    try {
      await uploadAvatar(userId, uri);
      queryClient.invalidateQueries({ queryKey: getGetApiProfilesMeQueryKey() });
    } catch {
      toast.error("Couldn't upload photo. Try again.");
    } finally {
      setUploading(false);
    }
  };

  const badge = Math.round(size * 0.34);

  return (
    <Pressable onPress={handlePick} className="relative" style={{ width: size, height: size }}>
      <FaceAvatar name={name ?? ''} size={size} photoUri={avatarUrl} />
      <View
        className="absolute items-center justify-center bg-surface"
        style={{
          right: -2,
          bottom: -2,
          width: badge,
          height: badge,
          borderRadius: badge / 2,
          borderWidth: 1.5,
          borderColor: '#F5F1E8',
          opacity: uploading ? 0.5 : 1,
        }}
      >
        <Ionicons name="camera-outline" size={Math.round(badge * 0.55)} color={colors.ink} />
      </View>
    </Pressable>
  );
}
