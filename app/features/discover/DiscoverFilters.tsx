import React from 'react';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { Text, View, Pressable } from '@/lib/tw';
import { colors } from '@/constants/theme';
import { PearMark } from '@/components/PearMark';
import type { Filter } from './constants';

type FilterDef = {
  key: Filter;
  label: string;
  tone: 'ink' | 'leaf';
  icon: (color: string) => React.ReactElement;
};

export const FILTERS: FilterDef[] = [
  {
    key: 'likes',
    label: 'Likes you',
    tone: 'ink',
    icon: (color) => <Ionicons name="heart" size={12} color={color} />,
  },
  {
    key: 'handpicked',
    label: 'Hand-picked',
    tone: 'leaf',
    icon: (color) => <PearMark size={13} color={color} variant="flat" />,
  },
];

export function DiscoverFilters({
  active,
  onToggle,
  onClearAll,
  counts,
}: {
  active: Filter[];
  onToggle: (key: Filter) => void;
  onClearAll: () => void;
  counts: Partial<Record<Filter, number>>;
}) {
  return (
    <View className="flex-row items-center flex-wrap px-4 pt-1 pb-3 gap-2">
      <Pressable onPress={onClearAll} disabled={active.length === 0}>
        <Text className="text-[13px] text-foreground-muted font-medium mr-1">For you</Text>
      </Pressable>
      <Text className="text-foreground-subtle text-xs">·</Text>
      {FILTERS.map((f) => {
        const on = active.includes(f.key);
        const activeBg = f.tone === 'leaf' ? colors.leaf : colors.ink;
        const activeFg = colors.white;
        const fg = on ? activeFg : colors.ink;
        const count = counts[f.key];
        return (
          <Pressable
            key={f.key}
            onPress={() => onToggle(f.key)}
            className="flex-row items-center justify-center"
            style={{
              height: 32,
              paddingLeft: 8,
              paddingRight: 12,
              borderRadius: 18,
              borderWidth: 1,
              borderColor: on ? activeBg : colors.divider,
              backgroundColor: on ? activeBg : colors.white,
              gap: 5,
            }}
          >
            {f.icon(fg)}
            <Text style={{ color: fg, fontSize: 12.5, fontWeight: '600' }}>{f.label}</Text>
            {count != null && (
              <View
                style={{
                  backgroundColor: on ? colors.overlayWhite22 : colors.muted,
                  borderRadius: 8,
                  height: 16,
                  minWidth: 16,
                  paddingHorizontal: 6,
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginLeft: 2,
                }}
              >
                <Text
                  style={{
                    color: on ? activeFg : colors.inkDim,
                    fontSize: 10.5,
                    fontWeight: '700',
                  }}
                >
                  {count}
                </Text>
              </View>
            )}
          </Pressable>
        );
      })}
    </View>
  );
}
