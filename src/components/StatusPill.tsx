import { Text, View } from "react-native";
import { colors, radius, spacing, fontSize } from "../theme/tokens";

type Variant = "available" | "comingSoon" | "outdated";

type Props = {
  label: string;
  variant: Variant;
};

const variantStyles: Record<Variant, { bg: string; text: string; border: string; dot?: string }> = {
  available: { bg: colors.successLight, text: colors.success, border: colors.successLight, dot: colors.success },
  comingSoon: { bg: colors.background, text: colors.textMuted, border: colors.border },
  outdated: { bg: colors.warningLight, text: colors.warning, border: colors.warningLight, dot: colors.warning },
};

export function StatusPill({ label, variant }: Props) {
  const s = variantStyles[variant];

  return (
    <View
      accessibilityRole="text"
      accessibilityLabel={label}
      style={{
        flexDirection: "row",
        alignItems: "center",
        alignSelf: "flex-start",
        backgroundColor: s.bg,
        borderWidth: 1,
        borderColor: s.border,
        borderRadius: radius.pill,
        paddingVertical: spacing.xs / 2,
        paddingHorizontal: spacing.sm,
        gap: spacing.xs,
      }}
    >
      {s.dot ? <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: s.dot }} /> : null}
      <Text style={{ fontSize: fontSize.caption, color: s.text, fontWeight: "600" }}>{label}</Text>
    </View>
  );
}
