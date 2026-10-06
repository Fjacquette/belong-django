// One Friends list, independent wide panes, and mutually exclusive narrow views.
(() => {
  const layout = document.querySelector('[data-layout-container]');
  const panes = document.querySelector('[data-discover-panes]');
  if (!layout || !panes) return;
  const friends = document.querySelector('[data-friends-column]');
  const activities = document.querySelector('[data-activity-frame]');
  const divider = document.querySelector('[data-pane-divider]');
  const switcher = document.querySelector('[data-pane-switch]');
  const choices = [...switcher.querySelectorAll('input')];
  const wide = matchMedia('(min-width: 1024px)');
  const minWidth = 200;
  // Two card columns, their gap, and the Activities pane inset.
  const activityMinWidth = 2 * Number(activities.dataset.cardMinWidth) + 24 + 8;
  let wantedWidth = 240;
  let pane = 'activities';
  let drag;
  const scroll = {friends: 0, activities: 0};
  try {
    const saved = Number(localStorage.getItem('belong-friends-width'));
    if (Number.isFinite(saved) && saved >= minWidth) wantedWidth = saved;
  } catch (_) {}
  document.body.classList.add('discover-page');
  const notify = () => window.dispatchEvent(new Event('belong:discovery-layout'));
  const maxWidth = () => Math.max(minWidth, Math.min(420, panes.clientWidth - 24 - activityMinWidth));
  const width = () => Math.round(Math.max(minWidth, Math.min(maxWidth(), wantedWidth)));
  const setWidth = value => {
    wantedWidth = Math.max(minWidth, Math.min(maxWidth(), value));
    panes.style.setProperty('--friends-width', `${width()}px`);
    divider.setAttribute('aria-valuemin', minWidth);
    divider.setAttribute('aria-valuemax', Math.floor(maxWidth()));
    divider.setAttribute('aria-valuenow', width());
    divider.setAttribute('aria-valuetext', `${width()} pixels`);
  };
  const persist = () => {
    try { localStorage.setItem('belong-friends-width', width()); } catch (_) {}
  };
  const rememberScroll = () => {
    if (!friends.hidden) scroll.friends = friends.scrollTop;
    if (!activities.hidden) scroll.activities = activities.scrollTop;
  };
  const apply = () => {
    rememberScroll();
    friends.hidden = !wide.matches && pane !== 'friends';
    activities.hidden = !wide.matches && pane !== 'activities';
    divider.hidden = !wide.matches;
    switcher.hidden = wide.matches;
    choices.forEach(choice => { choice.checked = choice.value === pane; });
    // Clamp rendering to the available workspace, retaining the preferred width.
    const preferred = wantedWidth;
    if (wide.matches) { setWidth(preferred); wantedWidth = preferred; }
    if (!activities.hidden) notify();
    requestAnimationFrame(() => {
      if (!friends.hidden) friends.scrollTop = scroll.friends;
      if (!activities.hidden) activities.scrollTop = scroll.activities;
    });
  };
  choices.forEach(choice => choice.addEventListener('change', () => {
    if (choice.checked) { pane = choice.value; apply(); }
  }));
  divider.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    event.preventDefault();
    divider.focus();
    drag = {x: event.clientX, width: width()};
    divider.setPointerCapture(event.pointerId);
  });
  divider.addEventListener('pointermove', event => {
    if (!drag) return;
    rememberScroll();
    setWidth(drag.width + event.clientX - drag.x);
    notify();
    activities.scrollTop = scroll.activities;
  });
  const endDrag = () => { if (drag) { drag = null; persist(); } };
  divider.addEventListener('pointerup', endDrag);
  divider.addEventListener('pointercancel', endDrag);
  divider.addEventListener('lostpointercapture', endDrag);
  divider.addEventListener('keydown', event => {
    const commands = {ArrowLeft: width() - 16, ArrowRight: width() + 16, Home: minWidth, End: maxWidth()};
    if (!(event.key in commands)) return;
    event.preventDefault();
    rememberScroll();
    setWidth(commands[event.key]);
    persist();
    notify();
    activities.scrollTop = scroll.activities;
  });
  new ResizeObserver(apply).observe(panes);
  wide.addEventListener('change', apply);
  apply();
})();
