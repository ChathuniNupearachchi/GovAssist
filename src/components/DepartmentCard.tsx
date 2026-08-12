import { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import type { ComponentProps } from "react";
import { colors, radius, spacing, fontSize, touchTarget } from "../theme/tokens";
import { StatusPill } from "./StatusPill";

type IconName = ComponentProps<typeof Ionicons>["name"];
type Status = "available" | "comingSoon";

type Props = {
  title: string;
  subtitle: string;
  icon: IconName;
  status: Status;
  onPress?: () => void;
};

export function DepartmentCard({ title, subtitle, icon, status, onPress }: Props) {
  const [pressed, setPressed] = useState(false);
  const available = status === "available";
  const interactive = available && !!onPress;

  const content = (
    <View style={{ flexDirection: "row", alignItems: "flex-start", gap: spacing.md }}>
      <View
        style={{
          width: 48,
          height: 48,
          borderRadius: radius.md,
          backgroundColor: available ? colors.primaryLight : colors.background,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Ionicons name={icon} size={24} color={available ? colors.primary : colors.textMuted} />
      </View>

      <View style={{ flex: 1, gap: spacing.xs }}>
        <Text
          style={{
            fontSize: fontSize.bodyLarge,
            fontWeight: "700",
            color: available ? colors.textPrimary : colors.textMuted,
          }}
        >
          {title}
        </Text>
        <Text
          style={{
            fontSize: fontSize.body,
            color: available ? colors.textSecondary : colors.textMuted,
          }}
        >
          {subtitle}
        </Text>
        <View style={{ marginTop: spacing.xs }}>
          <StatusPill
            label={available ? "Available" : "Coming Soon"}
            variant={available ? "available" : "comingSoon"}
          />
        </View>
      </View>

      {interactive ? <Ionicons name="chevron-forward" size={20} color={colors.textMuted} /> : null}
    </View>
  );

  const base = {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: available ? 4 : 1,
    borderLeftColor: available ? colors.primary : colors.border,
    borderRadius: radius.lg,
    padding: spacing.md,
    minHeight: touchTarget.min,
  };

  if (!interactive) {
    return (
      <View
        style={{ ...base, backgroundColor: colors.background, opacity: 0.85 }}
        accessibilityRole="text"
        accessibilityLabel={`${title}, ${subtitle}, Coming soon`}
      >
        {content}
      </View>
    );
  }

  return (
    <Pressable
      onPress={onPress}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      accessibilityRole="button"
      accessibilityLabel={`${title}, ${subtitle}`}
      style={{
        ...base,
        backgroundColor: pressed ? colors.primaryLight : colors.surface,
      }}
    >
      {content}
    </Pressable>
  );
}
