(function () {
  // Page layout depends on available space, never the number of matching cards.
  const frame = document.querySelector('[data-activity-frame]');
  const layout = document.querySelector('[data-layout-container]');
  if (!frame || !layout) return;
  const sidebar = document.querySelector('[data-friends-column]');
  const secondary = document.querySelector('[data-friends-secondary]');
  const twoCardWidth = 2 * Number(frame.dataset.cardMinWidth) + 24;
  function applyLayout() {
    if (sidebar) {
      sidebar.hidden = window.innerWidth < 1024;
      layout.dataset.layout = sidebar.hidden ? 'no-sidebar' : 'with-sidebar';
      if (!sidebar.hidden && frame.clientWidth < twoCardWidth) {
        sidebar.hidden = true;
        layout.dataset.layout = 'no-sidebar';
      }
      if (secondary) secondary.hidden = !sidebar.hidden;
    }
    window.dispatchEvent(new Event('belong:discovery-layout'));
  }
  window.addEventListener('resize', applyLayout);
  applyLayout();
}());
