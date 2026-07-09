// Pear field kit — presentational, react-hook-form-agnostic controls styled to the
// designer's `pear-kit` field set. These are the building blocks `createTypedForm`
// (lib/forms/typed-form.tsx) renders.
//
// COLOR CAVEAT: these controls often render inside a <Modal> (Sheet/Dialog/FullSheet),
// where NativeWind CSS-variable color classes are silently dropped (see lib/tw.tsx).
// So ALL colors come from `style` (colors.* == the design's PEAR tokens); className
// is layout-only.
import * as React from 'react';
import { TextInput as RNTextInput, type KeyboardTypeOptions } from 'react-native';
import Ionicons from 'react-native-vector-icons/Ionicons';

import { View, Text, TextInput, Pressable } from '@/lib/tw';
import { colors } from '@/constants/theme';
import { formatPhoneInput } from '@/lib/phoneUtils';
import DateInput from '@/components/ui/DateInput';
import { Sheet } from '@/components/ui/Sheet';

export const FIELD_ERROR = '#A33';

// ── KitField — label + control + hint/error wrapper ──────────────────────────
export function KitField({
  label,
  hint,
  error,
  optional,
  children,
}: {
  label?: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <View style={{ gap: 7 }}>
      {label ? (
        <View
          style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' }}
        >
          <Text
            style={{
              fontSize: 10.5,
              letterSpacing: 1.4,
              textTransform: 'uppercase',
              color: colors.inkDim,
              fontWeight: '600',
            }}
          >
            {label}
          </Text>
          {optional ? (
            <Text style={{ fontSize: 11, color: colors.inkDim, fontStyle: 'italic' }}>
              optional
            </Text>
          ) : null}
        </View>
      ) : null}
      {children}
      {error || hint ? (
        <Text style={{ fontSize: 12, lineHeight: 17, color: error ? FIELD_ERROR : colors.inkDim }}>
          {error || hint}
        </Text>
      ) : null}
    </View>
  );
}

// Shared 52px input visual; border reflects focus (leaf) / error (#A33).
function inputBorder(focused: boolean, invalid?: boolean): string {
  if (invalid) return FIELD_ERROR;
  if (focused) return colors.primary;
  return colors.divider;
}

export type ControlProps = {
  value: any;
  onChange: (v: any) => void;
  invalid?: boolean;
};

// Border + radius + bg live on a wrapping View (with overflow:hidden), NOT on the
// TextInput itself: a 1px border with borderRadius rendered directly on an iOS
// <TextInput> clips/uneven-renders its corners. The TextInput inside is borderless
// and transparent so the shell's rounded background shows through cleanly.
function InputShell({
  focused,
  invalid,
  style,
  children,
}: {
  focused: boolean;
  invalid?: boolean;
  style?: object;
  children: React.ReactNode;
}) {
  return (
    <View
      style={{
        borderWidth: 1,
        borderRadius: 14,
        borderColor: inputBorder(focused, invalid),
        backgroundColor: colors.white,
        overflow: 'hidden',
        ...style,
      }}
    >
      {children}
    </View>
  );
}

// ── Text input ───────────────────────────────────────────────────────────────
export function TextControl({
  value,
  onChange,
  invalid,
  placeholder,
  autoCapitalize,
  keyboardType,
  maxLength,
  autoFocus,
  autoComplete,
}: ControlProps & {
  placeholder?: string;
  autoCapitalize?: 'none' | 'words' | 'sentences' | 'characters';
  keyboardType?: KeyboardTypeOptions;
  maxLength?: number;
  autoFocus?: boolean;
  autoComplete?: React.ComponentProps<typeof TextInput>['autoComplete'];
}) {
  const [focused, setFocused] = React.useState(false);
  return (
    <InputShell focused={focused} invalid={invalid} style={{ height: 52 }}>
      <TextInput
        style={{ height: 52, paddingHorizontal: 14, fontSize: 16, color: colors.ink }}
        placeholder={placeholder}
        placeholderTextColor={colors.inkGhost}
        value={value ?? ''}
        onChangeText={onChange}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        autoCapitalize={autoCapitalize}
        keyboardType={keyboardType}
        maxLength={maxLength}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
      />
    </InputShell>
  );
}

