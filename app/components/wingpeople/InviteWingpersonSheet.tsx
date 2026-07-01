import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { toast } from 'sonner-native';
import * as SMS from 'expo-sms';
import * as Contacts from 'expo-contacts';
import { Ionicons } from '@expo/vector-icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { View } from '@/lib/tw';
import { Sprout } from '@/components/ui/Sprout';
import { Sheet } from '@/components/ui/Sheet';
import { KitField, PhoneControl } from '@/lib/forms/fields';
import { colors } from '@/constants/theme';
import { getGetApiWingpeopleQueryKey } from '@/lib/api/generated/contacts/contacts';
import { inviteWingperson } from '@/lib/api/actions';
import { toastError } from '@/lib/api/error-toast';
import { useGetApiProfilesMeSuspense } from '@/lib/api/generated/profiles/profiles';
import { toE164 } from '@/lib/phoneUtils';
import { ContactsPicker, type ContactEntry } from '@/components/wingpeople/ContactsPicker';

type InviteForm = { phone: string };

type Props = {
  visible: boolean;
  onClose: () => void;
  variant?: 'dater' | 'winger';
};

export function InviteWingpersonSheet({ visible, onClose, variant = 'dater' }: Props) {
  const queryClient = useQueryClient();
  const { data: profile } = useGetApiProfilesMeSuspense();

  const [contactsVisible, setContactsVisible] = useState(false);
  const [allContacts, setAllContacts] = useState<ContactEntry[]>([]);

  const inviteMutation = useMutation({
    mutationFn: (phoneNumber: string) => inviteWingperson({ phoneNumber }),
  });

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
    const result = await inviteMutation.mutateAsync(e164).catch((err) => {
      toastError(err, "Couldn't send invite. Try again.");
      return null;
    });
    if (result == null) {
      return false;
    }
    // The action records the contact (and, when the invitee is already a Pear
    // user, fires a server-side push). The response no longer distinguishes
    // existing vs. new users, so we also offer the SMS invite as the delivery
    // channel for invitees who aren't on Pear yet.
    const isAvailable = await SMS.isAvailableAsync();
    if (isAvailable) {
      const daterName = profile?.chosenName ?? 'Someone';
      const appUrl = 'https://apps.apple.com/app/pear/id6744145981';
      await SMS.sendSMSAsync(
        [e164],
        `${daterName} invited you to be their wingperson on Pear! Download the app: ${appUrl}`
      );
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
      <Sheet
        visible={visible}
        onClose={close}
        title={variant === 'winger' ? 'Help a friend date better' : 'Invite a wingperson'}
        subtitle={
          variant === 'winger'
            ? 'Invite them to Pear and you can start swiping for them.'
            : 'Enter their phone number — we’ll text them an invite.'
        }
        footer={
          <View style={{ gap: 10 }}>
            <Sprout
              block
              size="lg"
              onPress={onSendInvite}
              loading={isSubmitting}
              disabled={!isValid || isSubmitting}
            >
              Send invite
            </Sprout>
            <Sprout
              block
              variant="secondary"
              onPress={openContactsPicker}
              icon={<Ionicons name="people-outline" size={18} color={colors.ink} />}
            >
              Invite from contacts
            </Sprout>
          </View>
        }
      >
        <Controller
          control={control}
          name="phone"
          rules={{
            required: true,
            validate: (v) => Boolean(toE164(v)) || 'Please enter a valid phone number.',
          }}
          render={({ field: { value, onChange }, fieldState: { error } }) => (
            <KitField label="Phone number" error={error?.message}>
              <PhoneControl value={value} onChange={onChange} invalid={!!error} autoFocus />
            </KitField>
          )}
        />
      </Sheet>

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
