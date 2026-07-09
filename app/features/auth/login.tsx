import { useState } from 'react';
import { NativeModules, Platform } from 'react-native';
import { toast } from 'sonner-native';
import { View, Text } from '@/lib/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { PearMark } from '@/components/PearMark';
import { Button } from '@/components/Button';
import { IconSymbol } from '@/components/icon-symbol';
import { EmailSheet } from '@/features/auth/EmailSheet';
import { useAuthActions } from '@/context/auth';
import { toastError } from '@/lib/api/error-toast';
import { colors } from '@/constants/theme';

// Decorative PearMark fills (SVG color props — escape-hatch hex, no token).
const LEAF2 = '#7BAE52';
const SKIN = '#E8C77A';
const BLUSH = '#E9A6A0';

export default function LoginScreen() {
  const insets = useSafeAreaInsets();
  const { signInWithApple } = useAuthActions();
  const [emailOpen, setEmailOpen] = useState(false);

  const handleAppleSignIn = async () => {
    if (Platform.OS !== 'ios') return;
    try {
      const credential = await NativeModules.PearAppleAuthModule.signIn();
      if (!credential) return; // user cancelled

      if (!credential.identityToken) {
        toast.error('Apple sign-in did not return an identity token.');
        return;
      }

      const fullName = [credential.givenName, credential.middleName, credential.familyName]
        .filter(Boolean)
        .join(' ');

      const { error } = await signInWithApple(
        credential.identityToken,
        fullName.length > 0 ? fullName : undefined
      );

      if (error) {
        toastError(error);
        return;
      }
    } catch (e: any) {
      toastError(e, 'Apple sign-in failed');
    }
  };

  return (
    <View
      className="flex-1 bg-background"
      style={{ paddingTop: insets.top + 24, paddingBottom: insets.bottom + 16 }}
    >
      <View className="absolute" style={{ top: insets.top + 54, right: -28 }} pointerEvents="none">
        <View style={{ width: 240, height: 200 }}>
          <View
            style={{ position: 'absolute', top: 30, left: 18, transform: [{ rotate: '-14deg' }] }}
          >
            <PearMark size={104} color={LEAF2} leaf={colors.leaf} />
          </View>
          <View style={{ position: 'absolute', top: 0, left: 92, transform: [{ rotate: '8deg' }] }}>
            <PearMark size={132} color={SKIN} leaf={colors.leaf} />
          </View>
          <View
            style={{ position: 'absolute', top: 70, left: 168, transform: [{ rotate: '-4deg' }] }}
          >
            <PearMark size={68} color={BLUSH} leaf={colors.leaf} />
          </View>
        </View>
      </View>

      <View className="flex-row items-center px-7" style={{ gap: 9 }}>
        <PearMark size={28} />
        <Text
          className="text-foreground"
          style={{ fontFamily: 'DMSerifDisplay', fontSize: 22, letterSpacing: -0.4 }}
        >
          Pear
        </Text>
      </View>

      <View className="flex-1 justify-end px-7" style={{ paddingBottom: 28 }}>
        <Text className="text-primary mb-3.5" style={{ fontSize: 10.5, letterSpacing: 2 }}>
          DATING · WITH A SECOND OPINION
        </Text>
        <Text
          className="text-foreground"
          style={{
            fontFamily: 'DMSerifDisplay',
            fontSize: 60,
            lineHeight: 68,
            letterSpacing: -1.8,
          }}
        >
          Bring a{'\n'}
          <Text
            className="text-primary"
            style={{
              fontFamily: 'DMSerifDisplay',
              fontStyle: 'italic',
              fontSize: 60,
              lineHeight: 68,
              letterSpacing: -1.8,
            }}
          >
            friend
          </Text>
          {'\n'}along.
        </Text>
        <Text
          className="text-foreground-muted mt-4"
          style={{ fontSize: 15.5, lineHeight: 23, maxWidth: 300 }}
        >
          Your friends already have opinions about who you should date. We gave them a button.
        </Text>
      </View>

      <View className="px-7" style={{ gap: 10 }}>
        <Button
          block
          size="lg"
          icon={<IconSymbol name="applelogo" size={18} color={colors.white} />}
          onPress={handleAppleSignIn}
        >
          Continue with Apple
        </Button>
        <Button
          block
          size="lg"
          variant="secondary"
          icon={<IconSymbol name="envelope.fill" size={16} color={colors.ink} />}
          onPress={() => setEmailOpen(true)}
        >
          Email
        </Button>
        <Text
          className="text-foreground-subtle text-center mt-2"
          style={{ fontSize: 11, lineHeight: 17 }}
        >
          By continuing you agree to our Terms & Privacy.{'\n'}
          <Text className="text-foreground-subtle" style={{ fontSize: 11, opacity: 0.85 }}>
            Wingpeople can see what you swipe on. Yes, really.
          </Text>
        </Text>
      </View>

      <EmailSheet visible={emailOpen} onClose={() => setEmailOpen(false)} />
    </View>
  );
}
