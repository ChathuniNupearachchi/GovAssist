import * as Network from "expo-network";
import { getServices, postResolve, UnexpectedResponseError } from "../client";
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
});
