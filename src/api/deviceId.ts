import * as SecureStore from "expo-secure-store";
import { randomUUID } from "expo-crypto";

const DEVICE_ID_KEY = "govassist_device_id";

let cachedDeviceId: string | null = null;

/**
 * Returns this device's persistent identity — generated once on first
 * call, stored in SecureStore, reused on every subsequent call and app
 * launch. Sent as `device_ref` on every request that accepts one, so a
 * returning device resumes its most recent unresolved case instead of
 * starting over. No account required.
 *
 * Cached in memory after the first read so repeated calls within a
 * session don't re-hit SecureStore (an async, non-trivial read) for a
 * value that never changes after first launch.
 */
export async function getOrCreateDeviceId(): Promise<string> {
  if (cachedDeviceId) {
    return cachedDeviceId;
  }

  const existing = await SecureStore.getItemAsync(DEVICE_ID_KEY);
  if (existing) {
    cachedDeviceId = existing;
    return existing;
  }

  const created = randomUUID();
  await SecureStore.setItemAsync(DEVICE_ID_KEY, created);
  cachedDeviceId = created;
  return created;
}
