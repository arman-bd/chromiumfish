/* Shared front-end helpers for ByteTunnels.
   Kept tiny and framework-free so the pages stay predictable for automation. */
(function () {
  const root = document.documentElement;

  /* ---- Theme toggle (persisted) ---------------------------------------- */
  const saved = localStorage.getItem('al-theme');
  if (saved) root.setAttribute('data-theme', saved);
  function syncToggle() {
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = root.getAttribute('data-theme') === 'light' ? '🌙' : '☀️';
  }
  syncToggle();
  document.addEventListener('click', (e) => {
    if (e.target.closest('#theme-toggle')) {
      const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      localStorage.setItem('al-theme', next);
      syncToggle();
    }
  });

  /* ---- Toast helper ----------------------------------------------------- */
  function toast(message, variant) {
    const wrap = document.getElementById('toast-wrap');
    if (!wrap) return;
    const el = document.createElement('div');
    el.className = 'toast' + (variant ? ' ' + variant : '');
    el.setAttribute('role', 'status');
    el.textContent = message;
    wrap.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, 2600);
    setTimeout(() => el.remove(), 3000);
  }

  /* Auto-dismiss any server-flashed toasts */
  document.querySelectorAll('#toast-wrap .toast').forEach((el) => {
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, 2600);
    setTimeout(() => el.remove(), 3000);
  });

  /* Expose a tiny namespace for inline page scripts */
  window.AL = { toast };
})();
