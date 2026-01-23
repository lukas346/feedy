/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/templates/**/*.html",
    "./src/static/js/**/*.js"
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Light theme colors
        light: {
          bg: '#fafafa',
          'bg-secondary': '#ffffff',
          card: '#ffffff',
          text: '#18181b',
          muted: '#71717a',
          border: '#e4e4e7',
          accent: '#2563eb',
          'accent-hover': '#1d4ed8',
        },
        // Dark theme colors
        dark: {
          bg: '#09090b',
          'bg-secondary': '#18181b',
          card: '#1c1c1f',
          text: '#fafafa',
          muted: '#a1a1aa',
          border: '#27272a',
          accent: '#3b82f6',
          'accent-hover': '#60a5fa',
        },
        // Monochrome theme colors (e-ink friendly)
        mono: {
          bg: '#ffffff',
          'bg-secondary': '#fafafa',
          card: '#ffffff',
          text: '#000000',
          muted: '#525252',
          border: '#000000',
          accent: '#000000',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      boxShadow: {
        'glow': '0 0 20px rgba(59, 130, 246, 0.3)',
        'glow-lg': '0 0 40px rgba(59, 130, 246, 0.4)',
        'inner-glow': 'inset 0 1px 0 rgba(255, 255, 255, 0.1)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-shine': 'linear-gradient(110deg, transparent 25%, rgba(255,255,255,0.1) 50%, transparent 75%)',
      },
    },
  },
  plugins: [],
}
