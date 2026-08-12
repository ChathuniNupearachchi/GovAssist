import { useEffect, useRef, useState } from "react";
import {
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
import { colors, spacing, fontSize, radius, touchTarget } from "../theme/tokens";

type Props = NativeStackScreenProps<RootStackParamList, "Services">;

type IconName = ComponentProps<typeof Ionicons>["name"];
type Tab = "services" | "ask";

type ChatMessage = {
  id: string;
  from: "user" | "ai";
  text: string;
};

type ServiceOption = {
  id: string;
  name: string;
  description: string;
  duration: string;
  fee: string;
  icon: IconName;
  firstQuestion: string;
};

const SERVICES: ServiceOption[] = [
  {
    id: "new",
    name: "New passport",
    description: "First-time applicants",
    duration: "30 working days",
    fee: "LKR 10,000",
    icon: "document-text-outline",
    firstQuestion: "Is this your first Sri Lankan passport application?",
  },
  {
    id: "renew",
    name: "Renew passport",
    description: "Your current passport has expired or is expiring",
    duration: "30 working days",
    fee: "LKR 10,000",
    icon: "sync-outline",
    firstQuestion: "Do you still have your current passport, or has it been lost or stolen?",
  },
  {
    id: "lost",
    name: "Replace a lost passport",
    description: "Lost or stolen — additional charges apply",
    duration: "30 working days",
    fee: "from LKR 25,000",
    icon: "warning-outline",
    firstQuestion: "When did you realise your passport was lost or stolen?",
  },
  {
    id: "urgent",
    name: "Urgent service",
    description: "Same-day, Head Office only",
    duration: "Same day",
    fee: "LKR 20,000",
    icon: "flash-outline",
    firstQuestion: "Do you have a confirmed travel date within the next few days?",
  },
];

const FOLLOW_UP_SCRIPT = [
  "Thanks — noted. Since your name has changed, I'll add a marriage certificate to your checklist.",
  "One more thing: do you still have your expired passport with you?",
];

const ASK_SCRIPT = [
  "It sounds like you need to renew your passport. Since your name has changed, I'll add your marriage certificate to your checklist.",
  "One quick question: do you still have your expired passport?",
];

export function ServicesScreen({ navigation, route }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>(route.params?.initialTab ?? "services");
  const [selectedService, setSelectedService] = useState<ServiceOption | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [scriptStep, setScriptStep] = useState(0);
  const [planReady, setPlanReady] = useState(false);
  const scrollRef = useRef<ScrollView>(null);
  const idCounter = useRef(0);
  const nextId = () => `m${idCounter.current++}`;

  useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  const selectService = (service: ServiceOption) => {
    setSelectedService(service);
    setMessages([
      {
        id: nextId(),
        from: "ai",
        text: `I can help you with ${service.name.toLowerCase()}. ${service.firstQuestion}`,
      },
    ]);
    setScriptStep(0);
    setPlanReady(false);
    setDraft("");
  };

  const changeService = () => {
    setSelectedService(null);
    setMessages([]);
    setScriptStep(0);
    setPlanReady(false);
    setDraft("");
  };

  const switchTab = (tab: Tab) => {
    setActiveTab(tab);
    setSelectedService(null);
    setMessages([]);
    setScriptStep(0);
    setPlanReady(false);
    setDraft("");
  };

  const sendMessage = () => {
    const text = draft.trim();
    if (!text) return;

    const script = activeTab === "ask" ? ASK_SCRIPT : FOLLOW_UP_SCRIPT;
    const userMessage: ChatMessage = { id: nextId(), from: "user", text };

    if (activeTab === "ask" && scriptStep === 0) {
      // First reply in Ask mode surfaces both scripted lines together.
      setMessages((prev) => [
        ...prev,
        userMessage,
        { id: nextId(), from: "ai", text: script[0] },
        { id: nextId(), from: "ai", text: script[1] },
      ]);
      setScriptStep(script.length);
      setPlanReady(true);
    } else if (scriptStep < script.length) {
      const reply = script[scriptStep];
      const isLast = scriptStep === script.length - 1;
      setMessages((prev) => [...prev, userMessage, { id: nextId(), from: "ai", text: reply }]);
      setScriptStep((s) => s + 1);
      if (isLast) setPlanReady(true);
    } else {
      setMessages((prev) => [...prev, userMessage]);
    }

    setDraft("");
  };

  const showChat = activeTab === "ask" || selectedService !== null;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={["bottom", "left", "right"]}>
      <View style={{ flexDirection: "row", padding: spacing.md, gap: spacing.sm }}>
        <TabButton label="Services" active={activeTab === "services"} onPress={() => switchTab("services")} />
        <TabButton label="Ask" active={activeTab === "ask"} onPress={() => switchTab("ask")} />
      </View>

      {!showChat ? (
        <ScrollView contentContainerStyle={{ padding: spacing.md, paddingTop: 0, gap: spacing.md }}>
          {SERVICES.map((service) => (
            <Card key={service.id} onPress={() => selectService(service)}>
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
                  <Ionicons name={service.icon} size={20} color={colors.primary} />
                </View>
                <View style={{ flex: 1, gap: spacing.xs }}>
                  <Text style={{ fontSize: fontSize.bodyLarge, fontWeight: "700", color: colors.textPrimary }}>
                    {service.name}
                  </Text>
                  <Text style={{ fontSize: fontSize.body, color: colors.textSecondary }}>
                    {service.description}
                  </Text>
                  <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.xs }}>
                    <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.xs }}>
                      <Ionicons name="time-outline" size={fontSize.caption} color={colors.textMuted} />
                      <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>{service.duration}</Text>
                    </View>
                    <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.xs }}>
                      <Ionicons name="pricetag-outline" size={fontSize.caption} color={colors.textMuted} />
                      <Text style={{ fontSize: fontSize.caption, color: colors.textMuted }}>{service.fee}</Text>
                    </View>
                  </View>
                </View>
              </View>
            </Card>
          ))}
        </ScrollView>
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
            {messages.length === 0 ? (
              <Text style={{ fontSize: fontSize.body, color: colors.textMuted }}>
                Describe your situation and I'll work out what you need.
              </Text>
            ) : null}

            {messages.map((message) => (
              <ChatBubble key={message.id} message={message} />
            ))}

            {planReady ? (
              <Button label="View your plan" onPress={() => navigation.navigate("Plan")} fullWidth />
            ) : null}
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
              }}
              onSubmitEditing={sendMessage}
              returnKeyType="send"
            />
            <Pressable
              onPress={sendMessage}
              accessibilityRole="button"
              accessibilityLabel="Send message"
              style={{
                width: touchTarget.min,
                height: touchTarget.min,
                borderRadius: radius.pill,
                backgroundColor: colors.primary,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Ionicons name="send" size={fontSize.body} color="#FFFFFF" />
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
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

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.from === "user";

  return (
    <View style={{ flexDirection: "row", justifyContent: isUser ? "flex-end" : "flex-start", gap: spacing.sm }}>
      {!isUser ? (
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
      ) : null}

      <View
        style={{
          maxWidth: "78%",
          padding: spacing.md,
          borderRadius: radius.lg,
          backgroundColor: isUser ? colors.primary : colors.surface,
          borderWidth: isUser ? 0 : 1,
          borderColor: colors.border,
        }}
      >
        <Text style={{ fontSize: fontSize.body, color: isUser ? "#FFFFFF" : colors.textPrimary }}>
          {message.text}
        </Text>
      </View>
    </View>
  );
}
