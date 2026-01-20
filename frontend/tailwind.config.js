/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'obsidian': '#0A0A0A',
        'charcoal': '#1C1C1E',
        'warm-gold': '#C4A962',
        'soft-gold': '#D4BC7E',
        'ivory': '#FAFAF8',
        'mist': '#F5F5F3',
        'sand': '#E8E4DD',
      },
      fontFamily: {
        'serif': ['"Cormorant Garamond"', 'serif'],
        'sans': ['Inter', 'sans-serif'],
        'chinese': ['"Alibaba PuHuiTi"', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
      },
      boxShadow: {
        'luxury': '0 8px 40px rgba(196, 169, 98, 0.1)',
        'soft': '0 2px 12px rgba(0, 0, 0, 0.08)',
        'gold': '0 8px 40px rgba(196, 169, 98, 0.15)',
      },
      animation: {
        'float': 'float 3s ease-in-out infinite',
        'float-1': 'float1 4s ease-in-out infinite',
        'float-2': 'float2 5s ease-in-out infinite',
        'float-3': 'float3 6s ease-in-out infinite',
        'fade-in': 'fadeIn 0.8s ease-out',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        float1: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        float2: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        float3: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-15px)' },
        },
        fadeIn: {
          'from': { opacity: '0', transform: 'translateY(20px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      spacing: {
        '128': '32rem',
      },
    },
  },
  plugins: [],
}
