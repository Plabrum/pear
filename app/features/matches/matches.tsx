import ScreenSuspense from '@/components/ScreenSuspense';
import { MatchesList } from '@/features/matches/MatchesList';

export default function MatchesScreen() {
  return (
    <ScreenSuspense>
      <MatchesList />
    </ScreenSuspense>
  );
}
