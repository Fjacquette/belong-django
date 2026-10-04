// Full card values on keyboard focus and pointer hover, including HTMX updates.
(() => {
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
  const show = (target) => {
    const element = target.closest('.activity-card [title]');
    if (!element || owner === element) return;
    close();
    owner = element;
    previousDescription = element.getAttribute('aria-describedby');
    tooltip.textContent = element.title;
    element.setAttribute('aria-describedby', [previousDescription, tooltip.id].filter(Boolean).join(' '));
    tooltip.hidden = false;
    const rect = element.getBoundingClientRect();
    tooltip.style.left = `${Math.max(16, Math.min(rect.left, innerWidth - tooltip.offsetWidth - 16))}px`;
    tooltip.style.top = `${Math.max(16, Math.min(rect.bottom + 8, innerHeight - tooltip.offsetHeight - 16))}px`;
  };
  document.addEventListener('focusin', (event) => show(event.target));
  document.addEventListener('focusout', close);
  document.addEventListener('pointerover', (event) => show(event.target));
  document.addEventListener('pointerout', (event) => { if (owner && !owner.contains(event.relatedTarget)) close(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
  window.addEventListener('scroll', close, true);
  window.addEventListener('resize', close);
  document.addEventListener('htmx:beforeSwap', close);
})();
