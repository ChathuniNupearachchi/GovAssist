import { useEffect, useRef, useState } from "react";
import type { ComponentProps } from "react";
import { ActivityIndicator, Animated, Dimensions, Modal, Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Button } from "./Button";
import { useAuthStore } from "../store/authStore";
import { useDeviceStore } from "../store/deviceStore";
import { useUIStore } from "../store/uiStore";
import { navigationRef } from "../navigation/navigationRef";
import { deletePlan, listPlans } from "../api/client";
import type { SavedPlan } from "../api/types";
import { colors, spacing, fontSize, radius, touchTarget } from "../theme/tokens";

const DRAWER_WIDTH = Math.min(320, Dimensions.get("window").width * 0.85);

type Panel = "menu" | "my-plans";

/**
 * Item 7 — the slide-out drawer: Profile / My plans / Logout when
 * signed in; Sign in / Sign up when not (anonymous use stays a
 * first-class path, so this never blocks closing without signing in).
 * Mounted once at the app root (App.tsx), not per-screen — see
 * navigationRef.ts for why "reopen a plan" doesn't need this to be a
 * descendant of any particular screen.
 */
export function AccountDrawer() {
  const isOpen = useUIStore((s) => s.isDrawerOpen);
  const closeDrawer = useUIStore((s) => s.closeDrawer);
  const email = useAuthStore((s) => s.email);
  const token = useAuthStore((s) => s.token);
  const signOut = useAuthStore((s) => s.signOut);

  const [panel, setPanel] = useState<Panel>("menu");
  const [plans, setPlans] = useState<SavedPlan[] | null>(null);
  const [plansLoading, setPlansLoading] = useState(false);
  const [plansError, setPlansError] = useState<string | null>(null);

  const translateX = useRef(new Animated.Value(DRAWER_WIDTH)).current;

  useEffect(() => {
    Animated.timing(translateX, {
      toValue: isOpen ? 0 : DRAWER_WIDTH,
      duration: 220,
      useNativeDriver: true,
    }).start();
    if (isOpen) {
      setPanel("menu");
    }
  }, [isOpen, translateX]);

  const loadPlans = () => {
    if (!token) return;
    setPlansLoading(true);
    setPlansError(null);
    listPlans(token)
      .then((result) => {
        setPlans(result);
        setPlansLoading(false);
      })
      .catch(() => {
        setPlansError("Couldn't load your plans. Try again.");
        setPlansLoading(false);
      });
  };

  const openMyPlans = () => {
    setPanel("my-plans");
    loadPlans();
  };

  const reopenPlan = (plan: SavedPlan) => {
    // Reopening a saved plan means resuming that case as the device's
    // active one — the plan itself is never a stored snapshot (see
    // SavedPlan's own docstring on the backend); Plan screen re-fetches
    // the live resolve response for this case_id exactly like any
    // other visit there.
    useDeviceStore.setState({ caseId: plan.case_id, intakeComplete: true });
    closeDrawer();
    if (navigationRef.isReady()) {
      navigationRef.navigate("Plan");
    }
  };

  const handleDeletePlan = (plan: SavedPlan) => {
    if (!token) return;
    setPlans((prev) => (prev ? prev.filter((p) => p.id !== plan.id) : prev));
    deletePlan(token, plan.id).catch(() => {
      // Best-effort — reload the real list if the delete didn't
      // actually happen server-side, rather than leaving a stale
      // optimistic removal.
      loadPlans();
    });
  };

  const handleLogout = async () => {
    await signOut();
    closeDrawer();
  };

  const goToLogin = () => {
    closeDrawer();
    if (navigationRef.isReady()) {
      navigationRef.navigate("Login");
    }
  };

  return (
    <Modal visible={isOpen} transparent animationType="none" onRequestClose={closeDrawer}>
      <View style={{ flex: 1, flexDirection: "row" }}>
        <Pressable
          onPress={closeDrawer}
          accessibilityRole="button"
          accessibilityLabel="Close menu"
          style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.35)" }}
        />
        <Animated.View
          style={{
            width: DRAWER_WIDTH,
            backgroundColor: colors.surface,
            transform: [{ translateX }],
            paddingTop: spacing.xl,
          }}
        >
          {panel === "menu" ? (
            <View style={{ padding: spacing.lg, gap: spacing.md }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm }}>
                <Ionicons name="person-circle-outline" size={40} color={colors.primary} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: fontSize.bodyLarge, fontWeight: "700", color: colors.textPrimary }}>
                    {email ?? "Not signed in"}
                  </Text>
                  {!email ? (
                    <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>
                      Using GovAssist anonymously
                    </Text>
                  ) : null}
                </View>
              </View>

              {email ? (
                <>
                  <DrawerRow icon="person-outline" label="Profile" onPress={() => {}} />
                  <DrawerRow icon="document-text-outline" label="My plans" onPress={openMyPlans} />
                  <View style={{ height: 1, backgroundColor: colors.border, marginVertical: spacing.sm }} />
                  <DrawerRow icon="log-out-outline" label="Logout" onPress={handleLogout} />
                </>
              ) : (
                <>
                  <Text style={{ fontSize: fontSize.body, color: colors.textSecondary }}>
                    Sign in to save plans and pick up where you left off.
                  </Text>
                  <Button label="Sign in" onPress={goToLogin} fullWidth />
                </>
              )}
            </View>
          ) : (
            <View style={{ flex: 1 }}>
              <View
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  gap: spacing.sm,
                  paddingHorizontal: spacing.lg,
                  paddingBottom: spacing.md,
                }}
              >
                <Pressable
                  onPress={() => setPanel("menu")}
                  accessibilityRole="button"
                  accessibilityLabel="Back"
                  style={{ minWidth: touchTarget.min, minHeight: touchTarget.min, justifyContent: "center" }}
                >
                  <Ionicons name="chevron-back" size={fontSize.title} color={colors.primary} />
                </Pressable>
                <Text style={{ fontSize: fontSize.title, fontWeight: "700", color: colors.textPrimary }}>
                  My plans
                </Text>
              </View>

              <MyPlansList
                plans={plans}
                loading={plansLoading}
                error={plansError}
                onRetry={loadPlans}
                onOpen={reopenPlan}
                onDelete={handleDeletePlan}
              />
            </View>
          )}
        </Animated.View>
      </View>
    </Modal>
  );
}

