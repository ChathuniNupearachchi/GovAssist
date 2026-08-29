import { useState } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, Text, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Button } from "./Button";
import { useAuthStore } from "../store/authStore";
import { colors, spacing, fontSize, radius, touchTarget } from "../theme/tokens";

type Props = {
  visible: boolean;
  onClose: () => void;
  /** Called once the account is created and signed in — the caller decides what happens next (e.g. just closing the modal). */
  onSuccess: () => void;
};

/**
 * Item 7 — "Sign-up as a modal, not a screen." A `Modal` overlay rather
 * than a navigation route: the existing Login screen still owns
 * sign-in, this is reached only from its "Sign up" link and never adds
 * a stack entry of its own.
 */
export function SignUpModal({ visible, onClose, onSuccess }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const signingIn = useAuthStore((s) => s.signingIn);
  const signUpError = useAuthStore((s) => s.signUpError);
  const signUp = useAuthStore((s) => s.signUp);

  const reset = () => {
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    setLocalError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleCreateAccount = async () => {
    setLocalError(null);
    if (password !== confirmPassword) {
      setLocalError("Passwords don't match.");
      return;
    }
    const success = await signUp(email, password);
    if (success) {
      reset();
      onSuccess();
    }
  };

  const error = localError ?? signUpError;

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={handleClose}>
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" }}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
          <View
            style={{
              backgroundColor: colors.surface,
              borderTopLeftRadius: radius.lg,
              borderTopRightRadius: radius.lg,
              padding: spacing.lg,
              gap: spacing.md,
            }}
          >
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ fontSize: fontSize.title, fontWeight: "700", color: colors.textPrimary }}>
                Create an account
              </Text>
              <Pressable
                onPress={handleClose}
                accessibilityRole="button"
                accessibilityLabel="Close"
                style={{
                  width: touchTarget.min,
                  height: touchTarget.min,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Ionicons name="close" size={fontSize.title} color={colors.textSecondary} />
              </Pressable>
            </View>

            <Text style={{ fontSize: fontSize.body, color: colors.textSecondary }}>
              Save your plans and pick up where you left off on any device.
            </Text>

            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="Email address"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              keyboardType="email-address"
              accessibilityLabel="Email address"
              style={inputStyle}
            />
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="Password (at least 8 characters)"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
              accessibilityLabel="Password"
              style={inputStyle}
            />
            <TextInput
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              placeholder="Confirm password"
              placeholderTextColor={colors.textMuted}
              secureTextEntry
              accessibilityLabel="Confirm password"
              style={inputStyle}
            />

            {error ? (
              <Text
                accessibilityRole="alert"
                style={{ fontSize: fontSize.caption, color: colors.danger }}
              >
                {error}
              </Text>
            ) : null}

            <Button
              label="Create account"
              onPress={handleCreateAccount}
              loading={signingIn}
              disabled={!email.trim() || !password || !confirmPassword}
              fullWidth
            />
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

const inputStyle = {
  minHeight: touchTarget.min,
  borderWidth: 1,
  borderColor: colors.border,
  borderRadius: radius.md,
  paddingHorizontal: spacing.md,
  fontSize: fontSize.body,
  color: colors.textPrimary,
  backgroundColor: colors.background,
};
