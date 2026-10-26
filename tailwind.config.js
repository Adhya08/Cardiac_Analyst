/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: '#F6F8FA',
        surface: {
          DEFAULT: '#FFFFFF',
          secondary: '#FAFCFD',
          muted: '#F1F4F8',
          hover: '#F8FAFC',
        },
        navy: {
          950: '#0E1720',
          900: '#14222E',
          850: '#182B3A',
          800: '#1E3547',
          700: '#2A4962',
          600: '#3D6382',
        },
        slate: {
          900: '#0F172A',
          800: '#1E293B',
          700: '#334155',
          600: '#475569',
          500: '#64748B',
          400: '#94A3B8',
          300: '#CBD5E1',
          200: '#E2E8F0',
          100: '#F1F5F9',
          50: '#F8FAFC',
        },
        teal: {
          900: '#06423E',
          800: '#0B6862',
          700: '#0E7A73',
          600: '#0F8B83', // Primary Clinical Teal
          500: '#13ABA1',
          400: '#2CD5C9',
          200: '#B6EFEB',
          100: '#E3F8F6',
          50: '#F0FAF9',
        },
        blue: {
          900: '#1C3E7A',
          800: '#2854A3',
          700: '#3A6FC9',
          600: '#487FE0',
          500: '#5B8DEF', // Muted Blue Accent
          400: '#84ABF5',
          200: '#C8DBFB',
          100: '#EDF3FD',
          50: '#F6F9FE',
        },
        coral: {
          600: '#DC2626',
          500: '#EF4444',
          100: '#FEE2E2',
          50: '#FEF2F2',
        },
        amber: {
          600: '#D97706',
          500: '#F59E0B',
          100: '#FEF3C7',
          50: '#FFFBEB',
        },
        emerald: {
          700: '#047857',
          600: '#059669',
          500: '#10B981',
          100: '#D1FAE5',
          50: '#ECFDF5',
        },
        ecg: {
          gridMinor: '#FCE7EB',
          gridMajor: '#F8B6C3',
          trace: '#0E7A73',
          rhythm: '#182B3A',
        },
        border: {
          DEFAULT: '#E3E9EF',
          light: '#EDF2F7',
          dark: '#CBD5E1',
        },
      },
      boxShadow: {
        'panel': '0 1px 3px rgba(24, 43, 58, 0.04), 0 4px 12px rgba(24, 43, 58, 0.03)',
        'card': '0 1px 2px rgba(24, 43, 58, 0.05)',
        'elevated': '0 8px 24px -4px rgba(24, 43, 58, 0.08), 0 2px 6px -1px rgba(24, 43, 58, 0.04)',
        'modal': '0 20px 40px -8px rgba(24, 43, 58, 0.16), 0 4px 12px rgba(24, 43, 58, 0.08)',
        'button': '0 1px 2px rgba(15, 139, 131, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.2)',
        'button-secondary': '0 1px 2px rgba(24, 43, 58, 0.05), inset 0 1px 0 #FFFFFF',
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
        '3xl': '20px',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
