import { Pressable, Text, View } from "react-native";
import { colors, radius, fontSize, spacing, touchTarget } from "../theme/tokens";

type Status = "pending" | "collected" | "blocked";

type Props = {
  label: string;
  note?: string;
  status: Status;
  onToggle?: () => void;
};

const statusStyles = {
  pending: { box: colors.border, fill: "transparent", mark: "", text: colors.textPrimary },
  collected: { box: colors.success, fill: colors.success, mark: "✓", text: colors.textSecondary },
  blocked: { box: colors.warning, fill: colors.warningLight, mark: "!", text: colors.textPrimary },
};

export function ChecklistItem({ label, note, status, onToggle }: Props) {
  const c = statusStyles[status];

  return (
    <Pressable
      onPress={onToggle}
      disabled={!onToggle}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: status === "collected" }}
      accessibilityLabel={label}
      style={{
        minHeight: touchTarget.min,
        paddingVertical: spacing.sm,
        flexDirection: "row",
        alignItems: "flex-start",
        gap: spacing.md,
      }}
    >
      <View
        style={{
          width: 24,
          height: 24,
          marginTop: 2,
          borderRadius: radius.sm,
          borderWidth: 2,
          borderColor: c.box,
          backgroundColor: c.fill,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text
          style={{
            color: status === "collected" ? "#FFFFFF" : colors.warning,
            fontWeight: "700",
            fontSize: 14,
          }}
        >
          {c.mark}
        </Text>
      </View>

      <View style={{ flex: 1 }}>
        <Text
          style={{
            fontSize: fontSize.body,
            color: c.text,
            textDecorationLine: status === "collected" ? "line-through" : "none",
          }}
        >
          {label}
        </Text>
        {note ? (
          <Text style={{ fontSize: fontSize.caption, color: colors.textMuted, marginTop: 2 }}>
            {note}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}