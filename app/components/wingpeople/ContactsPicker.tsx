import { useState } from 'react';
import { FlatList, Modal } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { View, Text, TextInput, Pressable } from '@/lib/tw';
import { Dialog } from '@/components/ui/Dialog';

const INK = '#1F1B16';
const INK3 = '#8B8170';
const LINE = 'rgba(31,27,22,0.10)';
const LEAF = '#5A8C3A';
const LEAF_SOFT = 'rgba(90,140,58,0.12)';

export type ContactEntry = { id: string; name: string; phone: string };

type Props = {
  visible: boolean;
  contacts: ContactEntry[];
  onClose: () => void;
  onInvite: (phone: string) => Promise<boolean>;
};

export function ContactsPicker({ visible, contacts, onClose, onInvite }: Props) {
  const insets = useSafeAreaInsets();
  const [contactSearch, setContactSearch] = useState('');
  const [pendingContact, setPendingContact] = useState<ContactEntry | null>(null);
  const [contactInviting, setContactInviting] = useState(false);

  const filteredContacts = contactSearch.trim()
    ? contacts.filter((c) => c.name.toLowerCase().includes(contactSearch.toLowerCase()))
    : contacts;

  const handleContactConfirm = async () => {
    if (!pendingContact) return;
    setContactInviting(true);
    const ok = await onInvite(pendingContact.phone);
    setContactInviting(false);
    setPendingContact(null);
    if (ok) {
      setContactSearch('');
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent={false} onRequestClose={onClose}>
      <View className="flex-1 bg-background">
        <View
          style={{
            paddingTop: insets.top + 8,
            paddingHorizontal: 16,
            paddingBottom: 12,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <Pressable onPress={onClose} hitSlop={12} style={{ padding: 6 }}>
            <Ionicons name="chevron-back" size={22} color={INK} />
          </Pressable>
          <TextInput
            className="bg-surface"
            style={{
              flex: 1,
              borderWidth: 1,
              borderColor: LINE,
              borderRadius: 12,
              paddingHorizontal: 12,
              paddingVertical: 10,
              fontSize: 14,
              color: INK,
            }}
            placeholder="Search contacts…"
            placeholderTextColor={INK3}
            value={contactSearch}
            onChangeText={setContactSearch}
            autoCorrect={false}
          />
        </View>

        <FlatList
          data={filteredContacts}
          keyExtractor={(item) => item.id}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingBottom: insets.bottom + 16 }}
          renderItem={({ item }) => (
            <Pressable
              onPress={() => setPendingContact(item)}
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 12,
                paddingHorizontal: 16,
                paddingVertical: 12,
                borderBottomWidth: 1,
                borderColor: LINE,
              }}
            >
              <View
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 20,
                  backgroundColor: LEAF_SOFT,
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Text style={{ fontSize: 15, fontWeight: '600', color: LEAF }}>
                  {item.name.charAt(0).toUpperCase()}
                </Text>
              </View>
              <Text style={{ flex: 1, fontSize: 15, color: INK }}>{item.name}</Text>
            </Pressable>
          )}
        />
      </View>

      <Dialog
        visible={pendingContact != null}
        onClose={() => !contactInviting && setPendingContact(null)}
        title={pendingContact ? `Invite ${pendingContact.name}?` : undefined}
        body={
          pendingContact
            ? `We'll send ${pendingContact.name} a text inviting them to be your wingperson on Pear.`
            : undefined
        }
        actions={[
          { label: 'Yes, invite', onClick: handleContactConfirm, loading: contactInviting },
          { label: 'No', onClick: () => setPendingContact(null), disabled: contactInviting },
        ]}
      />
    </Modal>
  );
}
