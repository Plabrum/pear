import { Alert, Dimensions } from 'react-native';
import PulseSpinner from '@/components/ui/PulseSpinner';
import { toast } from 'sonner-native';
import type { UseFormReturn } from 'react-hook-form';
import Svg, { Path } from 'react-native-svg';

import type { OwnDatingProfileResponse } from '@/lib/api/generated/model';
import { useUploadProfilePhoto } from '@/hooks/use-upload-profile-photo';
import { getPhotoUrl, pickAndResizePhoto } from '@/lib/photos';
import {
  patchApiPhotosIdReorder,
  postApiPhotosIdApprove,
  postApiPhotosIdReject,
} from '@/lib/api/generated/photos/photos';

import { ScrollView, Text, Pressable, View } from '@/lib/tw';
import { PhotoRect } from '@/components/ui/PhotoRect';
import { FaceAvatar } from '@/components/ui/FaceAvatar';
import { Sprout } from '@/components/ui/Sprout';

const LINE = 'rgba(31,27,22,0.10)';
const LEAF = '#5A8C3A';

const PHOTO_GAP = 8;
const PHOTO_COL = (Dimensions.get('window').width - 16 * 2 - PHOTO_GAP * 2) / 3;

function FieldLabel({ children }: { children: string }) {
  return (
    <Text
      className="text-ink-dim"
      style={{
        fontSize: 10.5,
        letterSpacing: 1.4,
        textTransform: 'uppercase',
        fontWeight: '600',
        marginBottom: 8,
      }}
    >
      {children}
    </Text>
  );
}

function PlusIcon({ size = 18, color = LEAF }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 5v14M5 12h14" stroke={color} strokeWidth={2} strokeLinecap="round" />
    </Svg>
  );
}

function ArrowUpIcon({ size = 12, color = '#fff' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 19V5M5 12l7-7 7 7"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function XIcon({ size = 12, color = '#fff' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M6 6l12 12M18 6L6 18" stroke={color} strokeWidth={2} strokeLinecap="round" />
    </Svg>
  );
}

interface Props {
  form: UseFormReturn<NonNullable<OwnDatingProfileResponse>>;
  data: NonNullable<OwnDatingProfileResponse>;
  onRefresh: () => Promise<void>;
}

