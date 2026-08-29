import { Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useUIStore } from "../store/uiStore";
import { colors, fontSize, spacing, touchTarget } from "../theme/tokens";

/** Item 7 — the user icon top right on every main screen; opens the account drawer regardless of sign-in state (an anonymous citizen sees Sign in / Sign up there instead of Profile / My plans / Logout). */
export function UserMenuButton() {
  const openDrawer = useUIStore((s) => s.openDrawer);

  return (
    <Pressable
      onPress={openDrawer}
      accessibilityRole="button"
      accessibilityLabel="Account menu"
      style={{
        minWidth: touchTarget.min,
        minHeight: touchTarget.min,
        alignItems: "center",
        justifyContent: "center",
        marginRight: spacing.xs,
      }}
    >
      <Ionicons name="person-circle-outline" size={fontSize.heading} color={colors.primary} />
    </Pressable>
  );
}
