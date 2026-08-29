import { useState } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Button } from "./Button";
import { colors, spacing, fontSize, radius, touchTarget } from "../theme/tokens";

type Props = {
  visible: boolean;
  saving: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (label: string) => void;
};

/**
 * Item 7 — React Native has no built-in `prompt()` on Android, so
 * "prompting for a label" is this small modal rather than a native
 * dialog. Suggests a sensible default ("My plan") but the citizen can
 * change it, matching "a user-editable label."
 */
export function SavePlanModal({ visible, saving, error, onCancel, onConfirm }: Props) {
  const [label, setLabel] = useState("My plan");

  return (
    <Modal visible={visible} animationType="fade" transparent onRequestClose={onCancel}>
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", padding: spacing.lg }}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
          <View
            style={{
              backgroundColor: colors.surface,
              borderRadius: radius.lg,
              padding: spacing.lg,
              gap: spacing.md,
            }}
          >
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ fontSize: fontSize.title, fontWeight: "700", color: colors.textPrimary }}>
                Save this plan
              </Text>
              <Pressable
                onPress={onCancel}
                accessibilityRole="button"
                accessibilityLabel="Cancel"
                style={{ width: touchTarget.min, height: touchTarget.min, alignItems: "center", justifyContent: "center" }}
              >
                <Ionicons name="close" size={fontSize.title} color={colors.textSecondary} />
              </Pressable>
            </View>

            <Text style={{ fontSize: fontSize.body, color: colors.textSecondary }}>
              Give it a name so you can find it later — e.g. "My renewal" or "My daughter's passport."
            </Text>

            <TextInput
              value={label}
              onChangeText={setLabel}
              placeholder="Plan name"
              placeholderTextColor={colors.textMuted}
              accessibilityLabel="Plan name"
              style={{
                minHeight: touchTarget.min,
                borderWidth: 1,
                borderColor: colors.border,
                borderRadius: radius.md,
                paddingHorizontal: spacing.md,
                fontSize: fontSize.body,
                color: colors.textPrimary,
                backgroundColor: colors.background,
              }}
            />

            {error ? (
              <Text accessibilityRole="alert" style={{ fontSize: fontSize.caption, color: colors.danger }}>
                {error}
              </Text>
            ) : null}

            <Button
              label="Save"
              onPress={() => onConfirm(label)}
              loading={saving}
              disabled={!label.trim()}
              fullWidth
            />
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}
