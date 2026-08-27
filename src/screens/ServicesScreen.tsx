import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import type { ComponentProps } from "react";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { SourceCitation } from "../components/SourceCitation";
import { getServices, UnexpectedResponseError } from "../api/client";
import type { NetworkError, ServerError, UnreachableError } from "../api/errors";
import type { Service } from "../api/types";
import { formatCitation } from "../utils/citation";
import { useDeviceStore, type ChatBubble } from "../store/deviceStore";
import { colors, spacing, fontSize, radius, touchTarget } from "../theme/tokens";

type Props = NativeStackScreenProps<RootStackParamList, "Services">;

type IconName = ComponentProps<typeof Ionicons>["name"];
type Tab = "services" | "ask";

type ServicesListError = NetworkError | UnreachableError | ServerError | UnexpectedResponseError;

function isServicesListError(error: unknown): error is ServicesListError {
  return (
    error instanceof Error &&
    (error.name === "NetworkError" ||
      error.name === "UnreachableError" ||
      error.name === "ServerError" ||
      error.name === "UnexpectedResponseError")
  );
}

/**
 * `ServiceOut` carries only `{id, code, name, category}` — no audience,
 * timeline or fee (design.md finding 3). This is static presentational
 * copy sourced from proposal.md's own per-service descriptions, keyed
 * by the same service codes `deviceStore`'s
 * `OPENING_MESSAGE_BY_SERVICE_CODE` uses. A flat fee is shown only
 * where one genuinely exists; every other service gets a qualifier
 * rather than a misleading single number (fee depends on the citizen's
 * situation — validity tier, normal/urgent, penalty tiers, etc).
 */
const SERVICE_META: Record<string, { audience: string; fee: string; icon: IconName }> = {
  "passport-renewal": {
    audience: "Your current passport has expired or is expiring",
    fee: "Fee depends on your situation",
    icon: "sync-outline",
  },
  "passport-new": {
    audience: "First-time applicants who have never held a Sri Lankan passport",
    fee: "Fee depends on your situation",
    icon: "document-text-outline",
  },
  "passport-lost-stolen": {
    audience: "Your passport was lost or stolen",
    fee: "Fee depends on your situation",
    icon: "warning-outline",
  },
  "passport-amendment": {
    audience: "Correcting or updating details on a valid passport",
    fee: "LKR 1,200",
    icon: "create-outline",
  },
  "passport-under-16": {
    audience: "Applying for a passport for a child under 16",
    fee: "Fee depends on your situation",
    icon: "people-outline",
  },
  "passport-child-deletion": {
    audience: "Removing a child's name from a parent's passport",
    fee: "LKR 1,200",
    icon: "person-remove-outline",
  },
  "emergency-certificate": {
    audience: "Sri Lankan citizens in India or Nepal needing an emergency travel document",
    fee: "LKR 500",
    icon: "alert-circle-outline",
  },
};

const DEFAULT_META = { audience: "Immigration & Emigration service", fee: "Fee depends on your situation", icon: "document-text-outline" as IconName };

