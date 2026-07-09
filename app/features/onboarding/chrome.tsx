import { Pressable, Text, View } from '@/lib/tw';
import { cn } from '@/lib/cn';

// ── Shared onboarding chrome ────────────────────────────────────────

export function BackButton({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} className="self-start mb-3.5 flex-row items-center" hitSlop={8}>
      <Text className="text-foreground-muted" style={{ fontSize: 18, marginRight: 4 }}>
        ‹
      </Text>
      <Text className="text-[13px] text-foreground-muted font-medium">Back</Text>
    </Pressable>
  );
}

export function Progress({ step }: { step: number }) {
  return (
    <View className="flex-row items-center mb-[18px]" style={{ gap: 6 }}>
      {[1, 2, 3, 4].map((s) => (
        <View
          key={s}
          className={cn('flex-1 rounded-[2px]', s <= step ? 'bg-primary' : 'bg-border')}
          style={{ height: 3 }}
        />
      ))}
    </View>
  );
}

export function StepHeader({
  kicker,
  title,
  accent,
  sub,
}: {
  kicker: string;
  title: string;
  accent?: string;
  sub?: string;
}) {
  return (
    <>
      <Text
        className="font-mono text-foreground-subtle uppercase mb-2.5"
        style={{ fontSize: 10.5, letterSpacing: 1.6 }}
      >
        {kicker}
      </Text>
      <Text
        className="font-serif text-foreground"
        style={{ fontSize: 28, lineHeight: 30, letterSpacing: -0.7 }}
      >
        {title}
        {accent ? (
          <Text
            className="font-serif text-primary"
            style={{ fontSize: 28, lineHeight: 30, letterSpacing: -0.7, fontStyle: 'italic' }}
          >
            {' '}
            {accent}
          </Text>
        ) : null}
        .
      </Text>
      {sub ? (
        <Text className="text-sm text-foreground-muted mt-2.5 leading-[21px]">{sub}</Text>
      ) : null}
    </>
  );
}

export function MonoLabel({ children }: { children: React.ReactNode }) {
  return (
    <Text
      className="font-mono text-foreground-subtle uppercase mb-1.5"
      style={{ fontSize: 10.5, letterSpacing: 1.4 }}
    >
      {children}
    </Text>
  );
}

export function ChipRow<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly T[];
  value: T | null;
  onChange: (v: T) => void;
}) {
  return (
    <View className="flex-row flex-wrap" style={{ gap: 6 }}>
      {options.map((opt) => {
        const active = value === opt;
        return (
          <Pressable
            key={opt}
            onPress={() => onChange(opt)}
            className={cn(
              'h-[30px] px-3 rounded-full items-center justify-center border',
              active ? 'bg-primary-soft border-transparent' : 'bg-transparent border-border'
            )}
          >
            <Text
              className={cn(
                'text-[12.5px] font-medium',
                active ? 'text-primary' : 'text-foreground-muted'
              )}
            >
              {opt}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
