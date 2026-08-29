import * as Network from "expo-network";

/**
 * Three distinct failure shapes — see specs/mobile-app-integration's
 * "Network failure, an unreachable backend, and a server error each
 * show a distinct message" requirement. Each screen renders its error
 * state from one of these, never from a generic caught exception.
 */

/** The device itself has no network connectivity. */
export class NetworkError extends Error {
  constructor() {
    super("No network connection.");
    this.name = "NetworkError";
  }
}

/** The device has connectivity, but the configured backend could not be reached (wrong LAN IP, backend not running, connection refused/timed out). */
export class UnreachableError extends Error {
  constructor() {
    super("Can't reach the GovAssist server.");
    this.name = "UnreachableError";
  }
}

/** The backend responded, but with a 5xx status. */
export class ServerError extends Error {
  status: number;

  constructor(status: number) {
    super(`The server had a problem (${status}).`);
    this.name = "ServerError";
    this.status = status;
  }
}

export type ApiError = NetworkError | UnreachableError | ServerError;

/**
 * `fetch` throwing (as opposed to resolving with a non-ok status) means
 * the request never reached the server at all — that's either no
 * connectivity on the device, or the configured backend being
 * unreachable. Distinguished via `expo-network`'s connectivity read;
 * where that's inconclusive, the safer default is `UnreachableError`
 * (a real backend problem the citizen can retry) rather than
 * `NetworkError` (which would incorrectly tell a citizen with working
 * internet that they have none).
 */
export async function classifyFetchFailure(): Promise<NetworkError | UnreachableError> {
  try {
    const state = await Network.getNetworkStateAsync();
    const online = state.isInternetReachable ?? state.isConnected ?? true;
    if (!online) {
      return new NetworkError();
    }
  } catch {
    // If the connectivity check itself fails, fall through to the
    // safer UnreachableError default below rather than guessing.
  }
  return new UnreachableError();
}