export function ServicesScreen({ navigation, route }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>(route.params?.initialTab ?? "services");
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<ScrollView>(null);

  const [services, setServices] = useState<Service[] | null>(null);
  const [servicesLoading, setServicesLoading] = useState(true);
  const [servicesError, setServicesError] = useState<ServicesListError | null>(null);

  const deviceId = useDeviceStore((s) => s.deviceId);
  const selectedService = useDeviceStore((s) => s.selectedService);
  const bubbles = useDeviceStore((s) => s.bubbles);
  const intakeComplete = useDeviceStore((s) => s.intakeComplete);
  const caseId = useDeviceStore((s) => s.caseId);
  const initializing = useDeviceStore((s) => s.initializing);
  const initError = useDeviceStore((s) => s.initError);
  const sending = useDeviceStore((s) => s.sending);
  const sendError = useDeviceStore((s) => s.sendError);
  const initialize = useDeviceStore((s) => s.initialize);
  const selectService = useDeviceStore((s) => s.selectService);
  const changeService = useDeviceStore((s) => s.changeService);
  const sendMessage = useDeviceStore((s) => s.sendMessage);
  const retryLastMessage = useDeviceStore((s) => s.retryLastMessage);

  const loadServices = () => {
    setServicesLoading(true);
    setServicesError(null);
    getServices()
      .then((result) => {
        setServices(result);
        setServicesLoading(false);
      })
      .catch((error) => {
        if (isServicesListError(error)) {
          setServicesError(error);
          setServicesLoading(false);
        } else {
          setServicesLoading(false);
          throw error;
        }
      });
  };

  useEffect(() => {
    loadServices();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [bubbles, sending]);

  const showChat = activeTab === "ask" || selectedService !== null;

  const handleSend = () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    sendMessage(text);
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
      <View style={{ flexDirection: "row", padding: spacing.md, gap: spacing.sm }}>
        <TabButton label="Services" active={activeTab === "services"} onPress={() => setActiveTab("services")} />
        <TabButton label="Ask" active={activeTab === "ask"} onPress={() => setActiveTab("ask")} />
      </View>

      {!showChat ? (
        <ServicesList
          services={services}
          loading={servicesLoading}
          error={servicesError}
          onRetry={loadServices}
          onSelect={(service) => selectService(service)}
        />
      ) : (
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
        >
          {selectedService ? (
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                paddingHorizontal: spacing.md,
                paddingBottom: spacing.sm,
                borderBottomWidth: 1,
                borderBottomColor: colors.border,
              }}
            >
              <Text style={{ fontSize: fontSize.body, fontWeight: "700", color: colors.primary, flexShrink: 1 }}>
                {selectedService.name} · Immigration & Emigration
              </Text>
              <Pressable
                onPress={changeService}
                accessibilityRole="button"
                accessibilityLabel="Change service"
                style={{ minHeight: touchTarget.min, justifyContent: "center", paddingLeft: spacing.sm }}
              >
                <Text style={{ fontSize: fontSize.body, color: colors.primary, fontWeight: "600" }}>Change</Text>
              </Pressable>
            </View>
          ) : null}

          <ScrollView ref={scrollRef} contentContainerStyle={{ padding: spacing.md, gap: spacing.md }}>
            {initializing ? (
              <View style={{ paddingVertical: spacing.xl, alignItems: "center", gap: spacing.sm }}>
                <ActivityIndicator color={colors.primary} />
                <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>
                  Restoring your conversation…
                </Text>
              </View>
            ) : initError ? (
              <ErrorNotice error={initError} onRetry={initialize} />
            ) : (
              <>
                {bubbles.length === 0 ? (
                  <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>
                    {activeTab === "ask"
                      ? "Describe your situation and I'll work out what you need."
                      : "Starting your conversation…"}
                  </Text>
                ) : null}

                {bubbles.map((bubble) => (
                  <ChatBubbleView key={bubble.id} bubble={bubble} />
                ))}

                {sending ? <ThinkingIndicator /> : null}

                {sendError ? (
                  <ErrorNotice error={sendError} onRetry={retryLastMessage} />
                ) : null}

                {intakeComplete && caseId ? (
                  <Button label="View your plan" onPress={() => navigation.navigate("Plan")} fullWidth />
                ) : null}
              </>
            )}
          </ScrollView>

          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: spacing.sm,
              padding: spacing.md,
              borderTopWidth: 1,
              borderTopColor: colors.border,
              backgroundColor: colors.surface,
            }}
          >
            <TextInput
              value={draft}
              onChangeText={setDraft}
              editable={!sending && !initializing && !!deviceId}
              placeholder={activeTab === "ask" ? "Describe your situation..." : "Type your reply..."}
              placeholderTextColor={colors.textMuted}
              accessibilityLabel="Chat message"
              style={{
                flex: 1,
                minHeight: touchTarget.min,
                borderWidth: 1,
                borderColor: colors.border,
                borderRadius: radius.pill,
                paddingHorizontal: spacing.md,
                fontSize: fontSize.body,
                color: colors.textPrimary,
                backgroundColor: colors.background,
                opacity: sending ? 0.6 : 1,
              }}
              onSubmitEditing={handleSend}
              returnKeyType="send"
            />
            <Pressable
              onPress={handleSend}
              disabled={sending || initializing || !deviceId}
              accessibilityRole="button"
              accessibilityLabel="Send message"
              accessibilityState={{ disabled: sending || initializing || !deviceId }}
              style={{
                width: touchTarget.min,
                height: touchTarget.min,
                borderRadius: radius.pill,
                backgroundColor: colors.primary,
                alignItems: "center",
                justifyContent: "center",
                opacity: sending || initializing || !deviceId ? 0.5 : 1,
              }}
            >
              {sending ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <Ionicons name="send" size={fontSize.body} color="#FFFFFF" />
              )}
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}

function ServicesList({
  services,
  loading,
  error,
  onRetry,
  onSelect,
}: {
  services: Service[] | null;
  loading: boolean;
  error: ServicesListError | null;
  onRetry: () => void;
  onSelect: (service: Service) => void;
}) {
  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: spacing.sm }}>
        <ActivityIndicator color={colors.primary} />
        <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>Loading services…</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={{ flex: 1, padding: spacing.md, justifyContent: "center" }}>
        <ErrorNotice error={error} onRetry={onRetry} />
      </View>
    );
  }

  if (!services || services.length === 0) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.md }}>
        <Text style={{ fontSize: fontSize.body, color: colors.textMuted, textAlign: "center" }}>
          No services are available right now.
        </Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.md, paddingTop: 0, gap: spacing.md }}>
      {services.map((service) => {
        const meta = SERVICE_META[service.code] ?? DEFAULT_META;
        return (
          <Card key={service.id} onPress={() => onSelect(service)}>
            <View style={{ flexDirection: "row", gap: spacing.md }}>
              <View
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: radius.md,
                  backgroundColor: colors.primaryLight,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Ionicons name={meta.icon} size={20} color={colors.primary} />
              </View>
              <View style={{ flex: 1, gap: spacing.xs }}>
                <Text style={{ fontSize: fontSize.bodyLarge, fontWeight: "700", color: colors.textPrimary }}>
                  {service.name}
                </Text>
                <Text style={{ fontSize: fontSize.body, color: colors.textSecondary }}>{meta.audience}</Text>
                <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.xs }}>
                  <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.xs }}>
                    <Ionicons name="pricetag-outline" size={fontSize.caption} color={colors.textMuted} />
                    <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>{meta.fee}</Text>
                  </View>
                </View>
              </View>
            </View>
          </Card>
        );
      })}
    </ScrollView>
  );
}

function TabButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  const [pressed, setPressed] = useState(false);

  return (
    <Pressable
      onPress={onPress}
      onPressIn={() => setPressed(true)}
      onPressOut={() => setPressed(false)}
      accessibilityRole="tab"
      accessibilityState={{ selected: active }}
      accessibilityLabel={label}
      style={{
        flex: 1,
        minHeight: touchTarget.min,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: radius.md,
        backgroundColor: active ? colors.primary : pressed ? colors.primaryLight : colors.surface,
        borderWidth: 1,
        borderColor: active ? colors.primary : colors.border,
      }}
    >
      <Text style={{ fontSize: fontSize.body, fontWeight: "700", color: active ? "#FFFFFF" : colors.textSecondary }}>
        {label}
      </Text>
    </Pressable>
  );
}

/**
 * Renders every `ChatBubble` kind `deviceStore` produces. Deliberately
 * no separate "greeting"/"out-of-scope" visual — design.md's finding 2:
 * the backend has no structured signal for those, only
 * `answer.grounded`. A greeting/orientation message is just a
 * `grounded: true` answer with no citations, rendered as a normal
 * assistant message — not styled as an error either way.
 */
function ChatBubbleView({ bubble }: { bubble: ChatBubble }) {
  if (bubble.kind === "user") {
    return (
      <View style={{ flexDirection: "row", justifyContent: "flex-end" }}>
        <View
          style={{
            maxWidth: "78%",
            padding: spacing.md,
            borderRadius: radius.lg,
            backgroundColor: colors.primary,
          }}
        >
          <Text style={{ fontSize: fontSize.body, color: "#FFFFFF" }}>{bubble.text}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={{ flexDirection: "row", justifyContent: "flex-start", gap: spacing.sm }}>
      <View
        style={{
          width: 32,
          height: 32,
          borderRadius: radius.pill,
          backgroundColor: colors.primary,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ color: "#FFFFFF", fontSize: fontSize.caption, fontWeight: "700" }}>GA</Text>
      </View>

      <View
        style={{
          maxWidth: "78%",
          padding: spacing.md,
          borderRadius: radius.lg,
          backgroundColor: colors.surface,
          borderWidth: 1,
          borderColor: colors.border,
          gap: spacing.xs,
        }}
      >
        <Text
          style={{
            fontSize: fontSize.body,
            color: colors.textPrimary,
            fontStyle: bubble.kind === "acknowledgement" ? "italic" : "normal",
          }}
        >
          {bubble.text}
        </Text>

        {bubble.kind === "question" && bubble.hint ? (
          <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>{bubble.hint}</Text>
        ) : null}

        {bubble.kind === "answer" && bubble.grounded && bubble.citations.length > 0
          ? bubble.citations.map((citation, index) => (
              <SourceCitation key={`${citation.source_document_id}-${index}`} text={formatCitation(citation)} />
            ))
          : null}
      </View>
    </View>
  );
}

function ThinkingIndicator() {
  return (
    <View style={{ flexDirection: "row", justifyContent: "flex-start", gap: spacing.sm }}>
      <View
        style={{
          width: 32,
          height: 32,
          borderRadius: radius.pill,
          backgroundColor: colors.primary,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Text style={{ color: "#FFFFFF", fontSize: fontSize.caption, fontWeight: "700" }}>GA</Text>
      </View>
      <View
        style={{
          padding: spacing.md,
          borderRadius: radius.lg,
          backgroundColor: colors.surface,
          borderWidth: 1,
          borderColor: colors.border,
          flexDirection: "row",
          alignItems: "center",
          gap: spacing.sm,
        }}
      >
        <ActivityIndicator color={colors.primary} size="small" />
        <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>Thinking…</Text>
      </View>
    </View>
  );
}

/** Renders one of the three distinct error messages (specs/mobile-app-integration) with retry, never a generic "something went wrong". */
function ErrorNotice({ error, onRetry }: { error: ServicesListError; onRetry: () => void }) {
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
      <Text style={{ fontSize: fontSize.body, color: colors.danger }}>{error.message}</Text>
      <Button label="Retry" onPress={onRetry} variant="secondary" />
    </View>
  );
}
