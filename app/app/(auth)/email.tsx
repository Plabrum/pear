import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import { z } from 'zod';
import { View, Text, Pressable } from '@/lib/tw';
import { useAuthActions } from '@/context/auth';
import { createForm, RootError, SubmitButton } from '@/lib/forms';

const emailFormSchema = z.object({
  email: z.string().trim().email('Enter a valid email address.'),
});

const emailForm = createForm(emailFormSchema);

export default function EmailModal() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const { requestMagicLink } = useAuthActions();

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={{ padding: 24, gap: 8 }}
        keyboardShouldPersistTaps="handled"
      >
        {sentTo ? (
          // "Check your email" state — the return hop is handled by the
          // pear://magic-link?token=... deep link wired in AuthProvider, so
          // there's nothing more to submit here.
          <View className="gap-2">
            <Text className="text-2xl font-serif text-fg">Check your email</Text>
            <Text className="text-base text-fg-muted mt-1">
              We sent a sign-in link to {sentTo}. Open it on this device to continue.
            </Text>
            <Text className="text-sm text-fg-subtle mt-2">
              The link expires shortly. If it doesn&apos;t arrive, check your spam folder or
              request a new one.
            </Text>
            <Pressable className="items-center p-[10px] mt-2" onPress={() => setSentTo(null)}>
              <Text className="text-accent text-sm">Use a different email</Text>
            </Pressable>
          </View>
        ) : (
          <emailForm.Form
            defaultValues={{ email: '' }}
            onSubmit={async ({ email }) => {
              const normalized = email.trim();
              const { error } = await requestMagicLink(normalized);
              if (error) throw new Error(error.message);
              setSentTo(normalized);
            }}
          >
            <Text className="text-base text-fg-muted mt-2">
              Enter your email and we&apos;ll send you a magic link to sign in.
            </Text>
            <emailForm.TextField
              name="email"
              keyboardType="email-address"
              autoCapitalize="none"
              autoFocus
              placeholder="you@example.com"
            />
            <View className="mt-2">
              <SubmitButton label="Send Link" />
            </View>
            <RootError />
          </emailForm.Form>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
