// Runs before any test module loads. src/api/config.ts throws at
// import time if EXPO_PUBLIC_API_BASE_URL is unset (by design — see
// its own docstring) so any test importing src/api/client.ts needs
// this set first.
process.env.EXPO_PUBLIC_API_BASE_URL = "http://192.0.2.1:8000";
