import { Text, View } from "react-native";
import { colors, spacing, radius, fontSize } from "../theme/tokens";

type Size = "large" | "small";

const sizeStyles: Record<Size, { box: number; point: number; text: number }> = {
  large: { box: spacing.xxl * 2, point: spacing.xxl, text: fontSize.heading },
  small: { box: spacing.xxl, point: spacing.lg, text: fontSize.bodyLarge },
};

type Props = {
  size?: Size;
};

/**
 * Geometric shield mark built from View primitives — a rounded-top square
 * with a triangular point underneath. No image asset, no emoji.
 */
export function ShieldLogo({ size = "large" }: Props) {
  const s = sizeStyles[size];

  return (
    <View accessibilityRole="image" accessibilityLabel="GovAssist shield icon" style={{ alignItems: "center" }}>
      <View
        style={{
          width: s.box,
          height: s.box,
          borderTopLeftRadius: radius.lg,
          borderTopRightRadius: radius.lg,
          borderBottomLeftRadius: radius.sm,
          borderBottomRightRadius: radius.sm,
          backgroundColor: colors.primary,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ color: "#FFFFFF", fontWeight: "800", fontSize: s.text }}>GA</Text>
      </View>
      <View
        style={{
          width: 0,
          height: 0,
          borderLeftWidth: s.box / 2,
          borderRightWidth: s.box / 2,
          borderTopWidth: s.point / 2,
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: colors.primary,
        }}
      />
    </View>
  );
}
