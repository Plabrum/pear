import { colors } from '@/constants/theme';

type Props = {
  value: Date | null;
  onChange: (date: Date) => void;
  style?: React.CSSProperties;
};

export default function DateInput({ value, onChange, style }: Props) {
  return (
    <input
      type="date"
      max={new Date().toISOString().split('T')[0]}
      value={value ? value.toISOString().split('T')[0] : ''}
      onChange={(e) => {
        if (e.target.value) onChange(new Date(e.target.value));
      }}
      style={{
        backgroundColor: colors.white,
        borderRadius: 12,
        borderWidth: 1.5,
        borderStyle: 'solid',
        borderColor: colors.divider,
        paddingLeft: 16,
        paddingRight: 16,
        paddingTop: 14,
        paddingBottom: 14,
        fontSize: 16,
        color: value ? colors.ink : colors.inkGhost,
        width: '100%',
        boxSizing: 'border-box',
        ...style,
      }}
    />
  );
}
