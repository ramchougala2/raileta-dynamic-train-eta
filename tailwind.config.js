export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: { 950:'#0a0f1c', 900:'#0d1426', 850:'#111a30', 800:'#162038', 700:'#1e2a4a', 600:'#2a3a5e', 500:'#3a4d75' },
        accent: { 50:'#eff6ff',100:'#dbeafe',200:'#bfdbfe',300:'#93c5fd',400:'#60a5fa',500:'#3b82f6',600:'#2563eb',700:'#1d4ed8',800:'#1e40af',900:'#1e3a8a' },
        success: {400:'#4ade80',500:'#22c55e',600:'#16a34a'},
        warning: {400:'#fbbf24',500:'#f59e0b',600:'#d97706'},
        danger: {400:'#f87171',500:'#ef4444',600:'#dc2626'}
      },
      fontFamily: { sans:['Inter','system-ui','sans-serif'], mono:['JetBrains Mono','monospace'] },
      animation: { 'fade-in':'fadeIn .3s ease-out','slide-up':'slideUp .4s ease-out' },
      keyframes: { fadeIn:{'0%':{opacity:0},'100%':{opacity:1}}, slideUp:{'0%':{opacity:0,transform:'translateY(12px)'},'100%':{opacity:1,transform:'translateY(0)'}} }
    }
  },
  plugins: []
};
