import * as React from 'react';
import { StyleSheet, type KeyboardTypeOptions } from 'react-native';
import PulseSpinner from '@/components/ui/PulseSpinner';
import {
  Controller,
  FormProvider,
  useForm,
  useFormContext,
  type DefaultValues,
  type FieldPath,
  type FieldValues,
} from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner-native';

import { Modal, Pressable, ScrollView, Text, TextInput, View } from '@/lib/tw';
import { cn } from '@/lib/cn';
import { colors } from '@/constants/theme';
import { formatPhoneInput, toE164 } from '@/lib/phoneUtils';
import DateInput from '@/components/ui/DateInput';

const FormSubmitContext = React.createContext<(() => void) | null>(null);

const inputClass =
  'bg-white rounded-xl border-[1.5px] border-separator px-4 py-[14px] text-base text-fg';

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <Text className="text-sm font-semibold text-fg-muted uppercase tracking-[0.5px] mb-2 mt-5">
      {children}
    </Text>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <Text className="text-error text-sm mt-1.5">{message}</Text>;
}

export const phoneSchema = z
  .string()
  .refine((v) => toE164(v) !== null, 'Enter a valid phone number');

export function createForm<TSchema extends z.ZodTypeAny>(schema: TSchema) {
  type Values = z.infer<TSchema> extends FieldValues ? z.infer<TSchema> : never;
  type Name = FieldPath<Values>;

  function Form({
    defaultValues,
    onSubmit,
    children,
  }: {
    defaultValues: DefaultValues<Values>;
    onSubmit: (values: Values) => Promise<void> | void;
    children: React.ReactNode;
  }) {
    const methods = useForm<Values>({
      defaultValues,
      mode: 'onChange',

      resolver: zodResolver(schema as any) as never,
    });

    const submit = methods.handleSubmit(async (values) => {
      try {
        await onSubmit(values);
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Something went wrong';
        methods.setError('root', { message: msg });
        toast.error(msg);
      }
    });

    return (
      <FormProvider {...methods}>
        <FormSubmitContext.Provider value={submit}>{children}</FormSubmitContext.Provider>
      </FormProvider>
    );
  }

  type RenderProps = {
    value: any;
    onChange: (v: any) => void;
    invalid: boolean;
    error?: string;
  };

  function Field<N extends Name>({
    name,
    label,
    render,
    showError = true,
  }: {
    name: N;
    label?: string;
    render: (props: RenderProps) => React.ReactElement;
    showError?: boolean;
  }) {
    const { control } = useFormContext<Values>();
    return (
      <Controller
        control={control}
        name={name}
        render={({ field, fieldState }) => (
          <View>
            {label && <FieldLabel>{label}</FieldLabel>}
            {render({
              value: field.value,
              onChange: field.onChange,
              invalid: !!fieldState.error,
              error: fieldState.error?.message,
            })}
            {showError && <FieldError message={fieldState.error?.message} />}
          </View>
        )}
      />
    );
  }

  function TextField<N extends Name>({
    name,
    label,
    placeholder,
    multiline,
    autoCapitalize,
    keyboardType,
    maxLength,
    autoFocus,
    showCount,
    minHeightClass = 'min-h-[100px]',
  }: {
    name: N;
    label?: string;
    placeholder?: string;
    multiline?: boolean;
    autoCapitalize?: 'none' | 'words' | 'sentences' | 'characters';
    keyboardType?: KeyboardTypeOptions;
    maxLength?: number;
    autoFocus?: boolean;
    showCount?: boolean;
    minHeightClass?: string;
  }) {
    return (
      <Field
        name={name}
        label={label}
        render={({ value, onChange, invalid }) => (
          <View>
            <TextInput
              className={cn(inputClass, multiline && minHeightClass, invalid && 'border-error')}
              style={multiline ? { textAlignVertical: 'top' } : undefined}
              placeholder={placeholder}
              placeholderTextColor={colors.inkGhost}
              value={value ?? ''}
              onChangeText={onChange}
              autoCapitalize={autoCapitalize}
              keyboardType={keyboardType}
              maxLength={maxLength}
              autoFocus={autoFocus}
              multiline={multiline}
            />
            {showCount && maxLength ? (
              <Text className="text-xs text-fg-ghost text-right mt-1">
                {(value ?? '').length}/{maxLength}
              </Text>
            ) : null}
          </View>
        )}
      />
    );
  }

  function PhoneField<N extends Name>({
    name,
    label,
    autoFocus,
  }: {
    name: N;
    label?: string;
    autoFocus?: boolean;
  }) {
    return (
      <Field
        name={name}
        label={label}
        render={({ value, onChange, invalid }) => (
          <TextInput
            className={cn(inputClass, invalid && 'border-error')}
            placeholder="(555) 000-0000"
            placeholderTextColor={colors.inkGhost}
            keyboardType="phone-pad"
            autoComplete="tel"
            autoFocus={autoFocus}
            value={value ?? ''}
            onChangeText={(text) => onChange(formatPhoneInput(text))}
          />
        )}
      />
    );
  }

  function DateField<N extends Name>({ name, label }: { name: N; label?: string }) {
    return (
      <Field
        name={name}
        label={label}
        render={({ value, onChange }) => <DateInput value={value} onChange={onChange} />}
      />
    );
  }

  function ChoiceField<N extends Name>({
    name,
    label,
    options,
    multi,
    getLabel,
  }: {
    name: N;
    label?: string;
    options: readonly string[];
    multi?: boolean;
    getLabel?: (opt: string) => string;
  }) {
    return (
      <Field
        name={name}
        label={label}
        render={({ value, onChange }) => (
          <View className="flex-row flex-wrap gap-2">
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
                  className={cn(
                    'px-4 py-[10px] rounded-[24px] border-[1.5px] border-separator bg-white',
                    active && 'border-accent bg-accent-muted'
                  )}
                >
                  <Text
                    className={cn('text-sm text-fg-muted font-medium', active && 'text-accent')}
                  >
                    {getLabel ? getLabel(opt) : opt}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        )}
      />
    );
  }

  function SelectSheetField<N extends Name>({
    name,
    label,
    placeholder = 'Select…',
    options,
  }: {
    name: N;
    label?: string;
    placeholder?: string;
    options: readonly { value: string | null; label: string }[];
  }) {
    const [open, setOpen] = React.useState(false);
    return (
      <Field
        name={name}
        label={label}
        render={({ value, onChange, invalid }) => {
          const selected = options.find((o) => o.value === value);
          return (
            <>
              <Pressable
                onPress={() => setOpen(true)}
                className={cn(
                  inputClass,
                  'flex-row items-center justify-between',
                  invalid && 'border-error'
                )}
              >
                <Text className={selected ? 'text-base text-fg' : 'text-base text-fg-ghost'}>
                  {selected ? selected.label : placeholder}
                </Text>
                <Text className="text-fg-ghost">▾</Text>
              </Pressable>
              <Modal
                visible={open}
                transparent
                animationType="slide"
                onRequestClose={() => setOpen(false)}
              >
                <View
                  style={{
                    flex: 1,
                    justifyContent: 'flex-end',
                    backgroundColor: 'rgba(0,0,0,0.3)',
                  }}
                >
                  <View
                    style={{ maxHeight: '70%', backgroundColor: 'white' }}
                    className="rounded-t-[20px] pb-8"
                  >
                    <View
                      className="flex-row justify-end p-4"
                      style={{
                        borderBottomWidth: StyleSheet.hairlineWidth,
                        borderBottomColor: colors.divider,
                      }}
                    >
                      <Pressable onPress={() => setOpen(false)}>
                        <Text className="text-accent text-base font-semibold">Done</Text>
                      </Pressable>
                    </View>
                    <ScrollView>
                      {options.map((opt) => {
                        const active = opt.value === value;
                        return (
                          <Pressable
                            key={String(opt.value)}
                            onPress={() => {
                              onChange(opt.value);
                              setOpen(false);
                            }}
                            className={cn(
                              'px-5 py-4 flex-row items-center',
                              active && 'bg-accent-muted'
                            )}
                          >
                            <Text
                              className={cn(
                                'text-base text-fg',
                                active && 'text-accent font-semibold'
                              )}
                            >
                              {opt.label}
                            </Text>
                          </Pressable>
                        );
                      })}
                    </ScrollView>
                  </View>
                </View>
              </Modal>
            </>
          );
        }}
      />
    );
  }

  return { Form, Field, TextField, PhoneField, DateField, ChoiceField, SelectSheetField };
}

