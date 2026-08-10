import { Pressable, Text, ActivityIndicator } from "react-native";
import { colors, radius, fontSize, touchTarget, spacing } from "../theme/tokens";
import { useState } from "react";

type Variant = "primary" | "secondary" | "ghost";

type Props = {
  label: string;
  onPress: () => void;
  variant?: Variant;
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
};

const variantStyles = {
  primary: { bg: colors.primary, text: "#FFFFFF", border: colors.primary },
  secondary: { bg: colors.surface, text: colors.primary, border: colors.primary },
  ghost: { bg: "transparent", text: colors.primary, border: "transparent" },
};

export function Button({
  label,
  onPress,
  variant = "primary",
  disabled = false,
  loading = false,
  fullWidth = false,
}: Props) {
  const s = variantStyles[variant];
  const inactive = disabled || loading;
  const [pressed, setPressed] = useState(false);

  return (
    <Pressable
      onPress={onPress}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: inactive, busy: loading }}
      style={{
        minHeight: touchTarget.comfortable,
        paddingHorizontal: spacing.lg,
        borderRadius: radius.md,
        borderWidth: 1,
        backgroundColor: s.bg,
        borderColor: s.border,
        opacity: inactive ? 0.45 : pressed ? 0.85 : 1,
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "row",
        alignSelf: fullWidth ? "stretch" : "flex-start",
      }}
    >
      {loading ? (
        <ActivityIndicator color={s.text} />
      ) : (
        <Text style={{ color: s.text, fontSize: fontSize.body, fontWeight: "600" }}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}
