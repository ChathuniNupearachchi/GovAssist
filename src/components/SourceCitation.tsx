import { Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, fontSize } from "../theme/tokens";

type Props = {
  text: string;
};

export function SourceCitation({ text }: Props) {
  return (
    <View
      style={{ flexDirection: "row", alignItems: "center", gap: spacing.xs, marginTop: spacing.xs }}
      accessibilityRole="text"
      accessibilityLabel={text}
    >
      <Ionicons name="document-text-outline" size={fontSize.caption} color={colors.textMuted} />
      <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>{text}</Text>
    </View>
  );
}
