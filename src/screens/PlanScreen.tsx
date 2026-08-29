import { useEffect, useState } from "react";
import { ActivityIndicator, Linking, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { ChecklistItem } from "../components/ChecklistItem";
import { PlanHeader } from "../components/PlanHeader";
import { SourceCitation } from "../components/SourceCitation";
import { SavePlanModal } from "../components/SavePlanModal";
import { savePlan } from "../api/client";
import type { Requirement, RequirementKind } from "../api/types";
import { formatCitation } from "../utils/citation";
import { useAuthStore } from "../store/authStore";
import { useDeviceStore } from "../store/deviceStore";
import { usePlanStore } from "../store/planStore";
import { colors, spacing, fontSize, radius } from "../theme/tokens";

type Props = NativeStackScreenProps<RootStackParamList, "Plan">;

/**
 * `Requirement.kind` badge — string-union lookup, per CLAUDE.md's
 * "variants as string unions with a lookup object" rule. The list
 * itself stays in one `sequence`-ordered run (task 10.2 requires
 * sequence order, not kind-grouped sections); this badge is what makes
 * a prerequisite visually distinct from a document without reordering.
 */
const KIND_BADGE: Record<RequirementKind, { label: string; color: string; bg: string } | null> = {
  prerequisite: { label: "Before you apply", color: colors.warning, bg: colors.warningLight },
  step: { label: "Step", color: colors.primary, bg: colors.primaryLight },
  document: null,
};

export function PlanScreen({ navigation }: Props) {
  const caseId = useDeviceStore((s) => s.caseId);
  const citizenDistrict = useDeviceStore((s) => s.citizenDistrict);

  const resolution = usePlanStore((s) => s.resolution);
  const pendingQuestion = usePlanStore((s) => s.pendingQuestion);
  const resolveLoading = usePlanStore((s) => s.resolveLoading);
  const resolveError = usePlanStore((s) => s.resolveError);
  const resolveCase = usePlanStore((s) => s.resolveCase);

  const studios = usePlanStore((s) => s.studios);
  const studiosLoading = usePlanStore((s) => s.studiosLoading);
  const studiosError = usePlanStore((s) => s.studiosError);
  const loadStudios = usePlanStore((s) => s.loadStudios);

  const [collected, setCollected] = useState<Record<string, boolean>>({});
  const [saveModalVisible, setSaveModalVisible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const authToken = useAuthStore((s) => s.token);

  const handleConfirmSave = async (label: string) => {
    if (!authToken || !caseId) return;
    const trimmed = label.trim();
    if (!trimmed) return;
    setSaving(true);
    setSaveError(null);
    try {
      await savePlan(authToken, caseId, trimmed);
      setSaving(false);
      setSaveModalVisible(false);
      setSavedMessage(`Saved as "${trimmed}"`);
    } catch {
      setSaving(false);
      setSaveError("Couldn't save this plan. Try again.");
    }
  };

  useEffect(() => {
    if (caseId) {
      resolveCase(caseId);
    }
  }, [caseId]);

  useEffect(() => {
    if (citizenDistrict && !resolution?.scope_gate) {
      loadStudios(citizenDistrict);
    }
  }, [citizenDistrict, resolution?.scope_gate]);

  const toggleCollected = (id: string) => {
    setCollected((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // ---- Four states: loading / empty / error / loaded ----

  if (!caseId) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.lg }}>
          <Text style={{ fontSize: fontSize.body, color: colors.textMuted, textAlign: "center" }}>
            Start a conversation on the Services tab to build your plan.
          </Text>
          <View style={{ height: spacing.md }} />
          <Button label="Go to Services" onPress={() => navigation.navigate("Services", { initialTab: "services" })} />
        </View>
      </SafeAreaView>
    );
  }

  if (resolveLoading) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.sm }}>
          <ActivityIndicator color={colors.primary} />
          <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>Computing your plan…</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (resolveError) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
        <View style={{ flex: 1, padding: spacing.md, justifyContent: "center" }}>
          <ErrorBanner message={resolveError.message} onRetry={() => resolveCase(caseId)} />
        </View>
      </SafeAreaView>
    );
  }

  if (!resolution) {
    // Intake isn't complete yet (409) — an empty state, not an error.
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.lg, gap: spacing.md }}>
          <Text style={{ fontSize: fontSize.body, color: colors.textMuted, textAlign: "center" }}>
            {pendingQuestion
              ? `A few more questions to go: ${pendingQuestion}`
              : "Your plan isn't ready yet — finish answering the questions in chat first."}
          </Text>
          <Button label="Back to chat" onPress={() => navigation.navigate("Services", { initialTab: "ask" })} />
        </View>
      </SafeAreaView>
    );
  }

  // Scope gate: refusal only, never a partial plan (task 10.8).
  if (resolution.scope_gate) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
        <ScrollView contentContainerStyle={{ padding: spacing.md, flexGrow: 1, justifyContent: "center" }}>
          <View
            style={{
              backgroundColor: colors.warningLight,
              borderColor: colors.warning,
              borderWidth: 1,
              borderRadius: radius.lg,
              padding: spacing.lg,
              gap: spacing.sm,
            }}
          >
            <Text style={{ fontSize: fontSize.title, fontWeight: "700", color: colors.warning }}>
              We can't build a plan for this
            </Text>
            <Text style={{ fontSize: fontSize.body, color: colors.textPrimary }}>{resolution.scope_gate.reason}</Text>
          </View>
          <View style={{ height: spacing.md }} />
          <Button label="Ask a different question" onPress={() => navigation.navigate("Services", { initialTab: "ask" })} fullWidth />
        </ScrollView>
      </SafeAreaView>
    );
  }

  const sortedRequirements = [...resolution.requirements].sort((a, b) => a.sequence - b.sequence);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
      <ScrollView contentContainerStyle={{ padding: spacing.md, gap: spacing.lg }}>
        <PlanHeader fee={resolution.fee} offices={resolution.offices} />

        {resolution.amendment_alternative ? (
          <AmendmentAlternativeCard alternative={resolution.amendment_alternative} primaryFee={resolution.fee} />
        ) : null}

        <View style={{ gap: spacing.md }}>
          <Text style={{ fontSize: fontSize.title, fontWeight: "700", color: colors.textPrimary }}>
            Your document checklist
          </Text>

          {sortedRequirements.length === 0 ? (
            <Card>
              <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>
                No requirements were found for this case.
              </Text>
            </Card>
          ) : (
            <Card>
              <View style={{ gap: spacing.sm }}>
                {sortedRequirements.map((requirement, index) => (
                  <RequirementRow
                    key={requirement.id}
                    requirement={requirement}
                    first={index === 0}
                    collected={!!collected[requirement.id]}
                    onToggle={() => toggleCollected(requirement.id)}
                  />
                ))}
              </View>
            </Card>
          )}
        </View>

        <StudiosSection
          district={citizenDistrict}
          studios={studios}
          loading={studiosLoading}
          error={studiosError}
          onRetry={() => citizenDistrict && loadStudios(citizenDistrict)}
        />

        <View style={{ gap: spacing.sm }}>
          {authToken ? (
            <>
              <Button label="Save plan" onPress={() => setSaveModalVisible(true)} fullWidth />
              {savedMessage ? (
                <Text style={{ fontSize: fontSize.caption, color: colors.success, textAlign: "center" }}>
                  {savedMessage}
                </Text>
              ) : null}
            </>
          ) : null}
          <Button
            label="Ask about any item"
            onPress={() => navigation.navigate("Services", { initialTab: "ask" })}
            variant="secondary"
            fullWidth
          />
        </View>
      </ScrollView>

      <SavePlanModal
        visible={saveModalVisible}
        saving={saving}
        error={saveError}
        onCancel={() => setSaveModalVisible(false)}
        onConfirm={handleConfirmSave}
      />
    </SafeAreaView>
  );
}

