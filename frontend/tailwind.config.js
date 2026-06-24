/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark surface palette
        surface: {
          950: "#0a0e14",
          900: "#0e131b",
          850: "#121826",
          800: "#161d2b",
          700: "#1f2937",
          600: "#2a3543",
        },
        brand: {
          DEFAULT: "#0ea5e9",
          50: "#e0f2fe",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
        },
        accent: "#a855f7",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
