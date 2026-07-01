import ScreenSuspense from '@/components/ui/ScreenSuspense';
import { MatchesList } from '@/components/matches/MatchesList';

export default function MatchesScreen() {
  return (
    <ScreenSuspense>
      <MatchesList />
    </ScreenSuspense>
  );
}