function RequirementRow({
  requirement,
  first,
  collected,
  onToggle,
}: {
  requirement: Requirement;
  first: boolean;
  collected: boolean;
  onToggle: () => void;
}) {
  const badge = KIND_BADGE[requirement.kind];

  return (
    <View style={{ borderTopWidth: first ? 0 : 1, borderTopColor: colors.border, paddingTop: first ? 0 : spacing.sm }}>
      {badge ? (
        <View
          style={{
            alignSelf: "flex-start",
            backgroundColor: badge.bg,
            borderRadius: radius.pill,
            paddingHorizontal: spacing.sm,
            paddingVertical: 2,
            marginBottom: spacing.xs,
            marginLeft: 40,
          }}
        >
          <Text style={{ fontSize: fontSize.caption, color: badge.color, fontWeight: "600" }}>{badge.label}</Text>
        </View>
      ) : null}

      <ChecklistItem label={requirement.label} status={collected ? "collected" : "pending"} onToggle={onToggle} />

      <View style={{ marginLeft: 40, gap: spacing.xs }}>
        <SourceCitation text={formatCitation(requirement.citation)} />
        {requirement.resources.map((resource, index) => (
          <Pressable
            key={`${resource.url}-${index}`}
            onPress={() => Linking.openURL(resource.url)}
            accessibilityRole="link"
            accessibilityLabel={`Open ${resource.label}`}
            style={{ flexDirection: "row", alignItems: "center", gap: spacing.xs, minHeight: 32 }}
          >
            <Ionicons name="download-outline" size={fontSize.caption} color={colors.primary} />
            <Text style={{ fontSize: fontSize.caption, color: colors.primary, fontWeight: "600" }}>
              {resource.label} ({resource.type})
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function AmendmentAlternativeCard({
  alternative,
  primaryFee,
}: {
  alternative: NonNullable<import("../api/types").CaseResolution["amendment_alternative"]>;
  primaryFee: import("../api/types").Fee | null;
}) {
  return (
    <View
      style={{
        backgroundColor: colors.primaryLight,
        borderColor: colors.primary,
        borderWidth: 1,
        borderRadius: radius.lg,
        padding: spacing.lg,
        gap: spacing.md,
      }}
    >
      <Text style={{ fontSize: fontSize.bodyLarge, fontWeight: "700", color: colors.primary }}>
        You may have a faster option: amendment
      </Text>
      <Text style={{ fontSize: fontSize.body, color: colors.textPrimary }}>
        Instead of a full renewal, some cases qualify for a quicker, cheaper amendment. Compare both before deciding.
      </Text>

      <View style={{ flexDirection: "row", gap: spacing.md }}>
        <ComparisonColumn
          title="Renewal (this plan)"
          fee={primaryFee ? `LKR ${primaryFee.base_amount.toLocaleString("en-LK")}` : "—"}
        />
        <ComparisonColumn
          title="Amendment"
          fee={`LKR ${alternative.fee.base_amount.toLocaleString("en-LK")}`}
        />
      </View>

      <View style={{ gap: spacing.xs }}>
        <Text style={{ fontSize: fontSize.body, fontWeight: "700", color: colors.textPrimary }}>
          What amendment would need:
        </Text>
        {alternative.requirements
          .slice()
          .sort((a, b) => a.sequence - b.sequence)
          .map((requirement) => (
            <View key={requirement.id} style={{ flexDirection: "row", gap: spacing.xs, alignItems: "flex-start" }}>
              <Text style={{ fontSize: fontSize.body, color: colors.textSecondary }}>•</Text>
              <Text style={{ fontSize: fontSize.body, color: colors.textSecondary, flex: 1 }}>
                {requirement.label}
              </Text>
            </View>
          ))}
      </View>
    </View>
  );
}

function ComparisonColumn({ title, fee }: { title: string; fee: string }) {
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, borderRadius: radius.md, padding: spacing.sm, gap: 2 }}>
      <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>{title}</Text>
      <Text style={{ fontSize: fontSize.bodyLarge, fontWeight: "700", color: colors.textPrimary }}>{fee}</Text>
    </View>
  );
}

function StudiosSection({
  district,
  studios,
  loading,
  error,
  onRetry,
}: {
  district: string | null;
  studios: import("../api/types").StudioResolution | null;
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
}) {
  if (!district) {
    // Not applicable — an overseas applicant is never asked a district
    // question, so there's nothing to fetch. Not an error state.
    return null;
  }

  return (
    <View style={{ gap: spacing.md }}>
      <Text style={{ fontSize: fontSize.title, fontWeight: "700", color: colors.textPrimary }}>
        Authorised photo studios in {district}
      </Text>

      {loading ? (
        <Card>
          <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
            <ActivityIndicator color={colors.primary} />
            <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>Loading studios…</Text>
          </View>
        </Card>
      ) : error ? (
        <ErrorBanner message={error.message} onRetry={onRetry} />
      ) : !studios || studios.studios.length === 0 ? (
        <Card>
          <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>
            No authorised studios are listed for {district} yet.
          </Text>
        </Card>
      ) : (
        <Card>
          <View style={{ gap: spacing.sm }}>
            {studios.studios.map((studio, index) => (
              <View
                key={studio.id}
                style={{
                  borderTopWidth: index === 0 ? 0 : 1,
                  borderTopColor: colors.border,
                  paddingTop: index === 0 ? 0 : spacing.sm,
                  gap: spacing.xs,
                }}
              >
                <Text style={{ fontSize: fontSize.body, fontWeight: "700", color: colors.textPrimary }}>
                  {studio.name}
                </Text>
                <Text style={{ fontSize: fontSize.body, color: colors.textSecondary }}>{studio.address}</Text>
                {studio.phone ? (
                  <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>{studio.phone}</Text>
                ) : null}
                <SourceCitation text={formatCitation(studio.citation)} />
              </View>
            ))}
            <View style={{ borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm }}>
              <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>{studios.receipt_note}</Text>
            </View>
          </View>
        </Card>
      )}
    </View>
  );
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View
      style={{
        backgroundColor: colors.dangerLight,
        borderColor: colors.danger,
        borderWidth: 1,
        borderRadius: radius.md,
        padding: spacing.md,
        gap: spacing.sm,
      }}
    >
      <Text style={{ fontSize: fontSize.body, color: colors.danger }}>{message}</Text>
      <Button label="Retry" onPress={onRetry} variant="secondary" />
    </View>
  );
}
