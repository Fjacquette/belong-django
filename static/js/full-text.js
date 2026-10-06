// Full values only for genuinely clipped card text, including HTMX updates.
(() => {
  const selector = '.activity-card [data-full-text]';
  const tooltip = document.createElement('div');
  tooltip.id = 'card-full-text';
  tooltip.className = 'ui-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  tooltip.hidden = true;
  document.body.append(tooltip);
  let owner;
  let previousDescription;
  const close = () => {
    if (owner) {
      if (previousDescription) owner.setAttribute('aria-describedby', previousDescription);
      else owner.removeAttribute('aria-describedby');
    }
    owner = null;
    tooltip.hidden = true;
  };
  const boxFor = element => element.matches('.activity-card__title-link')
    ? element.closest('.activity-card__headline') : element;
  const update = element => {
    const box = boxFor(element);
    const clipped = box.clientWidth > 0 && box.clientHeight > 0 &&
      (box.scrollWidth > box.clientWidth + 1 || box.scrollHeight > box.clientHeight + 1);
    element.toggleAttribute('data-truncated', clipped);
    if (!element.matches('a[href], button, input, select, textarea, summary')) {
      if (clipped) element.setAttribute('tabindex', '0');
      else element.removeAttribute('tabindex');
    }
    if (!clipped && owner === element) close();
    return clipped;
  };
  const show = target => {
    const element = target.closest(selector);
    if (!element || !update(element)) return;
    if (owner === element) return;
    close();
    owner = element;
    previousDescription = element.getAttribute('aria-describedby');
    tooltip.textContent = element.dataset.fullText;
    element.setAttribute('aria-describedby', [previousDescription, tooltip.id].filter(Boolean).join(' '));
    tooltip.hidden = false;
    const rect = boxFor(element).getBoundingClientRect();
    tooltip.style.left = `${Math.max(16, Math.min(rect.left, innerWidth - tooltip.offsetWidth - 16))}px`;
    tooltip.style.top = `${Math.max(16, Math.min(rect.bottom + 8, innerHeight - tooltip.offsetHeight - 16))}px`;
  };
  let pending;
  const observed = new Set();
  const refresh = () => {
    pending = null;
    for (const box of observed) {
      if (!box.isConnected) { observer.unobserve(box); observed.delete(box); }
    }
    document.querySelectorAll(selector).forEach(element => {
      update(element);
      const box = boxFor(element);
      if (!observed.has(box)) { observed.add(box); observer.observe(box); }
    });
  };
  const schedule = () => {
    if (!pending) pending = requestAnimationFrame(refresh);
  };
  const observer = new ResizeObserver(schedule);
  document.addEventListener('focusin', event => show(event.target));
  document.addEventListener('focusout', close);
  document.addEventListener('pointerover', event => show(event.target));
  document.addEventListener('pointerout', event => {
    if (owner && !owner.contains(event.relatedTarget)) close();
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
  window.addEventListener('scroll', close, true);
  window.addEventListener('resize', () => { close(); schedule(); });
  document.addEventListener('belong:discovery-layout', schedule);
  document.addEventListener('htmx:beforeSwap', close);
  document.addEventListener('htmx:afterSwap', schedule);
  document.fonts.ready.then(schedule);
  document.fonts.addEventListener('loadingdone', schedule);
  schedule();
})();