function DrawerRow({
  icon,
  label,
  onPress,
}: {
  icon: ComponentIconName;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: spacing.md,
        minHeight: touchTarget.min,
      }}
    >
      <Ionicons name={icon} size={fontSize.title} color={colors.textSecondary} />
      <Text style={{ fontSize: fontSize.body, color: colors.textPrimary }}>{label}</Text>
    </Pressable>
  );
}

type ComponentIconName = ComponentProps<typeof Ionicons>["name"];

function MyPlansList({
  plans,
  loading,
  error,
  onRetry,
  onOpen,
  onDelete,
}: {
  plans: SavedPlan[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onOpen: (plan: SavedPlan) => void;
  onDelete: (plan: SavedPlan) => void;
}) {
  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.sm }}>
        <ActivityIndicator color={colors.primary} />
        <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>Loading your plans…</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={{ padding: spacing.lg, gap: spacing.sm }}>
        <Text style={{ fontSize: fontSize.body, color: colors.danger }}>{error}</Text>
        <Button label="Retry" onPress={onRetry} variant="secondary" />
      </View>
    );
  }

  if (!plans || plans.length === 0) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.lg }}>
        <Text style={{ fontSize: fontSize.body, color: colors.textMuted, textAlign: "center" }}>
          No saved plans yet. Save one from your Plan screen once it's ready.
        </Text>
      </View>
    );
  }

  return (
    <View style={{ paddingHorizontal: spacing.lg, gap: spacing.sm }}>
      {plans.map((plan) => (
        <View
          key={plan.id}
          style={{
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.md,
            padding: spacing.md,
            gap: spacing.xs,
          }}
        >
          <Pressable onPress={() => onOpen(plan)} accessibilityRole="button" accessibilityLabel={`Open ${plan.label}`}>
            <Text style={{ fontSize: fontSize.body, fontWeight: "700", color: colors.textPrimary }}>
              {plan.label}
            </Text>
            <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>
              {new Date(plan.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
            </Text>
          </Pressable>
          <Pressable
            onPress={() => onDelete(plan)}
            accessibilityRole="button"
            accessibilityLabel={`Delete ${plan.label}`}
            style={{ alignSelf: "flex-end", minHeight: touchTarget.min, justifyContent: "center", paddingHorizontal: spacing.xs }}
          >
            <Text style={{ fontSize: fontSize.caption, color: colors.danger }}>Remove</Text>
          </Pressable>
        </View>
      ))}
    </View>
  );
}
