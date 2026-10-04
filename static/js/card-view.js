(function () {
  const root = document.querySelector('[data-stack-root]');
  const toggle = document.getElementById('card-view-toggle');
  if (!root || !toggle) return;
  const items = Array.from(root.querySelectorAll('[data-stack-item]'));
  const layout = document.querySelector('[data-layout-container]');
  const sidebar = document.querySelector('[data-friends-column]');
  const secondary = document.querySelector('[data-friends-secondary]');
  const minWidth = Number(root.dataset.cardMinWidth);
  const gap = Number(root.dataset.stackGap);
  const maxColumns = Math.min(Number(root.dataset.maxColumns), items.length);
  let showAll = false;
  try { showAll = localStorage.getItem('belong-card-view') === 'all'; } catch (_) {}
  items.forEach(item => item.classList.add('activity-stack__layer'));
  const columns = () => Math.max(1, Math.min(maxColumns, Math.floor((root.clientWidth + gap) / (minWidth + gap))));
  function applyLayout() {
    if (sidebar) {
      sidebar.hidden = window.innerWidth < 1024;
      layout.dataset.layout = sidebar.hidden ? 'no-sidebar' : 'with-sidebar';
      if (!sidebar.hidden && columns() < 2) {
        sidebar.hidden = true;
        layout.dataset.layout = 'no-sidebar';
      }
      if (secondary) secondary.hidden = !sidebar.hidden;
    }
    const count = columns();
    root.dataset.stackColumns = count;
    root.dataset.view = showAll ? 'all' : 'stacked';
    root.style.gridTemplateColumns = `repeat(${count}, minmax(0, 1fr))`;
    root.replaceChildren();
    if (showAll) {
      root.append(...items);
    } else {
      const buckets = Array.from({length: count}, () => []);
      items.forEach((item, index) => buckets[index % count].push(item));
      buckets.forEach(bucket => {
        const stack = document.createElement('div');
        stack.className = 'activity-stack';
        stack.dataset.stackColumn = '';
        stack.style.setProperty('--stack-depth', bucket.length - 1);
        bucket.forEach((item, index) => {
          item.style.setProperty('--stack-index', index);
          item.style.setProperty('--stack-z', index + 1);
          stack.append(item);
        });
        root.append(stack);
      });
    }
    toggle.textContent = showAll ? 'Stack cards' : 'Show all';
    toggle.setAttribute('aria-pressed', String(showAll));
  }
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    showAll = !showAll;
    try { localStorage.setItem('belong-card-view', showAll ? 'all' : 'stacked'); } catch (_) {}
    applyLayout();
  });
  window.addEventListener('resize', applyLayout);
  applyLayout();
}());
