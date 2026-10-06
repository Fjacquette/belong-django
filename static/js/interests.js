(() => {
  const picker = document.querySelector('[data-interest-picker]');
  if (!picker) return;
  const choices = [...picker.querySelectorAll('[data-interest-choice]')];
  const sections = [...picker.querySelectorAll('[data-interest-section]')];
  const search = picker.querySelector('#interest-search');
  const selected = picker.querySelector('[data-interest-selected]');
  picker.querySelector('[data-interest-search-container]').hidden = false;
  function refreshSelected() {
    selected.replaceChildren();
    const checked = choices.filter(choice => choice.querySelector('input').checked);
    picker.querySelector('[data-interest-count]').textContent = `${checked.length} of 20 selected`;
    checked.forEach(choice => {
      const name = choice.querySelector('span').textContent;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'ui-button ui-button--quiet';
      button.textContent = `${name} ×`;
      button.setAttribute('aria-label', `Remove ${name}`);
      button.addEventListener('click', () => {
        choice.querySelector('input').checked = false;
        refreshSelected();
        search.focus();
      });
      selected.append(button);
    });
  }
  picker.addEventListener('change', refreshSelected);
  search.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    let matches = 0;
    sections.forEach((section, index) => {
      let sectionMatches = 0;
      section.querySelectorAll('[data-interest-choice]').forEach(choice => {
        const match = choice.textContent.toLocaleLowerCase().includes(query) ||
          section.querySelector('summary').textContent.toLocaleLowerCase().includes(query);
        choice.hidden = !match;
        if (match) sectionMatches++;
      });
      section.hidden = !sectionMatches;
      section.open = query ? !!sectionMatches : index === 0;
      matches += sectionMatches;
    });
    picker.querySelector('[data-interest-no-results]').hidden = !!matches;
  });
  refreshSelected();
})();
