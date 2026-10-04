(function () {
  const form = document.getElementById('discovery-filters');
  if (!form) return;
  const nearby = form.elements.nearby;
  const feedback = document.getElementById('location-feedback');
  const fail = (message) => {
    nearby.checked = false;
    nearby.disabled = false;
    form.elements.lat.value = '';
    form.elements.lon.value = '';
    feedback.textContent = message;
  };
  form.querySelectorAll('[data-quick-filter]').forEach(input => {
    input.addEventListener('change', () => {
      if (input !== nearby || !nearby.checked) {
        if (input === nearby) { form.elements.lat.value = ''; form.elements.lon.value = ''; }
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
    });
  });
}());
