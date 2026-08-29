import { API_BASE_URL } from "./config";
import { ServerError, classifyFetchFailure } from "./errors";
import type {
  AuthToken,
  CaseResolution,
  ChatMessageRequest,
  ChatMessageResponse,
  Question,
  SavedPlan,
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

// --- Item 7: user accounts and saved plans ---

/**
 * A 409 (duplicate email) and a 422 (bad email/short password) are
 * expected, meaningful outcomes a signup form displays inline — not
 * failures — so this returns a discriminated result the same way
 * `postResolve`'s 409 does, rather than throwing for them.
 */
export type SignUpResult = { ok: true; token: AuthToken } | { ok: false; message: string };

export async function signUp(email: string, password: string): Promise<SignUpResult> {
  const response = await request("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (response.status === 409 || response.status === 422) {
    const body = await safeJson(response);
    return { ok: false, message: body?.detail ?? "Couldn't create that account." };
  }
  if (!response.ok) {
    const body = await safeJson(response);
    throw new UnexpectedResponseError(response.status, body?.detail);
  }
  return { ok: true, token: (await response.json()) as AuthToken };
}

/** A 401 (wrong email/password) is likewise an expected outcome, not a failure. */
export type SignInResult = { ok: true; token: AuthToken } | { ok: false; message: string };

export async function signIn(email: string, password: string): Promise<SignInResult> {
  const response = await request("/auth/signin", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (response.status === 401) {
    const body = await safeJson(response);
    return { ok: false, message: body?.detail ?? "Incorrect email or password." };
  }
  if (!response.ok) {
    const body = await safeJson(response);
    throw new UnexpectedResponseError(response.status, body?.detail);
  }
  return { ok: true, token: (await response.json()) as AuthToken };
}

function _authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

export async function savePlan(token: string, caseId: string, label: string): Promise<SavedPlan> {
  const response = await request("/plans/save", {
    method: "POST",
    headers: _authHeaders(token),
    body: JSON.stringify({ case_id: caseId, label }),
  });
  if (!response.ok) {
    const body = await safeJson(response);
    throw new UnexpectedResponseError(response.status, body?.detail);
  }
  return (await response.json()) as SavedPlan;
}

export async function listPlans(token: string): Promise<SavedPlan[]> {
  const response = await request("/plans", { headers: _authHeaders(token) });
  if (!response.ok) {
    const body = await safeJson(response);
    throw new UnexpectedResponseError(response.status, body?.detail);
  }
  return (await response.json()) as SavedPlan[];
}

export async function deletePlan(token: string, planId: string): Promise<void> {
  const response = await request(`/plans/${planId}`, {
    method: "DELETE",
    headers: _authHeaders(token),
  });
  if (!response.ok) {
    const body = await safeJson(response);
    throw new UnexpectedResponseError(response.status, body?.detail);
  }
}
