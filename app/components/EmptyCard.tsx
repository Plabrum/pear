import type { ReactNode } from 'react';
import { Card } from '@/components/Card';

// Shared dashed paper panel for empty states.
export function EmptyCard({ children }: { children: ReactNode }) {
  return (
    <Card
      className="flex-1 rounded-[22px] border-dashed items-center justify-center"
      style={{ padding: 32, gap: 16 }}
    >
      {children}
    </Card>
  );
}
