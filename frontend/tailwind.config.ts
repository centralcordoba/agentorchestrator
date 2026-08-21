import type { Config } from "tailwindcss";

/**
 * Paleta inspirada en Claude Desktop: fondos cálidos casi blancos, texto tinta,
 * bordes suaves y un único acento terracota. Los colores semánticos y de agente
 * son oscuros y desaturados para leerse bien sobre fondo claro.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAF9F5",       // fondo de página
        surface: "#FFFFFF",     // paneles
        sunken: "#F4F2EC",      // zonas hundidas (inputs, código, cabeceras de tabla)
        line: {
          DEFAULT: "#E7E4DB",
          strong: "#D5D1C5",
        },
        ink: {
          900: "#1F1E1D",
          700: "#3D3A35",
          500: "#6B6760",
          400: "#8C887F",
          300: "#B3AFA6",
        },
        accent: {
          DEFAULT: "#C2562E",
          hover: "#A9482A",
          soft: "#F7EAE3",
          ring: "#E8B8A3",
        },
        ok: { DEFAULT: "#2E7D5B", soft: "#E7F2EC" },
        warn: { DEFAULT: "#9A6700", soft: "#FBF1DC" },
        danger: { DEFAULT: "#B3362B", soft: "#F9E8E5" },
        info: { DEFAULT: "#2F6F8F", soft: "#E6F0F5" },
        violet: { DEFAULT: "#5B4B8A", soft: "#EDEAF5" },
        rose: { DEFAULT: "#A8445C", soft: "#F7E8EC" },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "-apple-system", "Segoe UI", "Inter", "Helvetica Neue", "Arial", "sans-serif"],
        serif: ["Tiempos Headline", "Charter", "Georgia", "Times New Roman", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(31, 30, 29, 0.04), 0 1px 0 rgba(31, 30, 29, 0.02)",
        pop: "0 8px 24px rgba(31, 30, 29, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
