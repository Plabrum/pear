// createTypedForm — a typed, COMPOSABLE form builder over react-hook-form.
//
// Generic over a GENERATED action-data interface (`SuggestActionData`, …) so a form is
// typed end-to-end to the API contract: rename a contract field and the build breaks.
// Validation is RHF-NATIVE — per-field `rules` (`required`, `pattern`, `validate`), no
// zod. Backend types own the shape; the backend owns the real validation. Forms
// validate on submit (`mode: 'onSubmit'`) and surface inline errors; the submit button
// is gated on `isSubmitting` only, never `isValid`.
//
// The builder is PRESENTATION-AGNOSTIC. `Form` renders inline (FormProvider + a submit
// context — RN has no <form>), and you compose field components as children:
//
//   const F = createTypedForm<EmailValues>();
//   <F.Form defaultValues={{ email: '' }} onSubmit={…}>
//     <F.TextField name="email" label="Email" rules={{ pattern: EMAIL_PATTERN }} />
//     <F.SubmitButton label="Send link" />
//   </F.Form>
//
// For a modal form, the optional `FormSheet` / `FormDialog` / `FormFullSheet` wrappers
// compose that same `Form` inside the Pear Sheet/Dialog/FullSheet shells with a sticky
// SubmitButton footer. For a bespoke inline CTA use the `useSubmit()` hook.
import * as React from 'react';
import {
  Controller,
  FormProvider,
  useForm,
  useFormContext,
  useFormState,
  type DefaultValues,
  type FieldPath,
  type FieldValues,
  type RegisterOptions,
  type UseFormProps,
} from 'react-hook-form';
import { type KeyboardTypeOptions } from 'react-native';

import { View } from '@/lib/tw';
import { toastError } from '@/lib/api/error-toast';
import { Sprout } from '@/components/Sprout';
import { Sheet } from '@/components/Sheet';
import { Dialog } from '@/components/Dialog';
import { FullSheet } from '@/components/FullSheet';
import {
  KitField,
  TextControl,
  TextareaControl,
  PhoneControl,
  DateControl,
  ChoiceControl,
  SelectControl,
  ToggleControl,
  CheckControl,
  RadioGroupControl,
  OTPControl,
  type ControlProps,
  type SelectOption,
  type RadioOption,
} from '@/lib/forms/fields';

/** Standard email-format pattern for a text field's `pattern` rule. */
export const EMAIL_PATTERN = {
  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  message: 'Enter a valid email address.',
} as const;

