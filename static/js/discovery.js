(function () {
  const form = document.getElementById('discovery-filters');
  if (!form) return;
  const nearby = form.elements.nearby;
  const feedback = document.getElementById('location-feedback');
  const shortcuts = {today: ['timing', 'today'], online: ['location', 'online_capable'], free: ['cost', 'free']};
  const quickInputs = form.querySelectorAll('[data-quick-filter]');
  const syncQuick = () => quickInputs.forEach(input => {
    const mapping = shortcuts[input.dataset.quickFilter];
    if (mapping) input.checked = form.elements[mapping[0]].value === mapping[1];
  });
  Object.values(shortcuts).forEach(([dimension]) => form.elements[dimension].addEventListener('change', syncQuick));
  // Quick/advanced filter submissions retain the applied text query, not a draft.
  form.addEventListener('submit', event => {
    if (!event.submitter || !event.submitter.hasAttribute('data-text-search')) form.elements.q.value = form.dataset.query;
  });
  const fail = (message) => {
    nearby.checked = false;
    nearby.disabled = false;
    form.elements.lat.value = '';
    form.elements.lon.value = '';
    feedback.textContent = message;
  };
  quickInputs.forEach(input => input.addEventListener('change', () => {
    const mapping = shortcuts[input.dataset.quickFilter];
    if (mapping) {
      form.elements[mapping[0]].value = input.checked ? mapping[1] : '';
      form.requestSubmit();
      return;
    }
    if (!nearby.checked) {
      form.elements.lat.value = '';
      form.elements.lon.value = '';
      form.requestSubmit();
      return;
    }
    if (!navigator.geolocation) { fail('Nearby is off. This browser cannot provide location.'); return; }
    nearby.disabled = true;
    feedback.textContent = 'Getting your location…';
    navigator.geolocation.getCurrentPosition(position => {
      nearby.disabled = false;
      form.elements.lat.value = position.coords.latitude;
      form.elements.lon.value = position.coords.longitude;
      form.requestSubmit();
    }, () => fail('Nearby is off. Location access was denied or unavailable.'),
    {timeout: 10000, maximumAge: 60000, enableHighAccuracy: false});
  }));
  syncQuick();
}());
