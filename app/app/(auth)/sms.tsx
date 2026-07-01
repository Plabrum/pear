import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import { z } from 'zod';
import { View, Text, Pressable } from '@/lib/tw';
import { sendOTP, verifyOTP } from '@/context/auth';
import { toE164 } from '@/lib/phoneUtils';
import { createForm, RootError, SubmitButton, phoneSchema } from '@/lib/forms';

const phoneFormSchema = z.object({ phone: phoneSchema });
const otpFormSchema = z.object({
  code: z.string().min(6, 'Code must be 6 digits.').max(6, 'Code must be 6 digits.'),
});

const phoneForm = createForm(phoneFormSchema);
const otpForm = createForm(otpFormSchema);

export default function SmsModal() {
  const [step, setStep] = useState<'phone' | 'otp'>('phone');
  const [e164Phone, setE164Phone] = useState('');

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
        {step === 'phone' ? (
          <phoneForm.Form
            defaultValues={{ phone: '' }}
            onSubmit={async ({ phone }) => {
              const normalized = toE164(phone)!;
              const { error } = await sendOTP(normalized);
              if (error) throw new Error(error.message);
              setE164Phone(normalized);
              setStep('otp');
            }}
          >
            <phoneForm.PhoneField name="phone" autoFocus />
            <Text className="text-sm text-fg-subtle mt-1">
              US numbers are auto-detected. Include a country code for international numbers.
            </Text>
            <View className="mt-2">
              <SubmitButton label="Send Code" />
            </View>
            <RootError />
          </phoneForm.Form>
        ) : (
          <otpForm.Form
            defaultValues={{ code: '' }}
            onSubmit={async ({ code }) => {
              const { error } = await verifyOTP(e164Phone, code);
              if (error) throw new Error(error.message);
            }}
          >
            <Text className="text-sm text-fg-muted mt-2">
              We sent a 6-digit code to {e164Phone}
            </Text>
            <otpForm.TextField
              name="code"
              keyboardType="number-pad"
              maxLength={6}
              autoFocus
              placeholder="000000"
            />
            <View className="mt-2 gap-2">
              <SubmitButton label="Verify" />
              <Pressable className="items-center p-[10px]" onPress={() => setStep('phone')}>
                <Text className="text-accent text-sm">Change number</Text>
              </Pressable>
            </View>
            <RootError />
          </otpForm.Form>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
