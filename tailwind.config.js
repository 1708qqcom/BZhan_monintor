/** @type {import('tailwindcss').Config} */
module.exports = {
  // 扫描模板与静态 JS 中的 class 字面量，JIT 按需生成 CSS
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#0D9488',
          light: '#14B8A6',
          dark: '#0F766E',
          50: '#F0FDFA',
          100: '#CCFBF1',
          200: '#99F6E4',
        },
        accent: '#EA580C',
        bilibili: {
          pink: '#FB7299',
          blue: '#00A1D6',
        },
      },
      // 系统字体栈：去除 Google Fonts 依赖，中文环境显示更清晰
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif',
        ],
        mono: [
          '"SF Mono"',
          '"Cascadia Code"',
          'Consolas',
          '"Liberation Mono"',
          'Menlo',
          'monospace',
        ],
      },
      animation: {
        'fade-in-up': 'fadeInUp 400ms ease forwards',
        'slide-down': 'slideDown 400ms cubic-bezier(0.4, 0, 0.2, 1)',
        'pulse-ring': 'pulseRing 2s ease-out infinite',
        'skeleton': 'skeletonLoading 1.5s ease-in-out infinite',
        'float': 'float 3s ease-in-out infinite',
        'checkmark': 'checkmark 300ms ease',
      },
      keyframes: {
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        pulseRing: {
          '0%': { transform: 'scale(0.8)', opacity: '1' },
          '100%': { transform: 'scale(1.4)', opacity: '0' },
        },
        skeletonLoading: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        checkmark: {
          '0%': { transform: 'scale(0)' },
          '50%': { transform: 'scale(1.2)' },
          '100%': { transform: 'scale(1)' },
        },
      },
    },
  },
  plugins: [],
};
