/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        jamp: {
          base: "#080d18",
          panel: "#101827",
          elevated: "#172235",
          line: "#26364d",
          blue: "#38bdf8",
          green: "#34d399",
          amber: "#fbbf24",
          red: "#fb7185",
          muted: "#8da2bd",
        },
      },
      boxShadow: {
        glow: "0 0 28px rgba(56, 189, 248, 0.12)",
      },
    },
  },
  plugins: [],
};
