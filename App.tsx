import "./global.css";
import { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { Button } from "./src/components/Button";
import { Card } from "./src/components/Card";
import { ChecklistItem } from "./src/components/ChecklistItem";
import { colors, spacing, fontSize } from "./src/theme/tokens";

export default function App() {
  const [collected, setCollected] = useState(false);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
        <ScrollView contentContainerStyle={{ padding: spacing.md, gap: spacing.lg }}>
          <Text
            style={{
              fontSize: fontSize.heading,
              fontWeight: "700",
              color: colors.textPrimary,
            }}
          >
            Component check
          </Text>

          <View style={{ gap: spacing.sm }}>
            <Button label="Primary" onPress={() => {}} fullWidth />
            <Button label="Secondary" variant="secondary" onPress={() => {}} fullWidth />
            <Button label="Ghost" variant="ghost" onPress={() => {}} fullWidth />
            <Button label="Disabled" onPress={() => {}} disabled fullWidth />
            <Button label="Loading" onPress={() => {}} loading fullWidth />
          </View>

          <View style={{ gap: spacing.sm }}>
            <Card>
              <Text style={{ fontSize: fontSize.body, color: colors.textPrimary }}>
                Static card
              </Text>
            </Card>

            <Card onPress={() => {}}>
              <Text style={{ fontSize: fontSize.body, color: colors.textPrimary }}>
                Pressable card — tap me
              </Text>
            </Card>

            <Card disabled>
              <Text style={{ fontSize: fontSize.body, color: colors.textPrimary }}>
                Disabled card
              </Text>
            </Card>
          </View>

          <Card>
            <ChecklistItem
              label="Birth certificate"
              note="Obtained within the last 6 months"
              status={collected ? "collected" : "pending"}
              onToggle={() => setCollected(!collected)}
            />
            <ChecklistItem
              label="National Identity Card"
              status="pending"
              onToggle={() => {}}
            />
            <ChecklistItem
              label="Certified translation"
              note="Required before you apply"
              status="blocked"
            />
          </Card>
        </ScrollView>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}