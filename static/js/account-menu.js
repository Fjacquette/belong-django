(function () {
  // Native summary and menu links/buttons retain their operation without JavaScript.
  document.addEventListener('click', event => {
    document.querySelectorAll('.account-menu[open]').forEach(menu => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const menu = event.target.closest('.account-menu[open]');
    if (menu) {
      menu.open = false;
      menu.querySelector('summary').focus();
    }
  });
}());
