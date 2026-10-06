(function () {
  const root = document.querySelector('[data-stack-root]');
  const selector = document.getElementById('card-view-selector');
  if (!selector) return;
  const modes = Array.from(selector.querySelectorAll('input[name="card-view"]'));
  const items = root ? Array.from(root.querySelectorAll('[data-stack-item]')) : [];
  const minWidth = Number(root?.dataset.cardMinWidth);
  const gap = Number(root?.dataset.stackGap);
  const maxColumns = Math.min(Number(root?.dataset.maxColumns), items.length);
  let showAll = false;
  try { showAll = localStorage.getItem('belong-card-view') === 'all'; } catch (_) {}
  items.forEach(item => item.classList.add('activity-stack__layer'));
  const columns = () => Math.max(1, Math.min(maxColumns, Math.floor((root.clientWidth + gap) / (minWidth + gap))));
  function applyLayout() {
    modes.forEach(input => { input.checked = input.value === (showAll ? 'all' : 'stacked'); });
    if (!root || !root.clientWidth) return;
    const count = columns();
    root.dataset.stackColumns = count;
    root.dataset.view = showAll ? 'all' : 'stacked';
    root.style.gridTemplateColumns = `repeat(${count}, minmax(0, ${Math.min(minWidth, root.clientWidth)}px))`;
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
    modes.forEach(input => { input.checked = input.value === root.dataset.view; });
  }
  selector.hidden = false;
  modes.forEach(input => input.addEventListener('change', () => {
    if (!input.checked) return;
    showAll = input.value === 'all';
    try { localStorage.setItem('belong-card-view', showAll ? 'all' : 'stacked'); } catch (_) {}
    applyLayout();
  }));
  window.addEventListener('belong:discovery-layout', applyLayout);
  applyLayout();
}());
