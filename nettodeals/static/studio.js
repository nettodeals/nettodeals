'use strict';
document.querySelectorAll('[data-copy]').forEach(button => {
  button.addEventListener('click', async () => {
    const field = document.getElementById(button.dataset.copy);
    try {
      await navigator.clipboard.writeText(field.value);
      document.getElementById('copy-status').textContent = 'Text kopiert.';
    } catch (_) {
      field.focus(); field.select();
      document.getElementById('copy-status').textContent = 'Text markiert. Bitte über das Gerätemenü kopieren.';
    }
  });
});
// Links remain useful section anchors without JavaScript.
const panels = [...document.querySelectorAll('[data-admin-panel]')];
if (panels.length) {
  function show() {
    const selected = location.hash.slice(1);
    const id = panels.some(p => p.id === selected) ? selected : 'import';
    panels.forEach(p => { p.hidden = p.id !== id; });
    document.querySelectorAll('.admin-tabs a').forEach(a => {
      if (a.hash === '#' + id) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
  }
  window.addEventListener('hashchange', show); show();
}
