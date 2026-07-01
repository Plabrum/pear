import { Suspense, type ReactNode } from 'react';
import Splash from '@/components/ui/Splash';
import ScreenErrorBoundary from './ScreenErrorBoundary';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onRetry?: () => void;
}

export default function ScreenSuspense({ children, fallback, onRetry }: Props) {
  return (
    <ScreenErrorBoundary onRetry={onRetry}>
      <Suspense fallback={fallback ?? <Splash variant="spinner" />}>{children}</Suspense>
    </ScreenErrorBoundary>
  );
}
