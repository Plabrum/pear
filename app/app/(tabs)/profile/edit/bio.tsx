import { useNavigation } from '@react-navigation/native';
import { useQueryClient } from '@tanstack/react-query';

import {
  useGetApiDatingProfilesMeSuspense,
  getGetApiDatingProfilesMeQueryKey,
} from '@/lib/api/generated/profiles/profiles';
import { updateDatingProfile } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import { View, Text, ScrollView, SafeAreaView, TextInput } from '@/lib/tw';
import { colors } from '@/constants/theme';
import { NavHeader } from '@/components/ui/NavHeader';
import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { createTypedForm } from '@/lib/forms/typed-form';

type Values = { bio: string };
const BioForm = createTypedForm<Values>();

function BioScreenInner() {
  const navigation = useNavigation();
  const queryClient = useQueryClient();
  const { data: datingProfile } = useGetApiDatingProfilesMeSuspense();

  const saveBio = async (raw: string) => {
    if (!datingProfile) return;
    const bio = raw.trim();
    try {
      await updateDatingProfile(datingProfile.id, { bio: bio || null });
      queryClient.invalidateQueries({ queryKey: getGetApiDatingProfilesMeQueryKey() });
    } catch (err) {
      toastError(err, 'Could not save bio. Try again.');
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <NavHeader back title="Bio" onBack={() => navigation.goBack()} />
      <BioForm.Form defaultValues={{ bio: datingProfile?.bio ?? '' }} onSubmit={() => {}}>
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          <BioForm.CustomField
            name="bio"
            optional
            bare
            render={({ value, onChange }) => (
              <View>
                <TextInput
                  className="bg-white rounded-xl border-[1.5px] border-separator px-4 py-[14px] text-base text-fg min-h-[140px]"
                  style={{ textAlignVertical: 'top' }}
                  placeholder="Tell people a bit about yourself…"
                  placeholderTextColor={colors.inkGhost}
                  value={value ?? ''}
                  onChangeText={onChange}
                  onBlur={() => saveBio(value ?? '')}
                  multiline
                  maxLength={500}
                />
                <Text className="text-xs text-fg-ghost text-right mt-1">
                  {(value ?? '').length}/500
                </Text>
              </View>
            )}
          />
        </ScrollView>
      </BioForm.Form>
    </SafeAreaView>
  );
}

export default function BioScreen() {
  return (
    <ScreenSuspense>
      <BioScreenInner />
    </ScreenSuspense>
  );
}
