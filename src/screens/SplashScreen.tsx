import { useEffect } from "react";
import { Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { ShieldLogo } from "../components/ShieldLogo";
import { colors, spacing, fontSize, radius } from "../theme/tokens";

type Props = NativeStackScreenProps<RootStackParamList, "Splash">;

export function SplashScreen({ navigation }: Props) {
  useEffect(() => {
    const timer = setTimeout(() => {
      navigation.replace("Login");
    }, 2500);
    return () => clearTimeout(timer);
  }, [navigation]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.lg }}>
        <View style={{ marginBottom: spacing.lg }}>
          <ShieldLogo size="large" />
        </View>

        <Text
          style={{
            fontSize: fontSize.heading,
            fontWeight: "800",
            color: colors.primary,
            marginBottom: spacing.sm,
          }}
        >
          GovAssist
        </Text>

        <Text style={{ fontSize: fontSize.body, color: colors.textSecondary, textAlign: "center" }}>
          Know exactly what you need,{"\n"}before you go.
        </Text>
      </View>

      <View style={{ alignItems: "center", paddingBottom: spacing.xxl, gap: spacing.sm }}>
        <View
          style={{
            width: spacing.xxl * 2.5,
            height: 4,
            borderRadius: radius.pill,
            backgroundColor: colors.border,
            overflow: "hidden",
          }}
        >
          <View style={{ width: "40%", height: 4, borderRadius: radius.pill, backgroundColor: colors.primary }} />
        </View>
        <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>Loading…</Text>
      </View>
    </SafeAreaView>
  );
}
