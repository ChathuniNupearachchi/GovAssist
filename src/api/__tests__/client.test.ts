import * as Network from "expo-network";
import { deletePlan, getServices, listPlans, postResolve, savePlan, signIn, signUp, UnexpectedResponseError } from "../client";
import { NetworkError, ServerError, UnreachableError } from "../errors";

jest.mock("expo-network", () => ({
  getNetworkStateAsync: jest.fn(),
}));

const mockedGetNetworkStateAsync = Network.getNetworkStateAsync as jest.Mock;

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

describe("client request classification", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    mockedGetNetworkStateAsync.mockReset();
  });

  it("throws NetworkError when fetch fails and the device is offline", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("Network request failed"));
    mockedGetNetworkStateAsync.mockResolvedValue({ isConnected: false, isInternetReachable: false });

    await expect(getServices()).rejects.toBeInstanceOf(NetworkError);
  });

  it("throws UnreachableError when fetch fails but the device is online", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("Network request failed"));
    mockedGetNetworkStateAsync.mockResolvedValue({ isConnected: true, isInternetReachable: true });

    await expect(getServices()).rejects.toBeInstanceOf(UnreachableError);
  });

  it("throws ServerError on a 5xx response", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(500, { detail: "boom" }));

    await expect(getServices()).rejects.toBeInstanceOf(ServerError);
  });

  it("resolves normally on a 200 response", async () => {
    const services = [{ id: "1", code: "passport-renewal", name: "Renew", category: "passports" }];
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(200, services));

    await expect(getServices()).resolves.toEqual(services);
  });

  it("throws UnexpectedResponseError on a non-409, non-5xx error status", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(404, { detail: "not found" }));

    await expect(getServices()).rejects.toBeInstanceOf(UnexpectedResponseError);
  });

  it("resolve: a 409 becomes a not-ready result, not a thrown error", async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(jsonResponse(409, { detail: "Case is not ready to resolve — still pending: How old is the applicant?" }));

    const result = await postResolve("case-1");

    expect(result).toEqual({
      ready: false,
      pendingQuestion: "Case is not ready to resolve — still pending: How old is the applicant?",
    });
  });

  it("resolve: a 200 becomes a ready result carrying the resolution", async () => {
    const resolution = { requirements: [], fee: null, offices: null, amendment_alternative: null, scope_gate: null };
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(200, resolution));

    const result = await postResolve("case-1");

    expect(result).toEqual({ ready: true, resolution });
  });

  // --- Item 7: user accounts and saved plans ---

  it("signUp: a 409 (duplicate email) becomes a not-ok result, not a thrown error", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(409, { detail: "An account with this email already exists" }));

    const result = await signUp("taken@example.com", "hunter22");

    expect(result).toEqual({ ok: false, message: "An account with this email already exists" });
  });

  it("signUp: a 200 becomes an ok result carrying the token", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(200, { access_token: "abc", token_type: "bearer" }));

    const result = await signUp("new@example.com", "hunter22");

    expect(result).toEqual({ ok: true, token: { access_token: "abc", token_type: "bearer" } });
  });

  it("signIn: a 401 becomes a not-ok result, not a thrown error", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(401, { detail: "Incorrect email or password" }));

    const result = await signIn("someone@example.com", "wrong");

    expect(result).toEqual({ ok: false, message: "Incorrect email or password" });
  });

  it("signIn: a 200 becomes an ok result carrying the token", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(200, { access_token: "abc", token_type: "bearer" }));

    const result = await signIn("someone@example.com", "hunter22");

    expect(result).toEqual({ ok: true, token: { access_token: "abc", token_type: "bearer" } });
  });

  it("savePlan sends the bearer token and returns the saved plan", async () => {
    const savedPlan = { id: "p1", case_id: "c1", label: "My plan", created_at: "2026-01-01T00:00:00Z" };
    const fetchMock = jest.fn().mockResolvedValue(jsonResponse(200, savedPlan));
    global.fetch = fetchMock;

    const result = await savePlan("token-abc", "c1", "My plan");

    expect(result).toEqual(savedPlan);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer token-abc");
  });

  it("listPlans returns the array of saved plans", async () => {
    const plans = [{ id: "p1", case_id: "c1", label: "My plan", created_at: "2026-01-01T00:00:00Z" }];
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(200, plans));

    await expect(listPlans("token-abc")).resolves.toEqual(plans);
  });

  it("deletePlan resolves with no value on success", async () => {
    global.fetch = jest.fn().mockResolvedValue(jsonResponse(204, null));

    await expect(deletePlan("token-abc", "p1")).resolves.toBeUndefined();
  });
});