// ── Textarea (char count) ──────────────────────────────────────────────────────
export function TextareaControl({
  value,
  onChange,
  invalid,
  placeholder,
  maxLength,
  autoFocus,
}: ControlProps & { placeholder?: string; maxLength?: number; autoFocus?: boolean }) {
  const [focused, setFocused] = React.useState(false);
  const text: string = value ?? '';
  return (
    <View>
      <InputShell focused={focused} invalid={invalid}>
        <TextInput
          style={{
            minHeight: 96,
            paddingHorizontal: 14,
            paddingVertical: 13,
            fontSize: 15,
            lineHeight: 22,
            color: colors.ink,
            textAlignVertical: 'top',
          }}
          placeholder={placeholder}
          placeholderTextColor={colors.inkGhost}
          value={text}
          onChangeText={onChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          multiline
          maxLength={maxLength}
          autoFocus={autoFocus}
        />
      </InputShell>
      {maxLength != null ? (
        <Text style={{ textAlign: 'right', fontSize: 11, color: colors.inkDim, marginTop: 4 }}>
          {text.length}/{maxLength}
        </Text>
      ) : null}
    </View>
  );
}

// ── Phone input ──────────────────────────────────────────────────────────────
export function PhoneControl({
  value,
  onChange,
  invalid,
  autoFocus,
}: ControlProps & { autoFocus?: boolean }) {
  const [focused, setFocused] = React.useState(false);
  return (
    <InputShell focused={focused} invalid={invalid} style={{ height: 52 }}>
      <TextInput
        style={{ height: 52, paddingHorizontal: 14, fontSize: 16, color: colors.ink }}
        placeholder="(347) 555-0142"
        placeholderTextColor={colors.inkGhost}
        keyboardType="phone-pad"
        autoComplete="tel"
        autoFocus={autoFocus}
        value={value ?? ''}
        onChangeText={(t) => onChange(formatPhoneInput(t))}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
    </InputShell>
  );
}

// ── Date (delegates to the platform-split DateInput) ────────────────────────────
export function DateControl({ value, onChange }: ControlProps) {
  return <DateInput value={value} onChange={onChange} />;
}

// ── Choice chips (single or multi) ──────────────────────────────────────────────
export function ChoiceControl({
  value,
  onChange,
  options,
  multi,
  getLabel,
}: ControlProps & {
  options: readonly string[];
  multi?: boolean;
  getLabel?: (opt: string) => string;
}) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {options.map((opt) => {
        const active = multi ? Array.isArray(value) && value.includes(opt) : value === opt;
        return (
          <Pressable
            key={opt}
            onPress={() => {
              if (multi) {
                const list: string[] = Array.isArray(value) ? value : [];
                onChange(list.includes(opt) ? list.filter((v) => v !== opt) : [...list, opt]);
              } else {
                onChange(opt);
              }
            }}
            style={{
              paddingHorizontal: 16,
              paddingVertical: 10,
              borderRadius: 24,
              borderWidth: 1.5,
              borderColor: active ? colors.primary : colors.divider,
              backgroundColor: active ? colors.primarySoft : colors.white,
            }}
          >
            <Text
              style={{
                fontSize: 14,
                fontWeight: '500',
                color: active ? colors.primary : colors.inkMid,
              }}
            >
              {getLabel ? getLabel(opt) : opt}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export type SelectOption = { value: string | null; label: string };

// ── Select (opens a shared Sheet list) ──────────────────────────────────────────
export function SelectControl({
  value,
  onChange,
  invalid,
  placeholder = 'Select…',
  options,
  title,
}: ControlProps & {
  placeholder?: string;
  options: readonly SelectOption[];
  title?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = options.find((o) => o.value === value);
  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        style={{
          height: 52,
          paddingHorizontal: 14,
          borderWidth: 1,
          borderRadius: 14,
          backgroundColor: colors.white,
          borderColor: inputBorder(false, invalid),
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Text style={{ fontSize: 16, color: selected ? colors.ink : colors.inkGhost }}>
          {selected ? selected.label : placeholder}
        </Text>
        <Ionicons name="chevron-down" size={16} color={colors.inkDim} />
      </Pressable>
      <Sheet visible={open} onClose={() => setOpen(false)} title={title} maxHeight="70%">
        <View>
          {options.map((opt) => {
            const active = opt.value === value;
            return (
              <Pressable
                key={String(opt.value)}
                onPress={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                style={{
                  paddingHorizontal: 4,
                  paddingVertical: 14,
                  flexDirection: 'row',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Text
                  style={{
                    fontSize: 16,
                    color: active ? colors.primary : colors.ink,
                    fontWeight: active ? '600' : '400',
                  }}
                >
                  {opt.label}
                </Text>
                {active ? <Ionicons name="checkmark" size={18} color={colors.primary} /> : null}
              </Pressable>
            );
          })}
        </View>
      </Sheet>
    </>
  );
}

// ── Toggle row ───────────────────────────────────────────────────────────────
export function ToggleControl({
  value,
  onChange,
  label,
  sublabel,
}: ControlProps & { label: string; sublabel?: string }) {
  const on = !!value;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10 }}>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14.5, fontWeight: '500', color: colors.ink }}>{label}</Text>
        {sublabel ? (
          <Text style={{ fontSize: 12, color: colors.inkDim, marginTop: 1 }}>{sublabel}</Text>
        ) : null}
      </View>
      <Pressable
        onPress={() => onChange(!on)}
        style={{
          width: 46,
          height: 28,
          borderRadius: 16,
          backgroundColor: on ? colors.primary : colors.muted,
          padding: 3,
        }}
      >
        <View
          style={{
            width: 22,
            height: 22,
            borderRadius: 11,
            backgroundColor: '#fff',
            transform: [{ translateX: on ? 18 : 0 }],
            shadowColor: '#000',
            shadowOpacity: 0.25,
            shadowRadius: 3,
            shadowOffset: { width: 0, height: 1 },
          }}
        />
      </Pressable>
    </View>
  );
}

// ── Check / radio cell (shared visual) ──────────────────────────────────────────
export function CheckCell({
  label,
  sublabel,
  checked,
  onPress,
  radio,
}: {
  label: string;
  sublabel?: string;
  checked: boolean;
  onPress: () => void;
  radio?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={{
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: 12,
        paddingHorizontal: 14,
        paddingVertical: 12,
        borderRadius: 14,
        borderWidth: 1.5,
        borderColor: checked ? colors.primary : colors.divider,
        backgroundColor: checked ? colors.primarySoft : colors.white,
      }}
    >
      <View
        style={{
          width: 22,
          height: 22,
          marginTop: 1,
          borderRadius: radio ? 11 : 7,
          borderWidth: 1.5,
          borderColor: checked ? colors.primary : colors.inkDim,
          backgroundColor: checked ? colors.primary : 'transparent',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {checked ? (
          radio ? (
            <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: colors.white }} />
          ) : (
            <Ionicons name="checkmark" size={13} color={colors.white} />
          )
        ) : null}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14.5, fontWeight: '500', color: colors.ink }}>{label}</Text>
        {sublabel ? (
          <Text style={{ fontSize: 12.5, color: colors.inkMid, marginTop: 2, lineHeight: 18 }}>
            {sublabel}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

export function CheckControl({
  value,
  onChange,
  label,
  sublabel,
}: ControlProps & { label: string; sublabel?: string }) {
  return (
    <CheckCell
      label={label}
      sublabel={sublabel}
      checked={!!value}
      onPress={() => onChange(!value)}
    />
  );
}

export type RadioOption = { value: string; label: string; sublabel?: string };

export function RadioGroupControl({
  value,
  onChange,
  options,
}: ControlProps & { options: readonly RadioOption[] }) {
  return (
    <View style={{ gap: 8 }}>
      {options.map((o) => (
        <CheckCell
          key={o.value}
          radio
          label={o.label}
          sublabel={o.sublabel}
          checked={value === o.value}
          onPress={() => onChange(o.value)}
        />
      ))}
    </View>
  );
}

// ── OTP boxes (auto-advance, backspace-aware) ────────────────────────────────────
export function OTPControl({
  value,
  onChange,
  invalid,
  length = 6,
}: ControlProps & { length?: number }) {
  const refs = React.useRef<(RNTextInput | null)[]>([]);
  const code: string = value ?? '';
  const set = (i: number, ch: string) => {
    const digit = (ch || '').replace(/\D/g, '').slice(-1);
    const arr = code.padEnd(length, ' ').slice(0, length).split('');
    arr[i] = digit || ' ';
    onChange(arr.map((c) => (c === ' ' ? '' : c)).join(''));
    if (digit) refs.current[i + 1]?.focus();
  };
  return (
    <View style={{ flexDirection: 'row', gap: 8 }}>
      {Array.from({ length }).map((_, i) => {
        const filled = !!code[i];
        return (
          <RNTextInput
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            style={{
              flex: 1,
              height: 60,
              textAlign: 'center',
              fontSize: 26,
              fontWeight: '500',
              color: colors.ink,
              backgroundColor: filled ? '#fff' : colors.white,
              borderWidth: 1,
              borderRadius: 14,
              borderColor: invalid ? FIELD_ERROR : filled ? colors.primary : colors.divider,
            }}
            keyboardType="number-pad"
            maxLength={1}
            value={code[i] ?? ''}
            onChangeText={(ch) => set(i, ch)}
            onKeyPress={({ nativeEvent }) => {
              if (nativeEvent.key === 'Backspace' && !code[i]) {
                refs.current[i - 1]?.focus();
              }
            }}
          />
        );
      })}
    </View>
  );
}
