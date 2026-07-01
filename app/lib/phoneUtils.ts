import { AsYouType, parsePhoneNumberFromString } from 'libphonenumber-js';

export function formatPhoneInput(text: string): string {
  const hasPlus = text.startsWith('+');
  const digits = text.replace(/\D/g, '');
  return new AsYouType('US').input(hasPlus ? '+' + digits : digits);
}

export function toE164(displayValue: string): string | null {
  const parsed = parsePhoneNumberFromString(displayValue, 'US');
  return parsed?.isValid() ? parsed.number : null;
}