export function createTypedForm<TData extends FieldValues>() {
  type Name = FieldPath<TData>;

  // RN has no <form>/submit event, so the inline `Form` publishes its submit handler
  // through context; `SubmitButton` / `useSubmit` consume it.
  const SubmitContext = React.createContext<(() => void) | null>(null);

  // Shared rhf wiring used by both the inline `Form` and the modal wrappers.
  function useFormCore(
    defaultValues: DefaultValues<TData> | undefined,
    onSubmit: (values: TData) => Promise<void> | void,
    mode: UseFormProps<TData>['mode']
  ) {
    const methods = useForm<TData>({ defaultValues, mode, reValidateMode: 'onChange' });
    const submit = methods.handleSubmit(async (values) => {
      try {
        await onSubmit(values as TData);
      } catch (e) {
        toastError(e);
      }
    });
    return { methods, submit };
  }

  // ── Inline base ────────────────────────────────────────────────────────────────
  function Form({
    defaultValues,
    onSubmit,
    mode = 'onSubmit',
    children,
  }: {
    defaultValues?: DefaultValues<TData>;
    onSubmit: (values: TData) => Promise<void> | void;
    mode?: UseFormProps<TData>['mode'];
    children: React.ReactNode;
  }) {
    const { methods, submit } = useFormCore(defaultValues, onSubmit, mode);
    return (
      <FormProvider {...methods}>
        <SubmitContext.Provider value={submit}>{children}</SubmitContext.Provider>
      </FormProvider>
    );
  }

  /** Imperative submit + isSubmitting for a bespoke inline CTA. */
  function useSubmit() {
    const submit = React.useContext(SubmitContext);
    const { isSubmitting } = useFormState<TData>();
    return { submit: submit ?? (() => {}), isSubmitting };
  }

  // ── Field plumbing ───────────────────────────────────────────────────────────
  type FieldBase<N extends Name> = {
    name: N;
    label?: string;
    hint?: string;
    /** Skip the implicit `required` rule and show an "optional" badge. */
    optional?: boolean;
    /** Override the required-rule message (default "This field is required"). */
    requiredMessage?: string;
    /** Extra RHF rules — pattern / validate / etc. */
    rules?: RegisterOptions<TData, N>;
  };

  function rulesFor<N extends Name>(p: FieldBase<N>): RegisterOptions<TData, N> {
    return {
      required: p.optional ? undefined : (p.requiredMessage ?? 'This field is required'),
      ...p.rules,
    } as RegisterOptions<TData, N>;
  }

  // Controls that render their own inline label (no KitField label above).
  function FieldShell<N extends Name>({
    field,
    selfLabeled = false,
    render,
  }: {
    field: FieldBase<N>;
    selfLabeled?: boolean;
    render: (props: ControlProps) => React.ReactElement;
  }) {
    const { control } = useFormContext<TData>();
    return (
      <Controller
        control={control}
        name={field.name}
        rules={rulesFor(field)}
        render={({ field: f, fieldState }) => {
          const ctl = render({ value: f.value, onChange: f.onChange, invalid: !!fieldState.error });
          if (selfLabeled) return ctl;
          return (
            <KitField
              label={field.label}
              optional={field.optional}
              hint={field.hint}
              error={fieldState.error?.message}
            >
              {ctl}
            </KitField>
          );
        }}
      />
    );
  }

  // ── Field components ─────────────────────────────────────────────────────────
  function TextField<N extends Name>(
    p: FieldBase<N> & {
      placeholder?: string;
      maxLength?: number;
      autoFocus?: boolean;
      autoCapitalize?: 'none' | 'words' | 'sentences' | 'characters';
      keyboardType?: KeyboardTypeOptions;
    }
  ) {
    return (
      <FieldShell
        field={p}
        render={(c) => (
          <TextControl
            {...c}
            placeholder={p.placeholder}
            maxLength={p.maxLength}
            autoFocus={p.autoFocus}
            autoCapitalize={p.autoCapitalize}
            keyboardType={p.keyboardType}
          />
        )}
      />
    );
  }

  function TextareaField<N extends Name>(
    p: FieldBase<N> & { placeholder?: string; maxLength?: number; autoFocus?: boolean }
  ) {
    return (
      <FieldShell
        field={p}
        render={(c) => (
          <TextareaControl
            {...c}
            placeholder={p.placeholder}
            maxLength={p.maxLength}
            autoFocus={p.autoFocus}
          />
        )}
      />
    );
  }

  function PhoneField<N extends Name>(p: FieldBase<N> & { autoFocus?: boolean }) {
    return <FieldShell field={p} render={(c) => <PhoneControl {...c} autoFocus={p.autoFocus} />} />;
  }

  function DateField<N extends Name>(p: FieldBase<N>) {
    return <FieldShell field={p} render={(c) => <DateControl {...c} />} />;
  }

  function ChoiceField<N extends Name>(
    p: FieldBase<N> & {
      options: readonly string[];
      multi?: boolean;
      getLabel?: (opt: string) => string;
    }
  ) {
    return (
      <FieldShell
        field={p}
        render={(c) => (
          <ChoiceControl {...c} options={p.options} multi={p.multi} getLabel={p.getLabel} />
        )}
      />
    );
  }

  function SelectField<N extends Name>(
    p: FieldBase<N> & { placeholder?: string; options: readonly SelectOption[]; title?: string }
  ) {
    return (
      <FieldShell
        field={p}
        render={(c) => (
          <SelectControl
            {...c}
            placeholder={p.placeholder}
            options={p.options}
            title={p.title ?? p.label}
          />
        )}
      />
    );
  }

  function ToggleField<N extends Name>(p: FieldBase<N> & { sublabel?: string }) {
    return (
      <FieldShell
        field={p}
        selfLabeled
        render={(c) => <ToggleControl {...c} label={p.label ?? ''} sublabel={p.sublabel} />}
      />
    );
  }

  function CheckField<N extends Name>(p: FieldBase<N> & { sublabel?: string }) {
    return (
      <FieldShell
        field={p}
        selfLabeled
        render={(c) => <CheckControl {...c} label={p.label ?? ''} sublabel={p.sublabel} />}
      />
    );
  }

  function RadioField<N extends Name>(p: FieldBase<N> & { options: readonly RadioOption[] }) {
    return (
      <FieldShell field={p} render={(c) => <RadioGroupControl {...c} options={p.options} />} />
    );
  }

  function OTPField<N extends Name>(p: FieldBase<N> & { length?: number }) {
    return <FieldShell field={p} render={(c) => <OTPControl {...c} length={p.length} />} />;
  }

  /** Render-prop escape hatch — bring your own control, keep the rhf wiring + KitField. */
  function CustomField<N extends Name>(
    p: FieldBase<N> & {
      bare?: boolean;
      render: (props: ControlProps) => React.ReactElement;
    }
  ) {
    return <FieldShell field={p} selfLabeled={p.bare} render={p.render} />;
  }

  // ── Submit ───────────────────────────────────────────────────────────────────
  function SubmitButton({
    label,
    block = true,
    size = 'lg',
  }: {
    label: string;
    block?: boolean;
    size?: 'sm' | 'md' | 'lg';
  }) {
    const { submit, isSubmitting } = useSubmit();
    return (
      <Sprout
        block={block}
        size={size}
        onPress={submit}
        disabled={isSubmitting}
        loading={isSubmitting}
      >
        {label}
      </Sprout>
    );
  }

  // ── Optional modal wrappers (compose Form inside a Pear shell) ─────────────────
  type ModalFormProps = {
    visible: boolean;
    onClose: () => void;
    onSubmit: (values: TData) => Promise<void> | void;
    defaultValues?: DefaultValues<TData>;
    title?: string;
    subtitle?: string;
    submitLabel?: string;
    children: React.ReactNode;
  };

  function FormSheet({
    visible,
    onClose,
    title,
    subtitle,
    submitLabel = 'Save',
    onSubmit,
    defaultValues,
    children,
  }: ModalFormProps) {
    const { methods, submit } = useFormCore(defaultValues, onSubmit, 'onSubmit');
    // Sheet renders children + footer through an in-tree portal, OUTSIDE this
    // component's React position — so the form context must wrap the portaled
    // nodes themselves, not the Sheet. Both subtrees share the same `methods`.
    const provide = (node: React.ReactNode) => (
      <FormProvider {...methods}>
        <SubmitContext.Provider value={submit}>{node}</SubmitContext.Provider>
      </FormProvider>
    );
    return (
      <Sheet
        visible={visible}
        onClose={onClose}
        title={title}
        subtitle={subtitle}
        footer={provide(<SubmitButton label={submitLabel} />)}
        onShow={() => methods.reset(defaultValues)}
      >
        {provide(children)}
      </Sheet>
    );
  }

  function FormDialog({
    visible,
    onClose,
    title,
    subtitle,
    submitLabel = 'Save',
    onSubmit,
    defaultValues,
    children,
  }: ModalFormProps) {
    const { methods, submit } = useFormCore(defaultValues, onSubmit, 'onSubmit');
    // Dialog (rn-primitives) portals its children out of this position, so the
    // provider must live inside the Dialog wrapping the portaled subtree.
    return (
      <Dialog
        visible={visible}
        onClose={onClose}
        title={title}
        subtitle={subtitle}
        onShow={() => methods.reset(defaultValues)}
      >
        <FormProvider {...methods}>
          <SubmitContext.Provider value={submit}>
            {children}
            <View style={{ marginTop: 20 }}>
              <SubmitButton label={submitLabel} />
            </View>
          </SubmitContext.Provider>
        </FormProvider>
      </Dialog>
    );
  }

  function FormFullSheet({
    visible,
    onClose,
    title,
    submitLabel = 'Save',
    onSubmit,
    defaultValues,
    children,
    onBack,
    step,
  }: ModalFormProps & { onBack?: () => void; step?: string }) {
    const { methods, submit } = useFormCore(defaultValues, onSubmit, 'onSubmit');
    return (
      <FormProvider {...methods}>
        <SubmitContext.Provider value={submit}>
          <FullSheet
            visible={visible}
            onClose={onClose}
            onBack={onBack}
            step={step}
            title={title}
            footer={<SubmitButton label={submitLabel} />}
            onShow={() => methods.reset(defaultValues)}
          >
            {children}
          </FullSheet>
        </SubmitContext.Provider>
      </FormProvider>
    );
  }

  return {
    Form,
    useSubmit,
    SubmitButton,
    TextField,
    TextareaField,
    PhoneField,
    DateField,
    ChoiceField,
    SelectField,
    ToggleField,
    CheckField,
    RadioField,
    OTPField,
    CustomField,
    FormSheet,
    FormDialog,
    FormFullSheet,
  };
}
