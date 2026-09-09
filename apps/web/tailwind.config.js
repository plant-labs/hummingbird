/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14201b",
        moss: "#1f3d32",
        fern: "#2f6b4f",
        sand: "#e8e2d6",
        mist: "#f3efe6",
        alert: "#c45c26",
        signal: "#0e7c6b",
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
