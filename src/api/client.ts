import { API_BASE_URL } from "./config";
import { ServerError, classifyFetchFailure } from "./errors";
import type {
  CaseResolution,
  ChatMessageRequest,
  ChatMessageResponse,
  Question,
  Service,
  StudioResolution,
  Transcript,
} from "./types";

/**
 * A non-5xx, non-ok HTTP response the caller didn't expect (a 404 for
 * a stale case id, a 422 from a malformed request). Distinct from
 * `NetworkError`/`UnreachableError`/`ServerError` in errors.ts —
 * those three are the taxonomy specs/mobile-app-integration requires
 * distinct messages for; this is the rarer, genuinely-unexpected case.
 */
export class UnexpectedResponseError extends Error {
  status: number;

  constructor(status: number, detail?: string) {
    super(detail ?? `Unexpected response (${status}).`);
    this.name = "UnexpectedResponseError";
    this.status = status;
  }
}

async function safeJson(response: Response): Promise<{ detail?: string } | null> {
  try {
    return (await response.json()) as { detail?: string };
  } catch {
    return null;
  }
}

/**
 * Every client function routes through this — one place that turns a
 * thrown `fetch` into a classified `NetworkError`/`UnreachableError`,
 * and a 5xx response into `ServerError`, so no call site has to
 * remember to do it.
 */
async function request(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw await classifyFetchFailure();
  }

  if (response.status >= 500) {
    throw new ServerError(response.status);
  }

  return response;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await request(path);
  if (!response.ok) {
    const body = await safeJson(response);
    throw new UnexpectedResponseError(response.status, body?.detail);
  }
  return (await response.json()) as T;
}

export async function getServices(): Promise<Service[]> {
  return getJson<Service[]>("/services");
}

export async function postChatMessage(body: ChatMessageRequest): Promise<ChatMessageResponse> {
  const response = await request("/chat/message", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorBody = await safeJson(response);
    throw new UnexpectedResponseError(response.status, errorBody?.detail);
  }
  return (await response.json()) as ChatMessageResponse;
}

export async function getNextQuestion(caseId: string): Promise<Question | null> {
  return getJson<Question | null>(`/case/${caseId}/next-question`);
}

/**
 * `POST /case/{id}/resolve` returns a 409 (not an error the citizen
 * should see as a failure) whenever intake isn't complete yet — the
 * response body names the still-pending question. Modeled as a
 * discriminated union rather than a thrown error, since it's an
 * expected, meaningful outcome, not a failure.
 */
export type ResolveResult =
  | { ready: true; resolution: CaseResolution }
  | { ready: false; pendingQuestion: string | null };

export async function postResolve(caseId: string): Promise<ResolveResult> {
  const response = await request(`/case/${caseId}/resolve`, { method: "POST" });

  if (response.status === 409) {
    const body = await safeJson(response);
    return { ready: false, pendingQuestion: body?.detail ?? null };
  }

  if (!response.ok) {
    const body = await safeJson(response);
    throw new UnexpectedResponseError(response.status, body?.detail);
  }

  return { ready: true, resolution: (await response.json()) as CaseResolution };
}

export async function getTranscript(deviceRef: string): Promise<Transcript> {
  return getJson<Transcript>(`/chat/transcript?device_ref=${encodeURIComponent(deviceRef)}`);
}

export async function getStudios(district: string): Promise<StudioResolution> {
  return getJson<StudioResolution>(`/studios?district=${encodeURIComponent(district)}`);
}
