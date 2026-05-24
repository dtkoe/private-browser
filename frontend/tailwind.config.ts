import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#0b0d12", elevated: "#15181f", border: "#262a33" },
        accent: { DEFAULT: "#5b9eff", hover: "#7eb1ff" },
        muted: "#94a3b8",
      },
      fontFamily: { sans: ['"Inter"', "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
