// Email magic-link sheet — opened from the login screen's state (no route). Two
// states: the enter-email form (createTypedForm) and the "check your email"
// confirmation. The return hop is handled by the pear://magic-link?token=… deep
// link wired in AuthProvider, so there's nothing more to submit here.
import { useState } from 'react';

import { Text } from '@/lib/tw';
import { Sprout } from '@/components/Sprout';
import { Sheet } from '@/components/Sheet';
import { useAuthActions } from '@/context/auth';
import { createTypedForm, EMAIL_PATTERN } from '@/lib/forms/typed-form';
import { colors } from '@/constants/theme';

type EmailValues = { email: string };

const EmailForm = createTypedForm<EmailValues>();

export function EmailSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const { requestMagicLink } = useAuthActions();

  return (
    <>
      <EmailForm.FormSheet
        visible={visible && !sentTo}
        onClose={onClose}
        title="Sign in with email"
        subtitle="Enter your email and we'll send you a magic link to sign in."
        submitLabel="Send link"
        defaultValues={{ email: '' }}
        onSubmit={async ({ email }) => {
          const normalized = email.trim();
          const { error } = await requestMagicLink(normalized);
          if (error) throw new Error(error.message);
          setSentTo(normalized);
        }}
      >
        <EmailForm.TextField
          name="email"
          label="Email"
          placeholder="you@example.com"
          keyboardType="email-address"
          autoCapitalize="none"
          autoFocus
          rules={{ pattern: EMAIL_PATTERN }}
        />
      </EmailForm.FormSheet>

      <Sheet
        visible={visible && !!sentTo}
        onClose={onClose}
        title="Check your email"
        subtitle={
          sentTo
            ? `We sent a sign-in link to ${sentTo}. Open it on this device to continue.`
            : undefined
        }
        footer={
          <Sprout block size="lg" variant="secondary" onPress={() => setSentTo(null)}>
            Use a different email
          </Sprout>
        }
      >
        <Text style={{ fontSize: 13, color: colors.inkDim, lineHeight: 19 }}>
          The link expires shortly. If it doesn&apos;t arrive, check your spam folder or request a
          new one.
        </Text>
      </Sheet>
    </>
  );
}
