/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./App.tsx", "./src/**/*.{js,jsx,ts,tsx}"],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        primary: "#1B4D89",
        "primary-dark": "#123661",
        "primary-light": "#E8F0FA",
        surface: "#FFFFFF",
        background: "#F7F8FA",
        border: "#E2E5EA",
        "text-primary": "#1A1D21",
        "text-secondary": "#5A6270",
        "text-muted": "#8A919E",
        success: "#1E7A46",
        "success-light": "#E6F4EC",
        warning: "#A85A00",
        "warning-light": "#FDF0E1",
        danger: "#B3261E",
        "danger-light": "#FCEBEA",
      },
      borderRadius: { sm: "6px", md: "10px", lg: "16px" },
      fontSize: {
        caption: "13px",
        body: "16px",
        "body-lg": "18px",
        title: "22px",
        heading: "28px",
      },
    },
  },
  plugins: [],
};