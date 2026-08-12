import { useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { Button } from "../components/Button";
import { ShieldLogo } from "../components/ShieldLogo";
import { GoogleIcon } from "../components/GoogleIcon";
import { colors, spacing, fontSize, radius, touchTarget } from "../theme/tokens";

type Props = NativeStackScreenProps<RootStackParamList, "Login">;

export function LoginScreen({ navigation }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [googlePressed, setGooglePressed] = useState(false);

  const goToApp = () => navigation.replace("Departments");

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          contentContainerStyle={{ flexGrow: 1, padding: spacing.lg, justifyContent: "center", gap: spacing.md }}
          keyboardShouldPersistTaps="handled"
        >
          <View style={{ alignItems: "center", gap: spacing.sm, marginBottom: spacing.md }}>
            <ShieldLogo size="small" />
            <Text style={{ fontSize: fontSize.title, fontWeight: "800", color: colors.primary }}>GovAssist</Text>
          </View>

          <Pressable
            onPress={goToApp}
            onPressIn={() => setGooglePressed(true)}
            onPressOut={() => setGooglePressed(false)}
            accessibilityRole="button"
            accessibilityLabel="Continue with Google"
            style={{
              minHeight: touchTarget.comfortable,
              borderRadius: radius.md,
              borderWidth: 1,
              borderColor: colors.border,
              backgroundColor: googlePressed ? colors.background : colors.surface,
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "row",
              gap: spacing.sm,
            }}
          >
            <GoogleIcon size={fontSize.title} />
            <Text style={{ fontSize: fontSize.body, color: colors.textPrimary, fontWeight: "600" }}>
              Continue with Google
            </Text>
          </Pressable>

          <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
            <Text style={{ color: colors.textMuted, fontSize: fontSize.caption }}>or</Text>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
          </View>

          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder="Email address"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            keyboardType="email-address"
            accessibilityLabel="Email address"
            style={{
              minHeight: touchTarget.min,
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: radius.md,
              paddingHorizontal: spacing.md,
              fontSize: fontSize.body,
              color: colors.textPrimary,
              backgroundColor: colors.surface,
            }}
          />

          <View style={{ justifyContent: "center" }}>
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              placeholderTextColor={colors.textMuted}
              secureTextEntry={!showPassword}
              accessibilityLabel="Password"
              style={{
                minHeight: touchTarget.min,
                borderWidth: 1,
                borderColor: colors.border,
                borderRadius: radius.md,
                paddingHorizontal: spacing.md,
                paddingRight: touchTarget.min,
                fontSize: fontSize.body,
                color: colors.textPrimary,
                backgroundColor: colors.surface,
              }}
            />
            <Pressable
              onPress={() => setShowPassword((v) => !v)}
              accessibilityRole="button"
              accessibilityLabel={showPassword ? "Hide password" : "Show password"}
              style={{
                position: "absolute",
                right: 0,
                top: 0,
                width: touchTarget.min,
                height: touchTarget.min,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Ionicons
                name={showPassword ? "eye-off-outline" : "eye-outline"}
                size={fontSize.title}
                color={colors.textMuted}
              />
            </Pressable>
          </View>

          <Button label="Sign in" onPress={goToApp} fullWidth />

          <Pressable
            onPress={() => {}}
            accessibilityRole="link"
            accessibilityLabel="Forgot password?"
            style={{ alignSelf: "flex-end", minHeight: touchTarget.min, justifyContent: "center" }}
          >
            <Text style={{ color: colors.textSecondary, fontSize: fontSize.body }}>Forgot password?</Text>
          </Pressable>

          <View style={{ height: 1, backgroundColor: colors.border, marginVertical: spacing.sm }} />

          <Button label="Skip — continue without an account" onPress={goToApp} variant="secondary" fullWidth />

          <Pressable
            onPress={() => {}}
            accessibilityRole="link"
            accessibilityLabel="Sign up"
            style={{
              alignSelf: "center",
              minHeight: touchTarget.min,
              justifyContent: "center",
              flexDirection: "row",
            }}
          >
            <Text style={{ color: colors.textSecondary, fontSize: fontSize.body }}>Don't have an account? </Text>
            <Text style={{ color: colors.primary, fontSize: fontSize.body, fontWeight: "600" }}>Sign up</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
