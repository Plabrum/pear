import { Image, StyleSheet } from 'react-native';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { View, Text, Pressable } from '@/lib/tw';
import { colors } from '@/constants/theme';
import type { SwipeProfile } from '@/lib/api/generated/model';
import { Sprout } from '@/components/Sprout';

export function MatchOverlay({
  card,
  onClose,
  onMessage,
}: {
  card: SwipeProfile;
  onClose: () => void;
  onMessage: () => void;
}) {
  return (
    <View
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 50,
        backgroundColor: colors.canvas,
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: 28,
      }}
    >
      <View style={{ position: 'absolute', top: 56, right: 20 }}>
        <Pressable
          onPress={onClose}
          style={{
            width: 38,
            height: 38,
            borderRadius: 19,
            backgroundColor: colors.white,
            borderWidth: 1,
            borderColor: colors.divider,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Ionicons name="close" size={18} color={colors.ink} />
        </Pressable>
      </View>

      <Text
        className="text-primary"
        style={{
          fontSize: 11,
          letterSpacing: 2,
          textTransform: 'uppercase',
          marginBottom: 8,
          fontWeight: '600',
        }}
      >
        Mutual taste detected
      </Text>
      <Text
        className="text-ink"
        style={{
          fontFamily: 'DMSerifDisplay',
          fontSize: 56,
          lineHeight: 60,
          letterSpacing: -1.5,
          textAlign: 'center',
        }}
      >
        It’s a{' '}
        <Text className="text-primary" style={{ fontStyle: 'italic' }}>
          pear
        </Text>
        .
      </Text>

      <View style={{ flexDirection: 'row', marginTop: 36, marginBottom: 20 }}>
        <View
          style={{
            width: 118,
            height: 152,
            borderRadius: 20,
            overflow: 'hidden',
            transform: [{ rotate: '-4deg' }],
            borderWidth: 3,
            borderColor: colors.white,
            backgroundColor: colors.muted,
          }}
        >
          <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.muted }]} />
        </View>
        <View
          style={{
            width: 118,
            height: 152,
            borderRadius: 20,
            overflow: 'hidden',
            transform: [{ rotate: '4deg' }, { translateX: -14 }],
            borderWidth: 3,
            borderColor: colors.white,
            backgroundColor: colors.muted,
          }}
        >
          {card.photos[0] ? (
            <Image
              source={{ uri: card.photos[0].url }}
              style={StyleSheet.absoluteFill}
              resizeMode="cover"
            />
          ) : (
            <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.muted }]} />
          )}
        </View>
      </View>

      <Text
        className="text-ink-mid"
        style={{
          fontSize: 15,
          textAlign: 'center',
          maxWidth: 280,
          lineHeight: 22,
          marginBottom: 24,
        }}
      >
        You and {card.chosenName} both swiped right.
        {card.suggestions[0]?.wingerName != null
          ? ` ${card.suggestions[0].wingerName} called it.`
          : ''}
      </Text>

      <View style={{ width: '100%', maxWidth: 320, gap: 10 }}>
        <Sprout block size="lg" onPress={onMessage}>
          Send a message
        </Sprout>
        <Sprout block size="lg" variant="secondary" onPress={onClose}>
          Keep swiping
        </Sprout>
      </View>
    </View>
  );
}
