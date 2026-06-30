/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Enterprise light surfaces (warm paper)
        canvas: "#f4f3ee",
        surface: "#ffffff",
        line: "#e6e3da",
        "line-soft": "#efece4",
        // Institutional navy (sidebar, primary buttons, headings)
        navy: {
          950: "#0a0f1d",
          900: "#0f172a",
          800: "#1e293b",
          700: "#334155",
        },
        ink: "#0f172a",
        muted: "#64748b",
        faint: "#94a3b8",
        brand: {
          50: "#eff6ff",
          500: "#2563eb",
          600: "#1d4ed8",
        },
        risk: {
          low: "#059669",
          medium: "#d97706",
          high: "#ea580c",
          critical: "#dc2626",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        "label-caps": ["11px", { lineHeight: "16px", letterSpacing: "0.06em", fontWeight: "700" }],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.06)",
        pop: "0 8px 30px rgba(15,23,42,0.12)",
        ring: "0 0 0 4px rgba(37,99,235,0.12)",
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem",
      },
    },
  },
  plugins: [],
};
