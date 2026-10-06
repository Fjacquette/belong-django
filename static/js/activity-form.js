(function () {
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
