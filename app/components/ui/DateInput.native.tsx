import { useState } from 'react';
import { Modal, Platform, StyleSheet } from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import { View, Text, Pressable } from '@/lib/tw';
import { colors } from '@/constants/theme';

type Props = {
  value: Date | null;
  onChange: (date: Date) => void;
  style?: object;
};

function formatDate(date: Date) {
  return date.toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' });
}

export default function DateInput({ value, onChange, style }: Props) {
  const [show, setShow] = useState(false);
  const [temp, setTemp] = useState(new Date(2000, 0, 1));

  return (
    <>
      <Pressable
        className="bg-white rounded-xl border-[1.5px] border-separator px-4 py-[14px] justify-center"
        style={style}
        onPress={() => setShow(true)}
      >
        <Text className={value ? 'text-base text-fg' : 'text-base text-fg-ghost'}>
          {value ? formatDate(value) : 'Date of birth'}
        </Text>
      </Pressable>

      {Platform.OS === 'android' && show && (
        <DateTimePicker
          value={value ?? temp}
          mode="date"
          display="default"
          maximumDate={new Date()}
          onChange={(_, date) => {
            setShow(false);
            if (date) onChange(date);
          }}
        />
      )}

      {Platform.OS === 'ios' && (
        <Modal visible={show} transparent animationType="slide">
          <View className="flex-1 justify-end bg-[rgba(0,0,0,0.3)]">
            <View className="bg-white rounded-tl-[20px] rounded-tr-[20px] pb-8">
              <View
                className="flex-row justify-end p-4"
                style={{
                  borderBottomWidth: StyleSheet.hairlineWidth,
                  borderBottomColor: colors.divider,
                }}
              >
                <Pressable onPress={() => setShow(false)}>
                  <Text className="text-accent text-base font-semibold">Done</Text>
                </Pressable>
              </View>
              <DateTimePicker
                value={value ?? temp}
                mode="date"
                display="spinner"
                maximumDate={new Date()}
                onChange={(_, date) => {
                  if (date) {
                    onChange(date);
                    setTemp(date);
                  }
                }}
              />
            </View>
          </View>
        </Modal>
      )}
    </>
  );
}
