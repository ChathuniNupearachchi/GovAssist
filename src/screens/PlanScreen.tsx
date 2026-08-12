import { useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { ChecklistItem } from "../components/ChecklistItem";
import { SourceCitation } from "../components/SourceCitation";
import { colors, spacing, fontSize, radius } from "../theme/tokens";

type Props = NativeStackScreenProps<RootStackParamList, "Plan">;

type PlanItem = {
  id: string;
  label: string;
  note?: string;
  status: "collected" | "pending";
  source: string;
};

const INITIAL_ITEMS: PlanItem[] = [
  {
    id: "passport",
    label: "Current passport (original + photocopy)",
    status: "collected",
    source: "Immigration Dept · Verified 10 Aug 2026",
  },
  {
    id: "nic",
    label: "National Identity Card (original + photocopy)",
    status: "pending",
    source: "Immigration Dept · Verified 10 Aug 2026",
  },
  {
    id: "marriage",
    label: "Marriage certificate",
    note: "Required because your name changed",
    status: "pending",
    source: "Immigration Dept · Verified 10 Aug 2026",
  },
  {
    id: "photo",
    label: "Passport photograph",
    note: "From an authorised photo studio only",
    status: "pending",
    source: "Immigration Dept · Verified 10 Aug 2026",
  },
];

export function PlanScreen({ navigation }: Props) {
  const [items, setItems] = useState<PlanItem[]>(INITIAL_ITEMS);

  const toggleItem = (id: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, status: item.status === "collected" ? "pending" : "collected" } : item
      )
    );
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
      <ScrollView contentContainerStyle={{ padding: spacing.md, gap: spacing.lg }}>
        <View
          style={{
            backgroundColor: colors.primary,
            borderRadius: radius.lg,
            padding: spacing.lg,
            gap: spacing.md,
          }}
        >
          <View style={{ flexDirection: "row" }}>
            <PlanStat label="Fee" value="LKR 10,000" />
            <PlanDivider />
            <PlanStat label="Office" value="Kandy Regional Office" />
            <PlanDivider />
            <PlanStat label="Timeline" value="30 working days" />
          </View>

          <View style={{ height: 1, backgroundColor: "#FFFFFF", opacity: 0.25 }} />

          <Text style={{ color: "#FFFFFF", fontSize: fontSize.body }}>
            Your plan is ready. Tap any item to learn more.
          </Text>
        </View>

        <View style={{ gap: spacing.md }}>
          <Text style={{ fontSize: fontSize.title, fontWeight: "700", color: colors.textPrimary }}>
            Your document checklist
          </Text>

          <Card>
            <View style={{ gap: spacing.sm }}>
              {items.map((item, index) => (
                <View
                  key={item.id}
                  style={{
                    borderTopWidth: index === 0 ? 0 : 1,
                    borderTopColor: colors.border,
                    paddingTop: index === 0 ? 0 : spacing.sm,
                  }}
                >
                  <ChecklistItem
                    label={item.label}
                    note={item.note}
                    status={item.status}
                    onToggle={() => toggleItem(item.id)}
                  />
                  <View style={{ marginLeft: 40 }}>
                    <SourceCitation text={item.source} />
                  </View>
                </View>
              ))}
            </View>
          </Card>
        </View>

        <View style={{ gap: spacing.sm }}>
          <Button label="Save plan" onPress={() => {}} fullWidth />
          <Button
            label="Ask about any item"
            onPress={() => navigation.navigate("Services", { initialTab: "ask" })}
            variant="secondary"
            fullWidth
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function PlanStat({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flex: 1, gap: spacing.xs }}>
      <Text style={{ color: "#FFFFFF", opacity: 0.7, fontSize: fontSize.caption }}>{label}</Text>
      <Text style={{ color: "#FFFFFF", fontSize: fontSize.body, fontWeight: "700" }}>{value}</Text>
    </View>
  );
}

function PlanDivider() {
  return <View style={{ width: 1, backgroundColor: "#FFFFFF", opacity: 0.25, marginHorizontal: spacing.sm }} />;
}
