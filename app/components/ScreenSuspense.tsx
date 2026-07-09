import { Suspense, type ReactNode } from 'react';
import { QueryErrorResetBoundary } from '@tanstack/react-query';
import Splash from '@/components/Splash';
import ScreenErrorBoundary from './ScreenErrorBoundary';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onRetry?: () => void;
}

export default function ScreenSuspense({ children, fallback, onRetry }: Props) {
  // QueryErrorResetBoundary hands us `reset`, which clears the errored suspense
  // queries inside it. Without it, flipping the boundary back would just re-throw
  // the cached query error — the Retry button would do nothing.
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <ScreenErrorBoundary
          onRetry={() => {
            reset();
            onRetry?.();
          }}
        >
          <Suspense fallback={fallback ?? <Splash variant="spinner" />}>{children}</Suspense>
        </ScreenErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  );
}
