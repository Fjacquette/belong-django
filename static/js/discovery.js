(function () {
  const form = document.getElementById('discovery-filters');
  if (!form) return;
  const feedback = document.getElementById('location-feedback');
  const distanceInputs = Array.from(form.querySelectorAll('[data-distance]'));
  let generation = 0;
  function submit(facet, value) {
    try { sessionStorage.setItem('belong-open-facet', JSON.stringify({facet, value})); } catch (_) {}
    form.requestSubmit();
  }
  // Facet/list-management changes retain the applied search, not unsubmitted typing.
  form.addEventListener('submit', event => {
    if (!event.submitter || !event.submitter.hasAttribute('data-text-search')) form.elements.q.value = form.dataset.query;
  });
  form.querySelectorAll('[data-facet] input').forEach(input => input.addEventListener('change', () => {
    const token = ++generation;
    const facet = input.closest('[data-facet]').dataset.facet;
    const hasDistance = distanceInputs.some(choice => choice.checked);
    form.elements.location_notice.value = '';
    if (!hasDistance) {
      form.elements.lat.value = '';
      form.elements.lon.value = '';
      submit(facet, input.value);
      return;
    }
    if (form.elements.lat.value && form.elements.lon.value) { submit(facet, input.value); return; }
    feedback.textContent = 'Getting your location…';
    const fail = () => {
      if (token !== generation) return;
      distanceInputs.forEach(choice => { choice.checked = false; });
      form.elements.lat.value = '';
      form.elements.lon.value = '';
      form.elements.location_notice.value = 'unavailable';
      submit(facet, input.value);
    };
    if (!navigator.geolocation) { fail(); return; }
    navigator.geolocation.getCurrentPosition(position => {
      if (token !== generation) return;
      form.elements.lat.value = position.coords.latitude;
      form.elements.lon.value = position.coords.longitude;
      submit(facet, input.value);
    }, fail, {timeout: 10000, maximumAge: 60000, enableHighAccuracy: false});
  }));
  form.querySelectorAll('[data-facet]').forEach(menu => menu.addEventListener('toggle', () => {
    if (menu.open) form.querySelectorAll('[data-facet]').forEach(peer => { if (peer !== menu) peer.open = false; });
  }));
  try {
    const state = JSON.parse(sessionStorage.getItem('belong-open-facet'));
    sessionStorage.removeItem('belong-open-facet');
    if (state) {
      const menu = Array.from(form.querySelectorAll('[data-facet]')).find(item => item.dataset.facet === state.facet);
      if (menu) {
        menu.open = true;
        const input = Array.from(menu.querySelectorAll('input')).find(item => item.value === state.value);
        (input || menu.querySelector('summary')).focus();
      }
    }
  } catch (_) {}
}());
