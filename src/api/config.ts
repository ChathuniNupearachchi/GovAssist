/**
 * API base URL, read from env at module load (app startup) rather than
 * per-request — an unset value fails loudly once, immediately, instead
 * of producing a confusing "network request failed" on the first chat
 * message a citizen sends. See README's "Running on a physical device"
 * section: this must be the laptop's LAN IP, not "localhost" — on a
 * physical phone, "localhost" resolves to the phone itself.
 */

const rawBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;

if (!rawBaseUrl) {
  throw new Error(
    "EXPO_PUBLIC_API_BASE_URL is not set. Copy .env.example to .env, " +
      "set it to your laptop's LAN IP (see the README's \"Running on a " +
      'physical device" section), then restart `expo start`.'
  );
}

export const API_BASE_URL: string = rawBaseUrl;
