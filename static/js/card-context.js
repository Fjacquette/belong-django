(function () {
  function enableSharing() {
    document.querySelectorAll('[data-share-activity]').forEach(button => { button.hidden = false; });
  }

  async function shareActivity(button) {
    const menu = button.closest('.card-context-menu');
    const feedback = menu.querySelector('[data-share-feedback]');
    const link = menu.querySelector('[data-share-link]');
    const input = link.querySelector('input');
    const url = new URL(button.dataset.shareUrl, window.location.origin).href;
    button.disabled = true;
    feedback.textContent = '';
    link.hidden = true;
    try {
      if (typeof navigator.share === 'function') {
        try {
          await navigator.share({ title: button.dataset.shareTitle, url });
          feedback.textContent = 'Activity shared.';
          return;
        } catch (error) {
          // Cancelling the native sheet is deliberate; don't silently copy instead.
          if (error && error.name === 'AbortError') return;
        }
      }
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        try {
          await navigator.clipboard.writeText(url);
          feedback.textContent = 'Activity link copied.';
          return;
        } catch (_) { /* Try selection-based copying if clipboard access is denied. */ }
      }
      input.value = url;
      link.hidden = false;
      input.focus();
      input.select();
      let copied = false;
      try { copied = document.execCommand('copy'); } catch (_) { /* Manual copy remains available. */ }
      if (copied) {
        link.hidden = true;
        feedback.textContent = 'Activity link copied.';
      } else {
        feedback.textContent = 'Copy this activity link to share.';
      }
    } finally {
      button.disabled = false;
      if (link.hidden && document.activeElement === input) button.focus();
    }
  }

  enableSharing();
  document.addEventListener('htmx:afterSwap', enableSharing);
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-share-activity]');
    if (button && !button.disabled) shareActivity(button);
  });

  // Native disclosures work without JS; keep the optional dismissal behavior delegated
  // so freshly replaced HTMX cards receive it too.
  document.addEventListener('click', event => {
    document.querySelectorAll('.card-context-menu[open]').forEach(menu => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const menu = event.target.closest('.card-context-menu[open]');
    if (menu) {
      menu.open = false;
      menu.querySelector('summary').focus();
    }
  });
}());
