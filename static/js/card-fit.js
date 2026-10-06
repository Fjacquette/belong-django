/* Bounded typography; fixed card geometry and no persistent measuring elements. */
(function () {
  const observed = new WeakSet();
  const steps = ['normal', 'compact', 'minimum'];
  function fit(header) {
    const title = header.querySelector('.activity-card__headline');
    const logistics = header.querySelector('.activity-card__logistics');
    if (!title || !logistics || !header.clientWidth) return;
    const probe = title.cloneNode(true);
    probe.removeAttribute('data-fit');
    Object.assign(probe.style, {position: 'absolute', visibility: 'hidden', pointerEvents: 'none',
      width: `${title.clientWidth}px`, display: 'block', overflow: 'visible', maxHeight: 'none',
      webkitLineClamp: 'unset', left: '-10000px'});
    header.append(probe);
    for (const step of steps) {
      probe.dataset.fit = step;
      title.dataset.fit = step;
      if (probe.getBoundingClientRect().height <= parseFloat(getComputedStyle(probe).lineHeight) * 2 + 0.5) break;
    }
    probe.remove();
    const when = logistics.querySelector('.activity-card__when');
    const where = logistics.querySelector('.activity-card__where');
    const canvas = document.createElement('canvas');
    const measure = canvas.getContext('2d');
    function width(text) {
      const style = getComputedStyle(logistics);
      measure.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      return measure.measureText(text).width;
    }
    logistics.dataset.fit = 'normal';
    logistics.dataset.layout = width(`${when.textContent} · ${where.textContent}`) <= logistics.clientWidth ? 'inline' : 'split';
    if (logistics.dataset.layout === 'split') {
      for (const step of ['normal', 'minimum']) {
        logistics.dataset.fit = step;
        if (Math.max(width(when.textContent), width(where.textContent)) <= logistics.clientWidth) break;
      }
    }
  }
  const observer = new ResizeObserver(entries => entries.forEach(entry => fit(entry.target)));
  function refresh() {
    document.querySelectorAll('.activity-card__band-1').forEach(header => {
      fit(header);
      if (!observed.has(header)) { observed.add(header); observer.observe(header); }
    });
  }
  document.addEventListener('htmx:beforeSwap', event => {
    event.detail.target.querySelectorAll('.activity-card__band-1').forEach(header => observer.unobserve(header));
  });
  document.addEventListener('htmx:afterSwap', refresh);
  document.fonts.ready.then(refresh);
  refresh();
}());
