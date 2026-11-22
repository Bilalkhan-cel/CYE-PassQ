// translate.js — one language at a time.
// body gets 'lang-en' or 'lang-ur'; <html> gets lang + dir so Urdu pages are right-to-left.
// Pages can listen for the 'langchange' event, and call passqLang() to know the current one.

let currentLang = localStorage.getItem('dgip_lang') || 'en';

function passqLang() { return currentLang; }

// Old data-en / data-ur attributes (form.html, chat). Only the element's own text
// changes, so children such as the required "*" mark and icons stay in place.
function setOwnText(el, text) {
  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') { el.placeholder = text; return; }
  if (!el.children.length) { el.textContent = text; return; }
  var node = null;
  for (var i = 0; i < el.childNodes.length; i++) {
    var n = el.childNodes[i];
    if (n.nodeType === 3 && n.nodeValue.trim()) { node = n; break; }
  }
  if (node) node.nodeValue = text + ' ';
  else el.insertBefore(document.createTextNode(text + ' '), el.firstChild);
}

function applyDataAttrs() {
  document.querySelectorAll('[data-en]').forEach(function (el) {
    var t = (currentLang === 'ur' && el.getAttribute('data-ur')) ? el.getAttribute('data-ur') : el.getAttribute('data-en');
    if (t) setOwnText(el, t);
  });
}

function applyLang() {
  var ur = currentLang === 'ur';
  document.body.classList.remove('lang-en', 'lang-ur');
  document.body.classList.add('lang-' + currentLang);
  document.documentElement.lang = ur ? 'ur' : 'en';
  document.documentElement.dir = ur ? 'rtl' : 'ltr';
  applyDataAttrs();
  document.querySelectorAll('.lang-toggle-btn, .lang-switch').forEach(function (btn) {
    btn.textContent = ur ? 'English' : 'اردو';
    btn.classList.toggle('to-ur', !ur);
  });
  document.dispatchEvent(new CustomEvent('langchange', { detail: { lang: currentLang } }));
}

function toggleLang() {
  currentLang = currentLang === 'en' ? 'ur' : 'en';
  localStorage.setItem('dgip_lang', currentLang);
  applyLang();
}

// Run straight away (or as soon as the body exists) to avoid a flash of the wrong language.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', applyLang);
} else {
  applyLang();
}
