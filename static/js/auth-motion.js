// auth-motion.js — motion for the sign in / register / password pages.
// The CSS in style.css does the animating; this file only orders it,
// keeps the image still when switching Sign In <-> Register, and shows
// a loading state on submit.
(function () {
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Stagger: each block of the form rises one after another.
  var box = document.querySelector('.auth-box');
  if (box) {
    var i = 0;
    Array.prototype.forEach.call(box.children, function (el) {
      if (el.tagName === 'FORM') {
        Array.prototype.forEach.call(el.children, function (f) { f.style.setProperty('--i', i++); });
      } else {
        el.style.setProperty('--i', i++);
      }
    });
  }

  // Switching between the auth pages: fade the form out, keep the image still on arrival.
  var right = document.querySelector('.auth-right');
  function go(url) {
    try { sessionStorage.setItem('authSwap', '1'); } catch (e) {}
    if (reduce || !right) { window.location.href = url; return; }
    right.classList.add('is-leaving');
    setTimeout(function () { window.location.href = url; }, 200);
  }
  document.querySelectorAll('.auth-tab[data-href]').forEach(function (b) {
    b.addEventListener('click', function () { go(b.getAttribute('data-href')); });
  });
  if (right) {
    right.querySelectorAll('a[href]').forEach(function (a) {
      var path = a.pathname || '';
      if (/\/(signin|signup)$/.test(path) && path !== window.location.pathname) {
        a.addEventListener('click', function (e) {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
          e.preventDefault(); go(a.href);
        });
      }
    });
  }

  // Submit: spinner on the visible button; the browser only fires this once the form is valid.
  document.querySelectorAll('.auth-box form').forEach(function (form) {
    form.addEventListener('submit', function () {
      form.querySelectorAll('.f-submit').forEach(function (b) { b.classList.add('is-loading'); });
    });
  });

  // Coming back with the browser's Back button: clear any leftover state.
  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    if (right) right.classList.remove('is-leaving');
    document.querySelectorAll('.f-submit.is-loading').forEach(function (b) { b.classList.remove('is-loading'); });
  });
})();
