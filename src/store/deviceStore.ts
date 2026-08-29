import { create } from "zustand";
import { getOrCreateDeviceId } from "../api/deviceId";
import { getTranscript, postChatMessage, UnexpectedResponseError } from "../api/client";
import type { NetworkError, ServerError, UnreachableError } from "../api/errors";
import type { Citation, Question, Service } from "../api/types";
import { canonicalizeDistrict } from "../utils/districts";

export type ChatSendError = NetworkError | UnreachableError | ServerError | UnexpectedResponseError;

/**
 * One rendered chat bubble. A single backend turn can produce several
 * of these (an acknowledgement, an answer, a next question) — see
 * specs/mobile-app-integration's acknowledgement/citation/hint
 * requirements. Deliberately only four kinds — no separate "greeting"
 * or "out-of-scope" kind: design.md's finding is that the backend
 * doesn't distinguish those either, so this doesn't fabricate a
 * distinction that isn't real. A greeting/orientation message is just
 * an "answer" bubble with `grounded: true` and empty `citations`.
 */
export type ChatBubble =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "acknowledgement"; text: string }
  | { id: string; kind: "answer"; text: string; citations: Citation[]; grounded: boolean }
  | { id: string; kind: "question"; text: string; hint: string | null };

let bubbleCounter = 0;
function nextBubbleId(): string {
  bubbleCounter += 1;
  return `bubble-${bubbleCounter}`;
}

/**
 * Case creation has no direct "start service X" endpoint — routing is
 * entirely driven by matching specific phrases in the opening message
 * (`api/app/chat/service_routing.py`). Tapping a service card sends
 * one of these exact phrases (verified against that file's own phrase
 * sets) as a silent first turn — not shown as a user bubble, since the
 * citizen didn't actually type it — so the case lands on the tapped
 * service rather than falling through to the renewal default.
 *
 * KNOWN COUPLING (see design.md's Risks — added when this was
 * discovered during implementation): if service_routing.py's phrase
 * sets change, these strings need updating to match, or a tapped card
 * will silently misroute to renewal. Not detectable at compile time;
 * only a spec/manual-QA check against the real routing catches drift.
 */
const OPENING_MESSAGE_BY_SERVICE_CODE: Record<string, string> = {
  "passport-renewal": "i need to renew my passport",
  "passport-new": "i've never had a passport",
  "passport-lost-stolen": "my passport was stolen",
  "passport-amendment": "amend my passport",
  "passport-under-16": "my child needs a passport",
  "passport-child-deletion": "remove my child from my passport",
  "emergency-certificate": "i need an emergency certificate",
};

type DeviceState = {
  deviceId: string | null;
  caseId: string | null;
  selectedService: Service | null;
  bubbles: ChatBubble[];
  pendingQuestion: Question | null;
  /** True once a resolvable state is reached (no more questions pending, a case exists) — drives the "View your plan" affordance. */
  intakeComplete: boolean;
  /**
   * The citizen's own district answer, canonicalized — captured
   * client-side because the resolve response never exposes it
   * directly (see design.md's addendum). Null until the district
   * question is actually answered (and stays null for an overseas
   * applicant, who is never asked it at all).
   */
  citizenDistrict: string | null;

  initializing: boolean;
  initError: ChatSendError | null;

  sending: boolean;
  sendError: ChatSendError | null;
  /** The last message that failed to send, kept so retry doesn't require retyping. */
  pendingRetryMessage: string | null;

  initialize: () => Promise<void>;
  selectService: (service: Service, openingMessage?: string) => Promise<void>;
  changeService: () => void;
  sendMessage: (text: string, options?: { silent?: boolean }) => Promise<void>;
  retryLastMessage: () => Promise<void>;
};

function isChatSendError(error: unknown): error is ChatSendError {
  return (
    error instanceof Error &&
    (error.name === "NetworkError" ||
      error.name === "UnreachableError" ||
      error.name === "ServerError" ||
      error.name === "UnexpectedResponseError")
  );
}

