import * as SecureStore from "expo-secure-store";

const AUTH_TOKEN_KEY = "govassist_auth_token";
// The JWT payload carries only the user id (`sub`), not the email — the
// email shown on the Profile screen is stored alongside the token,
// captured from the citizen's own signup/signin input rather than
// decoded from the token.
const AUTH_EMAIL_KEY = "govassist_auth_email";

/**
 * Item 7 — persists the citizen's JWT across app launches, the same
 * SecureStore pattern `deviceId.ts` already uses. Deliberately separate
 * from the device id: the device id always exists and never changes;
 * this is null until the citizen signs up/in, and is cleared on
 * logout — two different lifecycles, two different keys.
 */

export async function getStoredToken(): Promise<string | null> {
  return SecureStore.getItemAsync(AUTH_TOKEN_KEY);
}

export async function storeToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(AUTH_TOKEN_KEY, token);
}

export async function clearStoredToken(): Promise<void> {
  await SecureStore.deleteItemAsync(AUTH_TOKEN_KEY);
  await SecureStore.deleteItemAsync(AUTH_EMAIL_KEY);
}

export async function getStoredEmail(): Promise<string | null> {
  return SecureStore.getItemAsync(AUTH_EMAIL_KEY);
}

export async function storeEmail(email: string): Promise<void> {
  await SecureStore.setItemAsync(AUTH_EMAIL_KEY, email);
}
