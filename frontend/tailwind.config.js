/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#0b0f14',
          panel: '#0f1620',
          stroke: '#1a2330',
          accent: {
            cyan: '#00D1FF',
            green: '#7CFFB2',
          },
          code: '#0b121a',
        },
        // ACFRL dashboard palette: dark green / charcoal + soft neon green
        acfrl: {
          bg: '#050a08',
          bg2: '#07110d',
          panel: '#0c1714',
          panel2: '#0f1d18',
          stroke: '#1c3329',
          muted: '#7d9b8e',
          text: '#e7f3ed',
          neon: '#4cf2a0',
          neonDim: '#2bbf7a',
          glow: 'rgba(76, 242, 160, 0.18)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        neon: '0 0 0 1px rgba(76, 242, 160, 0.25), 0 0 24px rgba(76, 242, 160, 0.12)',
      },
    },
  },
  plugins: [],
}

