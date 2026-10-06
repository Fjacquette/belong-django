/* Bounded typography; fixed card geometry and no persistent measuring elements. */
(function () {
  const observed = new WeakSet();
  const steps = ['normal', 'compact', 'minimum'];
  function fit(card) {
    const header = card.querySelector(".activity-card__band-1");
    if (!header) return;
    const title = header.querySelector('.activity-card__headline');
    const logistics = card.querySelector('.activity-card__logistics');
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
    logistics.dataset.layout = width(`${when.textContent} · ${where.textContent}`) <= logistics.clientWidth ? 'inline' : 'split';
  }
  const observer = new ResizeObserver(entries => entries.forEach(entry => fit(entry.target)));
  function refresh() {
    document.querySelectorAll('.activity-card').forEach(card => {
      fit(card);
      if (!observed.has(card)) { observed.add(card); observer.observe(card); }
    });
  }
  document.addEventListener('htmx:beforeSwap', event => {
    const target = event.detail.target;
    if (target.matches('.activity-card')) observer.unobserve(target);
    target.querySelectorAll('.activity-card').forEach(card => observer.unobserve(card));
  });
  document.addEventListener('htmx:afterSwap', refresh);
  document.fonts.ready.then(refresh);
  refresh();
}());
