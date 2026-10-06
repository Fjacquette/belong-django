/* Keep direct response labels whole. Without JS, the first choice remains direct. */
(function () {
  const observed = new WeakSet();
  function fit(form) {
    const buttons = Array.from(form.querySelectorAll('button'));
    if (buttons.length < 2) return;
    const optional = buttons[1];
    optional.hidden = false;
    buttons.forEach(button => { button.style.flex = '0 0 auto'; });
    // Reserve a check only for an offered committed response, so selecting it
    // does not make previously fitting labels overflow. Softer intent has no check.
    const width = buttons.reduce((sum, button) => sum + button.getBoundingClientRect().width, 8);
    const needsCheck = buttons.some(button => button.value === 'committed');
    const hasCheck = buttons.some(button => button.classList.contains('ui-response--confirmed'));
    const check = needsCheck && !hasCheck ? 16 : 0;
    optional.hidden = width + check > form.clientWidth;
    buttons.forEach(button => { button.style.flex = ''; });
  }
  const observer = new ResizeObserver(entries => entries.forEach(entry => fit(entry.target)));
  function refresh() {
    document.querySelectorAll('.card-response').forEach(form => {
      fit(form);
      if (!observed.has(form)) { observed.add(form); observer.observe(form); }
    });
  }
  document.addEventListener('htmx:beforeSwap', event => {
    event.detail.target.querySelectorAll('.card-response').forEach(form => observer.unobserve(form));
  });
  document.addEventListener('htmx:afterSwap', refresh);
  refresh();
  document.fonts.ready.then(refresh);
}());
