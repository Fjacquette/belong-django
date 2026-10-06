(function () {
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
