import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        panel: "#ffffff",
        panelAlt: "#f8fafc",
        edge: "#d0d9e4",
        accent: "#1d4ed8",
        danger: "#b42318",
        ok: "#027a48"
      }
    }
  },
  plugins: []
};

export default config;
