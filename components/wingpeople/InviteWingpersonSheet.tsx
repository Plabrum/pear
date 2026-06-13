import { useState } from 'react';
import { KeyboardAvoidingView, Modal, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Controller, useForm } from 'react-hook-form';
import { toast } from 'sonner-native';
import * as SMS from 'expo-sms';
import * as Contacts from 'expo-contacts';
import { useQueryClient } from '@tanstack/react-query';

import { View, Text, TextInput, Pressable } from '@/lib/tw';
import { Sprout } from '@/components/ui/Sprout';
import {
  getGetApiWingpeopleQueryKey,
  usePostApiWingpeopleInvite,
} from '@/lib/api/generated/contacts/contacts';
import { useGetApiProfilesMeSuspense } from '@/lib/api/generated/profiles/profiles';
import { formatPhoneInput, toE164 } from '@/lib/phoneUtils';
import { ContactsPicker, type ContactEntry } from '@/components/wingpeople/ContactsPicker';

const INK3 = '#8B8170';
const LINE = 'rgba(31,27,22,0.10)';

type InviteForm = { phone: string };

type Props = {
  visible: boolean;
  onClose: () => void;
  variant?: 'dater' | 'winger';
};

export function InviteWingpersonSheet({ visible, onClose, variant = 'dater' }: Props) {
  const insets = useSafeAreaInsets();
  const queryClient = useQueryClient();
  const { data: profile } = useGetApiProfilesMeSuspense();

  const [contactsVisible, setContactsVisible] = useState(false);
  const [allContacts, setAllContacts] = useState<ContactEntry[]>([]);

  const inviteMutation = usePostApiWingpeopleInvite();

  const {
    control,
    handleSubmit,
    reset,
    formState: { isSubmitting, isValid },
  } = useForm<InviteForm>({
    defaultValues: { phone: '' },
    mode: 'onChange',
  });

  const close = () => {
    onClose();
    reset();
  };

  const sendInviteToPhone = async (e164: string): Promise<boolean> => {
    const result = await inviteMutation
      .mutateAsync({ data: { phoneNumber: e164 } })
      .catch(() => null);
    if (result == null) {
      toast.error("Couldn't send invite. Try again.");
      return false;
    }
    if (result.wingerId == null) {
      const isAvailable = await SMS.isAvailableAsync();
      if (isAvailable) {
        const daterName = profile?.chosenName ?? 'Someone';
        const appUrl = 'https://apps.apple.com/app/pear/id6744145981';
        await SMS.sendSMSAsync(
          [e164],
          `${daterName} invited you to be their wingperson on Pear! Download the app: ${appUrl}`
        );
      } else {
        toast.error('SMS is not available on this device.');
      }
    }
    queryClient.invalidateQueries({ queryKey: getGetApiWingpeopleQueryKey() });
    return true;
  };

  const onSendInvite = handleSubmit(async ({ phone }) => {
    const e164 = toE164(phone)!;
    const ok = await sendInviteToPhone(e164);
    if (ok) close();
  });

  const openContactsPicker = async () => {
    const { status } = await Contacts.requestPermissionsAsync();
    if (status !== 'granted') {
      toast.error('Contacts permission is required to invite friends.');
      return;
    }
    const { data } = await Contacts.getContactsAsync({
      fields: [Contacts.Fields.PhoneNumbers, Contacts.Fields.Name],
    });
    const entries: ContactEntry[] = [];
    for (const c of data) {
      const name = c.name ?? '';
      if (!name) continue;
      for (const ph of c.phoneNumbers ?? []) {
        const raw = ph.number ?? '';
        const e164 = toE164(raw);
        if (e164) {
          entries.push({ id: `${c.id}-${raw}`, name, phone: e164 });
          break;
        }
      }
    }
    entries.sort((a, b) => a.name.localeCompare(b.name));
    setAllContacts(entries);
    setContactsVisible(true);
  };

  return (
    <>
      <Modal visible={visible} animationType="slide" transparent onRequestClose={close}>
        <View className="flex-1" style={{ backgroundColor: 'rgba(31,27,22,0.45)' }}>
          <Pressable className="flex-1" onPress={close} />
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={{ position: 'absolute', bottom: 0, left: 0, right: 0 }}
          >
            <View
              className="bg-background"
              style={{
                borderTopLeftRadius: 24,
                borderTopRightRadius: 24,
                paddingHorizontal: 20,
                paddingTop: 14,
                paddingBottom: insets.bottom + 24,
              }}
            >
              <View
                style={{
                  alignSelf: 'center',
                  width: 40,
                  height: 4,
                  borderRadius: 2,
                  backgroundColor: LINE,
                  marginBottom: 14,
                }}
              />
              <Text
                className="font-serif text-ink"
                style={{ fontSize: 24, letterSpacing: -0.4, lineHeight: 28 }}
              >
                {variant === 'winger' ? 'Help a friend date better' : 'Invite a wingperson'}
              </Text>
              <Text style={{ fontSize: 13, marginTop: 6, marginBottom: 14, color: INK3 }}>
                {variant === 'winger'
                  ? 'Invite them to Pear and you can start swiping for them.'
                  : 'Enter their phone number — we’ll text them an invite.'}
              </Text>

              <Controller
                control={control}
                name="phone"
                rules={{
                  required: true,
                  validate: (v) => Boolean(toE164(v)) || 'Please enter a valid phone number.',
                }}
                render={({ field: { value, onChange }, fieldState: { error } }) => (
                  <>
                    <TextInput
                      className="bg-surface text-ink"
                      style={{
                        borderWidth: 1,
                        borderColor: LINE,
                        borderRadius: 14,
                        paddingHorizontal: 14,
                        paddingVertical: 14,
                        fontSize: 14,
                      }}
                      placeholder="(555) 000-0000"
                      placeholderTextColor={INK3}
                      keyboardType="phone-pad"
                      value={value}
                      onChangeText={(t) => onChange(formatPhoneInput(t))}
                      autoFocus
                    />
                    {error && (
                      <Text className="text-destructive" style={{ fontSize: 13, marginTop: 6 }}>
                        {error.message}
                      </Text>
                    )}
                  </>
                )}
              />

              <View style={{ marginTop: 14 }}>
                <Sprout
                  block
                  onPress={onSendInvite}
                  loading={isSubmitting}
                  disabled={!isValid || isSubmitting}
                >
                  Send invite
                </Sprout>
              </View>

              <View style={{ marginTop: 10 }}>
                <Sprout block variant="secondary" onPress={openContactsPicker}>
                  Invite from contacts
                </Sprout>
              </View>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>

      <ContactsPicker
        visible={contactsVisible}
        contacts={allContacts}
        onClose={() => setContactsVisible(false)}
        onInvite={async (phone) => {
          const ok = await sendInviteToPhone(phone);
          if (ok) {
            setContactsVisible(false);
            close();
          }
          return ok;
        }}
      />
    </>
  );
}
