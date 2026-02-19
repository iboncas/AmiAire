/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'ami-azul': '#0a2f4d',
        'ami-azul-claro': '#0f4d80',
        'ami-oro': '#ff9a00',
        'ami-gris': '#f5f7f9',
      },
    },
  },
  plugins: [],
}
