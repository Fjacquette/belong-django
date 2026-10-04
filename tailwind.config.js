/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    './activities/forms.py',
    './belong/forms.py',
    './media_assets/forms.py',
  ],
  theme: {
    extend: {
      colors: {
        belong: {
          purple: '#843A96',
          purple10: '#773487',
          purple20: '#6A2E78',
          purple40: '#5C2969',
          purple60: '#4F235A',
          purple80: '#421D4B',
          purpleDark: '#35173C',
          lilac: '#C29DCB',
          lilacSoft: '#DAC4E0',
          lilacLight: '#E6D8EA',
          lilacLighter: '#F3EBF5',
          teal: '#00C9BC',
          tealDark: '#00AAA0',
          aqua: '#C1FCF6',
          slate: '#6F7A94',
          background: '#F3F5FF',
        },
      },
      fontFamily: {
        display: ['Rockwell', 'Rockwell Nova', 'Rockwell Std', 'Georgia', 'serif'],
        body: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        base16: ['1rem', '1.35rem'],
        sm10: ['0.625rem', '1rem'],
        xs9: ['0.5625rem', '0.9rem'],
      },
      boxShadow: {
        soft: '0 10px 28px rgba(132, 58, 150, 0.18)',
      },
    },
  },
  plugins: [],
};
