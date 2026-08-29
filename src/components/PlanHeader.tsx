import { Text, View } from "react-native";
import type { Fee, OfficeResolution } from "../api/types";
import { colors, spacing, fontSize, radius } from "../theme/tokens";

type Props = {
  fee: Fee | null;
  offices: OfficeResolution | null;
};

function formatAmount(amount: number): string {
  return `LKR ${amount.toLocaleString("en-LK")}`;
}

/**
 * Extracted from PlanScreen.tsx's old inline PlanStat/PlanDivider — see
 * tasks.md Group 6. No `timeline` prop: neither `Fee` nor
 * `OfficeResolution` carries one, so there's nothing real to show.
 * `conflict_note` is read off `offices` rather than taken as a separate
 * prop — it's already part of that same API object (design.md's
 * "conflict note stays part of OfficeResolution" note), and threading
 * it separately would just be two props derived from one response.
 */
export function PlanHeader({ fee, offices }: Props) {
  const conflictNote = offices?.conflict_note ?? null;
  const officeNames = offices?.offices.length ? offices.offices.map((o) => o.name).join(", ") : null;

  return (
    <View style={{ gap: spacing.sm }}>
      <View
        style={{
          backgroundColor: colors.primary,
          borderRadius: radius.lg,
          padding: spacing.lg,
          gap: spacing.md,
        }}
      >
        <View style={{ flexDirection: "row" }}>
          <PlanStat label="Fee" value={fee ? formatAmount(fee.base_amount) : "Not yet available"} />
          <PlanDivider />
          <PlanStat label="Office" value={officeNames ?? "Not yet available"} />
        </View>

        {offices?.district_mapping_caveat ? (
          <>
            <View style={{ height: 1, backgroundColor: "#FFFFFF", opacity: 0.25 }} />
            <Text style={{ color: "#FFFFFF", fontSize: fontSize.caption, opacity: 0.85 }}>
              {offices.district_mapping_caveat}
            </Text>
          </>
        ) : null}
      </View>

      {conflictNote ? (
        <View
          accessibilityRole="alert"
          accessibilityLabel={`Source disagreement: ${conflictNote.note_text}`}
          style={{
            backgroundColor: colors.warningLight,
            borderColor: colors.warning,
            borderWidth: 1,
            borderRadius: radius.md,
            padding: spacing.md,
            gap: spacing.xs,
          }}
        >
          <Text style={{ fontSize: fontSize.caption, fontWeight: "700", color: colors.warning }}>
            Sources disagree — confirm before you travel
          </Text>
          <Text style={{ fontSize: fontSize.body, color: colors.textPrimary }}>{conflictNote.note_text}</Text>
        </View>
      ) : null}
    </View>
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
