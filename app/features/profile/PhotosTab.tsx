import { Alert, Dimensions } from 'react-native';
import PulseSpinner from '@/components/PulseSpinner';
import type { UseFormReturn } from 'react-hook-form';

import type { OwnDatingProfile } from '@/lib/api/generated/model';
import { useUploadProfilePhoto } from '@/hooks/use-upload-profile-photo';
import { pickAndResizePhoto } from '@/lib/photos';
import { reorderPhoto } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import { useActionExecutor } from '@/hooks/actions/use-action-executor';
import { shortKey, type ActionDTO } from '@/lib/actions/types';

import { ScrollView, Text, Pressable, View } from '@/lib/tw';
import { PhotoRect } from '@/components/PhotoRect';
import { FaceAvatar } from '@/components/FaceAvatar';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { FieldLabel } from '@/components/FieldLabel';
import { PlusIcon, ArrowUpIcon, XIcon } from '@/components/icons';
import { colors } from '@/constants/theme';

const PHOTO_GAP = 8;
const PHOTO_COL = (Dimensions.get('window').width - 16 * 2 - PHOTO_GAP * 2) / 3;

interface Props {
  form: UseFormReturn<OwnDatingProfile>;
  data: OwnDatingProfile;
  onRefresh: () => Promise<void>;
}

export function PhotosTab({ form, data, onRefresh }: Props) {
  const { upload, isPending: uploading } = useUploadProfilePhoto();

  const photos = form.watch('photos');
  const selfPhotos = photos.filter((p) => p.suggesterId === null && p.status === 'approved');
  const pending = photos.filter((p) => p.suggesterId !== null && p.status === 'pending');

  // Photo writes flow through the executor, driven by each photo's server actions[]
  // (approve / reject / delete). `silent` keeps the quiet optimistic UX (form.setValue
  // below); the executor handles invalidation + error toasts. Reorder stays a direct
  // call (it's a hidden, batched action — not surfaced in actions[]).
  const executor = useActionExecutor({ actionGroup: 'photo_actions' });
  const photoAction = (photoId: string, key: string): ActionDTO | undefined =>
    (photos.find((p) => p.id === photoId)?.actions ?? []).find((a) => shortKey(a.action) === key);

  const handleApprove = async (photoId: string) => {
    const action = photoAction(photoId, 'approve');
    if (!action) return;
    const prev = photos;
    form.setValue(
      'photos',
      photos.map((p) => (p.id === photoId ? { ...p, status: 'approved' } : p))
    );
    await executor
      .executeAction(action, undefined, { objectId: photoId, silent: true })
      .catch(() => form.setValue('photos', prev));
  };

  const handleReject = async (photoId: string) => {
    const action = photoAction(photoId, 'reject');
    if (!action) return;
    const prev = photos;
    form.setValue(
      'photos',
      photos.filter((p) => p.id !== photoId)
    );
    await executor
      .executeAction(action, undefined, { objectId: photoId, silent: true })
      .catch(() => form.setValue('photos', prev));
  };

  const handleMoveUp = async (idx: number) => {
    if (idx === 0) return;
    const updated = [...selfPhotos];
    [updated[idx - 1], updated[idx]] = [updated[idx], updated[idx - 1]];
    const payload = updated.map((p, i) => ({ id: p.id, displayOrder: i }));
    const prev = photos;
    form.setValue('photos', [...updated.map((p, i) => ({ ...p, displayOrder: i })), ...pending]);
    try {
      await Promise.all(payload.map(({ id, displayOrder }) => reorderPhoto(id, { displayOrder })));
      onRefresh();
    } catch (err) {
      form.setValue('photos', prev);
      toastError(err, 'Could not reorder photos.');
    }
  };

  const handleDelete = (idx: number) => {
    const photo = selfPhotos[idx];
    const action = photoAction(photo.id, 'delete');
    if (!action) return;
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
          await executor
            .executeAction(action, undefined, { objectId: photo.id, silent: true })
            .catch(() => form.setValue('photos', prev));
        },
      },
    ]);
  };

  const handleAddPhoto = async () => {
    const uri = await pickAndResizePhoto({ aspect: [3, 4] });
    if (!uri) return;
    // The resized file's own basename is already unique (the manipulator writes
    // to a fresh temp path), so derive the upload filename from it — no need for
    // an impure `Date.now()` read.
    const filename = uri.split('/').pop() ?? 'photo.jpg';
    const ok = await upload(data.id, uri, filename, selfPhotos.length);
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
              <Card
                key={photo.id}
                className="overflow-hidden"
                style={{ borderRadius: 18, marginBottom: 10 }}
              >
                <PhotoRect uri={photo.storageUrl} ratio={4 / 3} blur style={{ borderRadius: 0 }} />
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
                      <Button block size="sm" onPress={() => handleApprove(photo.id)}>
                        Approve
                      </Button>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Button
                        block
                        size="sm"
                        variant="secondary"
                        onPress={() => handleReject(photo.id)}
                      >
                        Reject
                      </Button>
                    </View>
                  </View>
                </View>
              </Card>
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
            <PhotoRect uri={photo.storageUrl} ratio={3 / 4} style={{ borderRadius: 14 }} />
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
            borderColor: colors.leaf,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {uploading ? <PulseSpinner color={colors.leaf} /> : <PlusIcon size={20} />}
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
