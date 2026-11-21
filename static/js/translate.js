// translate.js — FINAL FIXED VERSION
// Simple: body gets class 'lang-ur' or 'lang-en'

let currentLang = localStorage.getItem('dgip_lang') || 'en';


function applyDataAttrs() {
  // Handle old data-en / data-ur attribute system (used in form.html labels)
  document.querySelectorAll('[data-en]').forEach(function(el) {
    if (currentLang === 'ur' && el.getAttribute('data-ur')) {
      el.textContent = el.getAttribute('data-ur');
    } else if (el.getAttribute('data-en')) {
      el.textContent = el.getAttribute('data-en');
    }
  });
}
function applyLang() {
  document.body.classList.remove('lang-en', 'lang-ur');
  document.body.classList.add('lang-' + currentLang);

  applyDataAttrs();
  document.querySelectorAll('.lang-toggle-btn').forEach(function(btn) {
    btn.textContent = currentLang === 'en' ? '🌐 اردو' : '🌐 English';
  });
}

function toggleLang() {
  currentLang = currentLang === 'en' ? 'ur' : 'en';
  localStorage.setItem('dgip_lang', currentLang);
  applyLang();
}

// Run immediately when script loads (not waiting for DOMContentLoaded)
// to avoid flash of wrong language
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', applyLang);
} else {
  applyLang();
}