type ButtonVariant = 'solid' | 'outline' | 'ghost' | 'destructive';

const variantStyles: Record<ButtonVariant, { box: string; text: string; spinner: string }> = {
  solid: {
    box: 'bg-accent rounded-xl py-[15px] px-6 items-center justify-center',
    text: 'text-white text-base font-semibold',
    spinner: 'white',
  },
  outline: {
    box: 'bg-transparent border-[1.5px] border-accent rounded-xl py-[15px] px-6 items-center justify-center',
    text: 'text-accent text-base font-semibold',
    spinner: colors.primary,
  },
  ghost: {
    box: 'bg-transparent rounded-xl py-[15px] px-6 items-center justify-center',
    text: 'text-accent text-base font-semibold',
    spinner: colors.primary,
  },
  destructive: {
    box: 'bg-error rounded-xl py-[15px] px-6 items-center justify-center',
    text: 'text-white text-base font-semibold',
    spinner: 'white',
  },
};

export function useFormSubmit() {
  const submit = React.useContext(FormSubmitContext);
  const { formState } = useFormContext();
  return {
    submit: submit ?? (() => {}),
    isValid: formState.isValid,
    isSubmitting: formState.isSubmitting,
  };
}

export function SubmitButton({
  label,
  variant = 'solid',
  disableUntilValid = true,
}: {
  label: string;
  variant?: ButtonVariant;
  disableUntilValid?: boolean;
}) {
  const submit = React.useContext(FormSubmitContext);
  const { formState } = useFormContext();
  const { isValid, isSubmitting } = formState;
  const disabled = (disableUntilValid && !isValid) || isSubmitting;
  const styles = variantStyles[variant];
  return (
    <Pressable
      className={cn(styles.box, disabled && 'opacity-40')}
      disabled={disabled}
      onPress={submit ?? undefined}
    >
      {isSubmitting ? (
        <PulseSpinner color={styles.spinner} />
      ) : (
        <Text className={styles.text}>{label}</Text>
      )}
    </Pressable>
  );
}

export function RootError() {
  const { formState } = useFormContext();
  const message = formState.errors.root?.message;
  if (!message) return null;
  return <Text className="text-error text-sm mt-2 text-center">{String(message)}</Text>;
}
