import { useState } from 'react';
import { FlatList, Modal } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { View, Text, TextInput, Pressable } from '@/lib/tw';
import { Sprout } from '@/components/ui/Sprout';

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

      {pendingContact != null && (
        <View
          style={{
            position: 'absolute',
            inset: 0,
            backgroundColor: 'rgba(31,27,22,0.5)',
            alignItems: 'center',
            justifyContent: 'center',
            paddingHorizontal: 28,
          }}
        >
          <View
            className="bg-background"
            style={{
              borderRadius: 20,
              padding: 24,
              width: '100%',
            }}
          >
            <Text
              className="font-serif text-ink"
              style={{
                fontSize: 22,
                letterSpacing: -0.3,
                marginBottom: 8,
              }}
            >
              Invite {pendingContact.name}?
            </Text>
            <Text style={{ fontSize: 13, color: INK3, lineHeight: 19, marginBottom: 20 }}>
              We{"'"}ll send {pendingContact.name} a text inviting them to be your wingperson on
              Pear.
            </Text>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <View style={{ flex: 1 }}>
                <Sprout block variant="secondary" onPress={() => setPendingContact(null)}>
                  No
                </Sprout>
              </View>
              <View style={{ flex: 1 }}>
                <Sprout
                  block
                  onPress={handleContactConfirm}
                  loading={contactInviting}
                  disabled={contactInviting}
                >
                  Yes, invite
                </Sprout>
              </View>
            </View>
          </View>
        </View>
      )}
    </Modal>
  );
}
