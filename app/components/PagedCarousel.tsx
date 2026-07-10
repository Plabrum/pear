import { ReactNode, useState } from 'react';
import { NativeScrollEvent, NativeSyntheticEvent, StyleProp, ViewStyle } from 'react-native';

import { View, ScrollView } from '@/lib/tw';

/**
 * Horizontal paged ScrollView + dot indicator, shared by every "swipe through N
 * cards" spot (discover wing-picks, discover prompt commentary, profile approved
 * responses). Page math is derived from `pageWidth` (the real per-page scroll
 * distance, gap included) rather than the rendered card width, so the dots can't
 * drift out of sync after a few swipes.
 *
 * Renders a fixed-size dot row by default (all dots 6x6, active one recolored).
 * Callers that want the variable-width active-dot look (PromptsTab) pass
 * `showDots={false}` and render their own dot row using the exposed page state
 * isn't needed here — see PromptsTab's `ApprovedResponsesCarousel`.
 */
export function PagedCarousel({
  pageCount,
  pageWidth,
  children,
  snapToInterval,
  contentContainerStyle,
  showDots = true,
  gap = 8,
  onPageChange,
}: {
  pageCount: number;
  pageWidth: number;
  children: ReactNode;
  snapToInterval?: number;
  contentContainerStyle?: StyleProp<ViewStyle>;
  showDots?: boolean;
  gap?: number;
  onPageChange?: (page: number) => void;
}) {
  const [page, setPage] = useState(0);

  const handleScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.round(e.nativeEvent.contentOffset.x / pageWidth);
    setPage(next);
    onPageChange?.(next);
  };

  return (
    <View style={{ gap }}>
      <ScrollView
        horizontal
        pagingEnabled={snapToInterval == null}
        snapToInterval={snapToInterval}
        decelerationRate={snapToInterval != null ? 'fast' : undefined}
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={handleScroll}
        contentContainerStyle={contentContainerStyle}
      >
        {children}
      </ScrollView>
      {showDots && pageCount > 1 ? (
        <View className="flex-row justify-center gap-1.5">
          {Array.from({ length: pageCount }).map((_, i) => (
            <View
              key={i}
              className={i === page ? 'bg-primary' : 'bg-surface-muted'}
              style={{ width: 6, height: 6, borderRadius: 3 }}
            />
          ))}
        </View>
      ) : null}
    </View>
  );
}
