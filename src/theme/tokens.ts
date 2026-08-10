export const colors = {
  primary: "#1B4D89",      // deep institutional blue
  primaryDark: "#123661",
  primaryLight: "#E8F0FA",

  surface: "#FFFFFF",
  background: "#F7F8FA",
  border: "#E2E5EA",

  textPrimary: "#1A1D21",
  textSecondary: "#5A6270",
  textMuted: "#8A919E",

  success: "#1E7A46",
  successLight: "#E6F4EC",
  warning: "#A85A00",
  warningLight: "#FDF0E1",
  danger: "#B3261E",
  dangerLight: "#FCEBEA",
} as const;

export const spacing = {
  xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48,
} as const;

export const radius = {
  sm: 6, md: 10, lg: 16, pill: 999,
} as const;

export const fontSize = {
  caption: 13,
  body: 16,      // never smaller for body text
  bodyLarge: 18,
  title: 22,
  heading: 28,
} as const;

export const touchTarget = {
  min: 48,       // accessibility floor
  comfortable: 56,
} as const;