export const useDeviceStore = create<DeviceState>((set, get) => ({
  deviceId: null,
  caseId: null,
  selectedService: null,
  bubbles: [],
  pendingQuestion: null,
  intakeComplete: false,
  citizenDistrict: null,

  initializing: true,
  initError: null,

  sending: false,
  sendError: null,
  pendingRetryMessage: null,

  initialize: async () => {
    set({ initializing: true, initError: null });
    try {
      const deviceId = await getOrCreateDeviceId();
      const transcript = await getTranscript(deviceId);
      const restored: ChatBubble[] = transcript.messages.map((message) => ({
        id: message.id,
        // Restored history has no structured citation objects (only
        // `cited_chunk_ids`, not full Citation records) — rendered as
        // plain text. Full citation rendering applies to live turns.
        kind: message.role === "user" ? "user" : "answer",
        text: message.content,
        ...(message.role === "assistant" ? { citations: [], grounded: true } : {}),
      })) as ChatBubble[];

      set({
        deviceId,
        caseId: transcript.case_id,
        bubbles: restored,
        initializing: false,
      });
    } catch (error) {
      if (isChatSendError(error)) {
        set({ initializing: false, initError: error });
      } else {
        throw error;
      }
    }
  },

  selectService: async (service, openingMessage) => {
    set({
      selectedService: service,
      bubbles: [],
      pendingQuestion: null,
      intakeComplete: false,
      caseId: null,
      sendError: null,
      citizenDistrict: null,
    });
    const message = openingMessage ?? OPENING_MESSAGE_BY_SERVICE_CODE[service.code];
    if (message) {
      await get().sendMessage(message, { silent: true });
    }
  },

  changeService: () => {
    set({
      selectedService: null,
      caseId: null,
      bubbles: [],
      pendingQuestion: null,
      intakeComplete: false,
      sendError: null,
      pendingRetryMessage: null,
      citizenDistrict: null,
    });
  },

  sendMessage: async (text: string, options?: { silent?: boolean }) => {
    const { deviceId, caseId, pendingQuestion } = get();
    const trimmed = text.trim();
    if (!trimmed) return;

    if (!options?.silent) {
      set((state) => ({
        bubbles: [...state.bubbles, { id: nextBubbleId(), kind: "user", text: trimmed }],
      }));
    }
    // Gap B: the resolve response never exposes the citizen's district
    // directly, so it's captured here, client-side, at the one point
    // it's knowable — the turn where the pending question being
    // answered was itself the district question. A failed
    // canonicalization keeps the previous value rather than clobbering
    // a known-good district with null on a bad guess.
    const districtUpdate =
      pendingQuestion?.answer_type === "district"
        ? { citizenDistrict: canonicalizeDistrict(trimmed) ?? get().citizenDistrict }
        : {};
    set({ sending: true, sendError: null, pendingRetryMessage: null, ...districtUpdate });

    try {
      const response = await postChatMessage({
        message: trimmed,
        case_id: caseId ?? undefined,
        device_ref: deviceId ?? undefined,
      });

      const newBubbles: ChatBubble[] = [];
      if (response.acknowledgement) {
        newBubbles.push({ id: nextBubbleId(), kind: "acknowledgement", text: response.acknowledgement });
      }
      if (response.answer) {
        newBubbles.push({
          id: nextBubbleId(),
          kind: "answer",
          text: response.answer.text,
          citations: response.answer.citations,
          grounded: response.answer.grounded,
        });
      }
      if (response.next_question) {
        newBubbles.push({
          id: nextBubbleId(),
          kind: "question",
          text: response.next_question.display_text,
          hint: response.next_question.hint,
        });
      }

      set((state) => ({
        caseId: response.case_id,
        bubbles: [...state.bubbles, ...newBubbles],
        pendingQuestion: response.next_question,
        intakeComplete: response.next_question === null,
        sending: false,
      }));
    } catch (error) {
      if (isChatSendError(error)) {
        set({ sending: false, sendError: error, pendingRetryMessage: trimmed });
      } else {
        set({ sending: false });
        throw error;
      }
    }
  },

  retryLastMessage: async () => {
    const { pendingRetryMessage } = get();
    if (!pendingRetryMessage) return;
    // The failed message was never shown as a bubble on failure in the
    // silent case, and was already shown for a normal send — re-adding
    // it here would duplicate it, so retry re-runs the same send path
    // without pushing a second user bubble.
    await get().sendMessage(pendingRetryMessage, { silent: true });
  },
}));
