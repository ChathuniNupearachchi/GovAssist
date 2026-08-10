import { useState } from "react";
import { Pressable, View } from "react-native";
import type { ReactNode } from "react";
import { colors, radius, spacing } from "../theme/tokens";

type Props = {
  children: ReactNode;
  onPress?: () => void;
  disabled?: boolean;
};

export function Card({ children, onPress, disabled = false }: Props) {
  const [pressed, setPressed] = useState(false);

  const base = {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: spacing.md,
    opacity: disabled ? 0.5 : 1,
  };

  if (!onPress || disabled) {
    return <View style={base}>{children}</View>;
  }

  return (
    <Pressable
      onPress={onPress}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      accessibilityRole="button"
      style={{
        ...base,
        borderColor: pressed ? colors.primary : colors.border,
        backgroundColor: pressed ? colors.primaryLight : colors.surface,
      }}
    >
      {children}
    </Pressable>
  );
}