export function PhotosTab({ form, data, onRefresh }: Props) {
  const { upload, isPending: uploading } = useUploadProfilePhoto();

  const photos = form.watch('photos');
  const selfPhotos = photos.filter((p) => p.suggesterId === null && p.approvedAt !== null);
  const pending = photos.filter((p) => p.suggesterId !== null && p.approvedAt === null);

  const handleApprove = async (photoId: string) => {
    const prev = photos;
    const now = new Date().toISOString();
    form.setValue(
      'photos',
      photos.map((p) => (p.id === photoId ? { ...p, approvedAt: now } : p))
    );
    try {
      await postApiPhotosIdApprove(photoId);
    } catch {
      form.setValue('photos', prev);
      toast.error('Could not approve photo.');
    }
  };

  const handleReject = async (photoId: string) => {
    const prev = photos;
    form.setValue(
      'photos',
      photos.filter((p) => p.id !== photoId)
    );
    try {
      await postApiPhotosIdReject(photoId);
    } catch {
      form.setValue('photos', prev);
      toast.error('Could not reject photo.');
    }
  };

  const handleMoveUp = async (idx: number) => {
    if (idx === 0) return;
    const updated = [...selfPhotos];
    [updated[idx - 1], updated[idx]] = [updated[idx], updated[idx - 1]];
    const payload = updated.map((p, i) => ({ id: p.id, displayOrder: i }));
    const prev = photos;
    form.setValue('photos', [...updated.map((p, i) => ({ ...p, displayOrder: i })), ...pending]);
    try {
      await Promise.all(
        payload.map(({ id, displayOrder }) => patchApiPhotosIdReorder(id, { displayOrder }))
      );
      onRefresh();
    } catch {
      form.setValue('photos', prev);
      toast.error('Could not reorder photos.');
    }
  };

  const handleDelete = (idx: number) => {
    const photo = selfPhotos[idx];
    Alert.alert('Delete Photo', "This can't be undone.", [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          const prev = photos;
          form.setValue(
            'photos',
            photos.filter((p) => p.id !== photo.id)
          );
          try {
            await postApiPhotosIdReject(photo.id);
          } catch {
            form.setValue('photos', prev);
            toast.error('Could not delete photo.');
          }
        },
      },
    ]);
  };

  const handleAddPhoto = async () => {
    const uri = await pickAndResizePhoto();
    if (!uri) return;
    const ok = await upload(data.id, uri, `${Date.now()}.jpg`, selfPhotos.length);
    if (ok) await onRefresh();
  };

  return (
    <ScrollView
      contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
      showsVerticalScrollIndicator={false}
    >
      {pending.length > 0 ? (
        <View style={{ marginBottom: 18 }}>
          <FieldLabel>Suggested by wingpeople</FieldLabel>
          {pending.map((photo) => {
            const suggesterName = photo.suggester?.chosenName ?? 'a wingperson';
            return (
              <View
                key={photo.id}
                className="bg-surface"
                style={{
                  borderRadius: 18,
                  borderWidth: 1,
                  borderColor: LINE,
                  overflow: 'hidden',
                  marginBottom: 10,
                }}
              >
                <PhotoRect
                  uri={getPhotoUrl(photo.storageUrl)}
                  ratio={4 / 3}
                  blur
                  style={{ borderRadius: 0 }}
                />
                <View style={{ padding: 14 }}>
                  <View
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}
                  >
                    <FaceAvatar name={photo.suggester?.chosenName ?? ''} size={22} />
                    <Text className="text-ink" style={{ fontSize: 14, fontWeight: '600' }}>
                      From {suggesterName}
                    </Text>
                  </View>
                  <Text className="text-ink-dim" style={{ fontSize: 13, marginBottom: 12 }}>
                    Approve to add this to your profile.
                  </Text>
                  <View style={{ flexDirection: 'row', gap: 8 }}>
                    <View style={{ flex: 1 }}>
                      <Sprout block size="sm" onPress={() => handleApprove(photo.id)}>
                        Approve
                      </Sprout>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Sprout
                        block
                        size="sm"
                        variant="secondary"
                        onPress={() => handleReject(photo.id)}
                      >
                        Reject
                      </Sprout>
                    </View>
                  </View>
                </View>
              </View>
            );
          })}
        </View>
      ) : null}

      <FieldLabel>
        {`My photos${selfPhotos.length > 0 ? ` · ${selfPhotos.length}` : ''}`}
      </FieldLabel>

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: PHOTO_GAP }}>
        {selfPhotos.map((photo, idx) => (
          <View
            key={photo.id}
            style={{ width: PHOTO_COL, aspectRatio: 3 / 4, position: 'relative' }}
          >
            <PhotoRect
              uri={getPhotoUrl(photo.storageUrl)}
              ratio={3 / 4}
              style={{ borderRadius: 14 }}
            />
            {idx === 0 ? (
              <View
                className="bg-primary"
                style={{
                  position: 'absolute',
                  top: 6,
                  left: 6,
                  borderRadius: 8,
                  paddingHorizontal: 6,
                  paddingVertical: 2,
                }}
              >
                <Text className="text-surface" style={{ fontSize: 10, fontWeight: '700' }}>
                  Primary
                </Text>
              </View>
            ) : (
              <Pressable
                onPress={() => handleMoveUp(idx)}
                hitSlop={4}
                style={{
                  position: 'absolute',
                  top: 6,
                  left: 6,
                  width: 22,
                  height: 22,
                  borderRadius: 11,
                  backgroundColor: 'rgba(0,0,0,0.45)',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <ArrowUpIcon />
              </Pressable>
            )}
            <Pressable
              onPress={() => handleDelete(idx)}
              hitSlop={4}
              style={{
                position: 'absolute',
                top: 6,
                right: 6,
                width: 22,
                height: 22,
                borderRadius: 11,
                backgroundColor: 'rgba(0,0,0,0.45)',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <XIcon />
            </Pressable>
          </View>
        ))}

        <Pressable
          onPress={handleAddPhoto}
          disabled={uploading}
          style={{
            width: PHOTO_COL,
            height: Math.round(PHOTO_COL * (4 / 3)),
            borderRadius: 14,
            borderWidth: 1.5,
            borderStyle: 'dashed',
            borderColor: LEAF,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {uploading ? <PulseSpinner color={LEAF} /> : <PlusIcon size={20} />}
        </Pressable>
      </View>

      {selfPhotos.length === 0 ? (
        <Text className="text-ink-dim" style={{ fontSize: 13, marginTop: 12 }}>
          Add at least one so people can see you.
        </Text>
      ) : null}
    </ScrollView>
  );
}
