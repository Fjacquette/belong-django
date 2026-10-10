/* Production Discover: three presentation modes; retrieval batches are server-side. */
(() => {
  const root = document.querySelector('[data-stack-root]');
  const selector = document.getElementById('card-view-selector');
  const densitySelector = document.getElementById('card-density-selector');
  const controls = document.querySelector('[data-paged-controls]');
  const pane = document.querySelector('[data-activity-frame]');
  const serverPager = document.querySelector('[data-server-pagination]');
  if (!root || !selector || !densitySelector || !controls || !pane) return;

  const items = [...root.querySelectorAll('[data-stack-item]')];
  const modes = [...selector.querySelectorAll('input[name="card-view"]')];
  const densities = [...densitySelector.querySelectorAll('input[name="card-density"]')];
  const previous = controls.querySelector('[data-set-previous]');
  const next = controls.querySelector('[data-set-next]');
  const range = controls.querySelector('[data-set-range]');
  const mobile = matchMedia('(max-width:639px)');
  const minWidth = Number(root.dataset.cardMinWidth);
  const gap = Number(root.dataset.stackGap);
  const maxColumns = Number(root.dataset.maxColumns);
  const batchStart = Number(controls.dataset.batchStart || 1);
  const total = Number(controls.dataset.total || items.length);
  const read = key => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const save = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  const stored = read('belong-card-view');
  const validModes = ['paged', 'stacked', 'all'];
  let explicitMode = validModes.includes(stored);
  let mode = explicitMode ? stored : mobile.matches ? 'all' : 'paged';
  let density = read('belong-card-density') === 'tight' ? 'tight' : 'regular';
  let first = 0, capacity = 1, renderedMode = '';
  const openLastSet = window.location.hash === '#discover-last-set';
  // Keep range-width changes from repeatedly wrapping/unwrapping the toolbar.
  range.style.minWidth = (String(total).length * 3 + 5) + 'ch';

  const token = name => parseFloat(getComputedStyle(root).getPropertyValue(name));
  const cardHeight = () => token('--card-height');
  const overlap = () => token('--band-1') + (density === 'regular' ? token('--band-2') : 0);
  const columns = () => Math.max(1, Math.min(maxColumns,
      Math.floor((root.clientWidth + gap) / (minWidth + gap))));
  const serverUrl = direction => controls.dataset[direction === 'next' ? 'batchNext' : 'batchPrevious'];

  function makeStacks(cards, count) {
    const buckets = Array.from({length: count}, () => []);
    cards.forEach((item, index) => buckets[index % count].push(item));
    buckets.forEach(bucket => {
      const stack = document.createElement('div');
      stack.className = 'activity-stack';
      stack.style.setProperty('--stack-depth', bucket.length - 1);
      bucket.forEach((item, index) => {
        item.classList.add('activity-stack__layer');
        item.style.setProperty('--stack-index', index);
        item.style.setProperty('--stack-z', index + 1);
        stack.append(item);
      });
      root.append(stack);
    });
  }

  function paint() {
    if (!root.clientWidth) return;
    const previousScroll = pane.scrollTop;
    const focused = root.contains(document.activeElement) ? document.activeElement : null;
    // Measure with the requested controls present, including their wrapped rows.
    // The full-grid fallback may hide them only after deciding whether Paged fits.
    controls.hidden = mode !== 'paged';
    densitySelector.hidden = mode === 'all';
    const count = columns();
    const offset = overlap();
    const available = Math.max(0,
      pane.getBoundingClientRect().bottom - (root.getBoundingClientRect().top + previousScroll) - 72);
    // When a full card cannot fit, use the accessible full-card grid instead.
    const canPage = mode === 'paged' && available >= cardHeight();
    if (canPage && renderedMode !== 'paged' && previousScroll > 0) {
      const top = pane.getBoundingClientRect().top;
      const anchor = items.findIndex(item => item.getBoundingClientRect().bottom > top);
      if (anchor >= 0) first = anchor;
    }
    renderedMode = canPage ? 'paged' : mode === 'paged' ? 'all' : mode;
    capacity = canPage ? count * (1 + Math.floor((available - cardHeight()) / offset)) : items.length;
    first = canPage ? Math.floor(Math.min(first, items.length - 1) / capacity) * capacity : first;
    root.style.setProperty('--stack-offset', offset + 'px');
    root.dataset.view = renderedMode;
    root.dataset.stackColumns = count;
    root.style.gridTemplateColumns = 'repeat(' + count + ', minmax(0, ' +
      Math.min(minWidth, root.clientWidth) + 'px))';
    root.replaceChildren();
    items.forEach(item => { item.classList.add('activity-stack__layer'); });
    if (renderedMode === 'all') root.append(...items);
    else if (renderedMode === 'stacked') makeStacks(items, count);
    else makeStacks(items.slice(first, first + capacity), count);

    controls.hidden = !canPage;
    if (serverPager) serverPager.hidden = canPage;
    densitySelector.hidden = mode === 'all' || renderedMode === 'all';
    modes.forEach(input => { input.checked = input.value === mode; });
    densities.forEach(input => { input.checked = input.value === density; });
    if (canPage) {
      const end = Math.min(first + capacity, items.length);
      range.textContent = (batchStart + first) + '–' + (batchStart + end - 1) + ' of ' + total;
      const hasPrevious = first > 0 || !!serverUrl('previous');
      const hasNext = end < items.length || !!serverUrl('next');
      previous.disabled = !hasPrevious;
      next.disabled = !hasNext;
      previous.title = first ? 'Previous set' : 'Previous results';
      next.title = end < items.length ? 'Next set' : 'Next results';
      previous.setAttribute('aria-label', previous.title);
      next.setAttribute('aria-label', next.title);
    }
    // Paging must start below its toolbar; a scrolled grid is not extra capacity.
    pane.scrollTop = canPage ? 0 : previousScroll;
    if (focused && root.contains(focused)) focused.focus({preventScroll: true});
  }

  function move(direction) {
    const desired = first + direction * capacity;
    if (desired >= 0 && desired < items.length) {
      first = desired;
      paint();
    } else {
      const url = serverUrl(direction < 0 ? 'previous' : 'next');
      if (url) {
        // Returning from the next server batch starts at the final visible set.
        if (direction < 0) window.location.assign(url + '#discover-last-set');
        else window.location.assign(url);
      }
    }
  }

  previous.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  modes.forEach(input => input.addEventListener('change', () => {
    if (!input.checked) return;
    if (input.value === 'paged' && renderedMode !== 'paged') {
      const top = Math.max(pane.getBoundingClientRect().top, root.getBoundingClientRect().top);
      const anchor = items.findIndex(item => item.getBoundingClientRect().bottom > top);
      if (anchor >= 0) first = anchor;
    }
    mode = input.value;
    explicitMode = true;
    save('belong-card-view', mode);
    paint();
  }));
  densities.forEach(input => input.addEventListener('change', () => {
    if (!input.checked) return;
    density = input.value;
    save('belong-card-density', density);
    paint();
  }));
  selector.hidden = false;
  window.addEventListener('belong:discovery-layout', paint);
  new ResizeObserver(paint).observe(document.getElementById('discovery-filters'));
  document.addEventListener('htmx:afterSettle', event => {
    if (pane.contains(event.target)) paint();
  });
  mobile.addEventListener('change', () => {
    // Device width is a default only; never erase an explicitly chosen mode.
    if (!explicitMode) mode = mobile.matches ? 'all' : 'paged';
    paint();
  });
  if (openLastSet) {
    // The return link retains existing query/filters and restores the final set.
    first = items.length - 1;
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }
  paint();
})();
