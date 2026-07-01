import * as AppleAuthentication from 'expo-apple-authentication';
import { Platform } from 'react-native';
import { toast } from 'sonner-native';
import { View, Text } from '@/lib/tw';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { PearMark } from '@/components/ui/PearMark';
import { Sprout } from '@/components/ui/Sprout';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { supabase } from '@/lib/supabase';

const LEAF = '#5A8C3A';
const LEAF2 = '#7BAE52';
const SKIN = '#E8C77A';
const BLUSH = '#E9A6A0';

export default function LoginScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  const handleAppleSignIn = async () => {
    if (Platform.OS !== 'ios') return;
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });

      if (!credential.identityToken) {
        toast.error('Apple sign-in did not return an identity token.');
        return;
      }

      const { error } = await supabase.auth.signInWithIdToken({
        provider: 'apple',
        token: credential.identityToken,
      });

      if (error) {
        toast.error(error.message);
        return;
      }

      if (credential.fullName) {
        const parts = [
          credential.fullName.givenName,
          credential.fullName.middleName,
          credential.fullName.familyName,
        ].filter(Boolean);

        if (parts.length > 0) {
          await supabase.auth.updateUser({
            data: {
              full_name: parts.join(' '),
              given_name: credential.fullName.givenName,
              family_name: credential.fullName.familyName,
            },
          });
        }
      }
    } catch (e: any) {
      if (e.code === 'ERR_REQUEST_CANCELED') return;
      console.error('Apple sign-in error:', e);
      toast.error(e.message ?? 'Apple sign-in failed');
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
            <PearMark size={104} color={LEAF2} leaf={LEAF} />
          </View>
          <View style={{ position: 'absolute', top: 0, left: 92, transform: [{ rotate: '8deg' }] }}>
            <PearMark size={132} color={SKIN} leaf={LEAF} />
          </View>
          <View
            style={{ position: 'absolute', top: 70, left: 168, transform: [{ rotate: '-4deg' }] }}
          >
            <PearMark size={68} color={BLUSH} leaf={LEAF} />
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
        <Sprout
          block
          size="lg"
          icon={<IconSymbol name="applelogo" size={18} color="#FBF8F1" />}
          onPress={handleAppleSignIn}
        >
          Continue with Apple
        </Sprout>
        <View className="flex-row" style={{ gap: 10 }}>
          <View className="flex-1">
            <Sprout
              block
              size="lg"
              variant="secondary"
              icon={<IconSymbol name="phone.fill" size={16} color="#1F1B16" />}
              onPress={() => router.push('/(auth)/sms')}
            >
              Phone
            </Sprout>
          </View>
        </View>
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
    </View>
  );
}
