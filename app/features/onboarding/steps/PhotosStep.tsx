import { useState } from 'react';
import { Image } from 'react-native';
import PulseSpinner from '@/components/PulseSpinner';
import { Pressable, ScrollView, Text, View } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { Button } from '@/components/Button';
import { PearMark } from '@/components/PearMark';
import { XIcon } from '@/components/icons';
import { colors } from '@/constants/theme';
import { getApiDatingProfilesMe } from '@/lib/api/generated/profiles/profiles';
import { deletePhoto } from '@/lib/api/actions';
import { useUploadProfilePhoto } from '@/hooks/use-upload-profile-photo';
import { pickAndResizePhoto } from '@/lib/photos';
import { toastError } from '@/lib/api/error-toast';
import { StepHeader } from '@/features/onboarding/chrome';

type LocalPhoto = { id: string; uri: string };

export function PhotosStep({ dpId, onContinue }: { dpId: string | null; onContinue: () => void }) {
  const [photos, setPhotos] = useState<LocalPhoto[]>([]);
  const { upload, isPending: uploading } = useUploadProfilePhoto();

  async function refresh() {
    const data = await getApiDatingProfilesMe();
    if (!data) return;
    setPhotos(
      data.photos.flatMap((p) => {
        const uri = p.storageUrl;
        return uri ? [{ id: p.id, uri }] : [];
      })
    );
  }

  async function handleAdd() {
    if (!dpId || photos.length >= 6) return;
    const uri = await pickAndResizePhoto({ aspect: [3, 4] });
    if (!uri) return;
    const ok = await upload(dpId, uri, `${Date.now()}.jpg`, photos.length);
    if (ok) await refresh();
  }

  async function handleRemove(photoId: string) {
    const previous = photos;
    setPhotos((p) => p.filter((x) => x.id !== photoId));
    try {
      await deletePhoto(photoId);
    } catch (err) {
      setPhotos(previous);
      toastError(err, 'Failed to remove photo. Please try again.');
    }
  }

  const slots = Array.from({ length: 6 }, (_, i) => photos[i] ?? null);
  const canContinue = photos.length >= 1;

  return (
    <View className="flex-1">
      <ScrollView className="flex-1" contentContainerClassName="pb-4">
        <StepHeader
          kicker="Step 2 · Show up"
          title="Add a few"
          accent="photos"
          sub="At least one. The first one shows up biggest."
        />
        <View className="flex-row flex-wrap mt-[22px]" style={{ gap: 8 }}>
          {slots.map((slot, i) => (
            <View key={i} style={{ width: '31%', aspectRatio: 3 / 4 }}>
              {slot ? (
                <PhotoSlot photo={slot} isMain={i === 0} onRemove={() => handleRemove(slot.id)} />
              ) : (
                <EmptySlot onPress={handleAdd} disabled={uploading || !dpId} />
              )}
            </View>
          ))}
        </View>
        <View
          className="mt-4 px-3.5 py-3 rounded-[14px] bg-primary-soft flex-row items-start"
          style={{ gap: 10 }}
        >
          <View
            className="w-7 h-7 rounded-full bg-primary items-center justify-center"
            style={{ flexShrink: 0 }}
          >
            <PearMark
              size={16}
              color={colors.white}
              leaf={colors.white}
              stem={colors.white}
              variant="flat"
            />
          </View>
          <Text className="flex-1 text-[12.5px] text-foreground-muted leading-[18px]">
            <Text className="text-foreground font-semibold">Ask a wingperson</Text> to suggest a
            photo of you they think shows up well.
          </Text>
        </View>
      </ScrollView>
      <Button block size="md" onPress={onContinue} disabled={!canContinue}>
        Continue
      </Button>
    </View>
  );
}

function PhotoSlot({
  photo,
  isMain,
  onRemove,
}: {
  photo: LocalPhoto;
  isMain: boolean;
  onRemove: () => void;
}) {
  return (
    <View
      className={cn(
        'w-full h-full rounded-[14px] overflow-hidden relative',
        isMain ? 'border-[1.5px] border-primary' : 'border border-border'
      )}
    >
      <Image
        source={{ uri: photo.uri }}
        style={{ width: '100%', height: '100%' }}
        resizeMode="cover"
      />
      {isMain ? (
        <View
          className="absolute top-1.5 left-1.5 bg-primary rounded-md"
          style={{ paddingHorizontal: 7, paddingVertical: 3 }}
        >
          <Text
            className="font-mono text-primary-foreground uppercase"
            style={{ fontSize: 10, fontWeight: '700', letterSpacing: 0.6 }}
          >
            Main
          </Text>
        </View>
      ) : null}
      <Pressable
        onPress={onRemove}
        hitSlop={6}
        className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full items-center justify-center"
        style={{ backgroundColor: colors.scrim65 }}
      >
        <XIcon color={colors.white} size={12} />
      </Pressable>
    </View>
  );
}

function EmptySlot({ onPress, disabled }: { onPress: () => void; disabled: boolean }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      className={cn(
        'w-full h-full rounded-[14px] bg-surface border-[1.5px] border-dashed border-border items-center justify-center',
        disabled && 'opacity-40'
      )}
    >
      {disabled ? (
        <PulseSpinner color={colors.primary} />
      ) : (
        <Text className="text-foreground-subtle" style={{ fontSize: 24, lineHeight: 24 }}>
          +
        </Text>
      )}
    </Pressable>
  );
}
