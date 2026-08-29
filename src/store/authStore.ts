import { create } from "zustand";
import { signIn as apiSignIn, signUp as apiSignUp } from "../api/client";
import { clearStoredToken, getStoredEmail, getStoredToken, storeEmail, storeToken } from "../api/authToken";

type AuthState = {
  token: string | null;
  email: string | null;
  /** True until the stored token (if any) has been loaded at startup — gates rendering the same way deviceStore's `initializing` does. */
  initializing: boolean;

  signingIn: boolean;
  signUpError: string | null;
  signInError: string | null;

  initialize: () => Promise<void>;
  signUp: (email: string, password: string) => Promise<boolean>;
  signIn: (email: string, password: string) => Promise<boolean>;
  signOut: () => Promise<void>;
};

/**
 * Item 7 — deliberately separate from `deviceStore`: signing in must
 * never discard the device's existing case (an anonymous citizen who
 * used the app, then signed up, keeps their work) — the two stores
 * share no state and neither resets the other. `deviceStore`'s
 * `case_id`/`bubbles`/etc. are untouched by every action here.
 */
export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  email: null,
  initializing: true,

  signingIn: false,
  signUpError: null,
  signInError: null,

  initialize: async () => {
    const [token, email] = await Promise.all([getStoredToken(), getStoredEmail()]);
    set({ token, email, initializing: false });
  },

  signUp: async (email: string, password: string) => {
    set({ signingIn: true, signUpError: null });
    const trimmedEmail = email.trim();
    const result = await apiSignUp(trimmedEmail, password);
    if (!result.ok) {
      set({ signingIn: false, signUpError: result.message });
      return false;
    }
    await Promise.all([storeToken(result.token.access_token), storeEmail(trimmedEmail)]);
    set({ signingIn: false, token: result.token.access_token, email: trimmedEmail });
    return true;
  },

  signIn: async (email: string, password: string) => {
    set({ signingIn: true, signInError: null });
    const trimmedEmail = email.trim();
    const result = await apiSignIn(trimmedEmail, password);
    if (!result.ok) {
      set({ signingIn: false, signInError: result.message });
      return false;
    }
    await Promise.all([storeToken(result.token.access_token), storeEmail(trimmedEmail)]);
    set({ signingIn: false, token: result.token.access_token, email: trimmedEmail });
    return true;
  },

  signOut: async () => {
    await clearStoredToken();
    set({ token: null, email: null });
  },
}));
