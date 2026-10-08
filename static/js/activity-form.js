(function () {
  const participation = document.getElementById('id_participation_pattern');
  if (participation) {
    function updateParticipation() {
      document.querySelectorAll('[data-registration-policy]').forEach(section => { section.hidden = participation.value !== 'registration'; });
      document.querySelectorAll('[data-poll-date]').forEach(section => { section.hidden = participation.value !== 'planning'; });
      document.querySelectorAll('[data-legacy-response-choices]').forEach(section => {
        section.hidden = Boolean(participation.value);
      });
    }
    participation.addEventListener('change', updateParticipation);
    updateParticipation();
  }

  const group = document.getElementById('id_group');
  const defaults = document.getElementById('activity-group-defaults');
  const context = document.getElementById('activity-group-context');
  const image = document.getElementById('id_header_image');
  if (group && defaults && context && image) {
    const choices = JSON.parse(defaults.textContent);
    function update(applyImage) {
      const selected = choices[group.value];
      context.hidden = !selected;
      context.textContent = selected ? `Creating an activity for ${selected.name}` : '';
      if (applyImage) image.value = selected ? selected.image : '';
    }
    group.addEventListener('change', () => update(true));
    update(false);
  }

  document.querySelectorAll('[data-counter-for]').forEach(counter => {
    const input = document.getElementById(counter.dataset.counterFor);
    const limit = Number(counter.dataset.limit);
    if (!input) return;
    function update() {
      const count = Array.from(input.value).length;
      const near = count >= Math.ceil(limit * 0.8);
      counter.dataset.nearLimit = String(near);
      counter.textContent = `${count} / ${limit}${near ? ' — Near the limit; keep this short for cards.' : ''}`;
    }
    input.addEventListener('input', update);
    update();
  });
}());
