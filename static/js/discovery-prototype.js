/* #92: native scroll drives a bounded window. No wheel/touch interception. */
(() => {
  const controls = document.querySelector('[data-prototype-controls]');
  const root = document.querySelector('[data-stack-root]');
  if (!controls || !root) return;
  const pane = document.querySelector('[data-activity-frame]');
  const originals = [...root.querySelectorAll('[data-stack-item]')];
  const countInput = controls.querySelector('[data-simulation-count]');
  const batches = controls.querySelector('[data-simulation-batches]');
  const metrics = controls.querySelector('[data-prototype-metrics]');
  const position = controls.querySelector('[data-prototype-position]');
  const navigation = controls.querySelector('[data-prototype-navigation]');
  const narrow = matchMedia('(max-width:639px)');
  const width = Number(root.dataset.cardMinWidth), gap = 24, offset = 136, cardHeight = 440;
  let mode = narrow.matches ? 'all' : 'moving';
  let items = originals, columns = 1, slots = 0, start = 0, generation = 0, frame;
  let track, stage, selected, started = performance.now();
  let simulation = false, wanted = originals.length, firstDisplay;
  controls.querySelector('[data-prototype-modes]').hidden = false;
  controls.querySelector('[data-prototype-simulation]').hidden = false;
  // The prototype never reads/writes the production view preference.
  function report() {
    firstDisplay ??= Math.round(performance.now() - started);
    metrics.textContent = `${simulation ? 'Simulation' : 'Real results'}: ${items.length}/${wanted} cards; ${root.querySelectorAll('.activity-card').length} live card nodes; first display ${firstDisplay}ms (layout only).`;
  }
  function top() { return root.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop; }
  function choose(item) {
    if (selected) selected.removeAttribute('data-selected');
    selected = item;
    item.dataset.selected = '';
  }
  function prepare(item) {
    if (item.dataset.prototypePrepared) return;
    item.dataset.prototypePrepared = 'true';
    item.tabIndex = 0;
    item.setAttribute('role', 'group');
    item.setAttribute('aria-label', `Examine ${item.querySelector('h2').textContent.trim()}`);
    item.addEventListener('click', event => {
      if (mode !== 'moving' && mode !== 'paged') return;
      if (selected !== item && Number(item.style.getPropertyValue('--prototype-z')) < slots + 1) {
        event.preventDefault(); choose(item); item.focus({preventScroll:true});
      }
    });
    item.addEventListener('focusin', () => choose(item));
    item.addEventListener('keydown', event => {
      if (event.target === item && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault(); choose(item);
      }
    });
  }
  function draw() {
    frame = null;
    if (!stage) return;
    const relative = Math.max(0, pane.scrollTop - top());
    const maxRow = Math.max(0, Math.ceil(items.length / columns) - slots - 1);
    const row = mode === 'moving' ? Math.min(maxRow, Math.floor(relative / offset)) : start;
    const fraction = mode === 'moving' && row < maxRow ? relative % offset : 0;
    const visible = items.slice(row * columns, Math.min(items.length, (row + slots + 1 + (fraction > 0 ? 1 : 0)) * columns));
    // Keep focused content attached and reachable until the user leaves it.
    const focused = items.find(item => item.contains(document.activeElement));
    if (focused && !visible.includes(focused)) visible.push(focused);
    const current = new Set(visible);
    stage.querySelectorAll('[data-stack-item]').forEach(item => { if (!current.has(item)) item.remove(); });
    visible.forEach(item => {
      const index = items.indexOf(item), local = Math.floor(index / columns) - row;
      let y = local * offset - fraction;
      if (item === focused && (local < 0 || local > slots)) y = slots * offset;
      item.className = 'prototype-item';
      item.style.setProperty('--prototype-y', `${y}px`);
      item.style.setProperty('--prototype-z', Math.max(1, local + 1));
      const column = stage.children[index % columns];
      if (item.parentElement !== column) column.append(item);
    });
    position.textContent = `${row * columns + 1}–${Math.min(items.length, (row + slots + 1) * columns)} of ${items.length}`;
    controls.querySelector('[data-prototype-previous]').disabled = row === 0;
    controls.querySelector('[data-prototype-next]').disabled = row >= maxRow;
    report();
  }
  function layout() {
    if (!root.clientWidth) return;
    const focus = document.activeElement;
    const savedScroll = pane.scrollTop;
    columns = Math.max(1, Math.min(5, Math.floor((root.clientWidth + gap) / (width + gap))));
    // Use the pane after controls have scrolled away; short viewports use full grid.
    const available = pane.clientHeight - 24;
    slots = Math.max(0, Math.floor((available - cardHeight) / offset));
    const moving = mode === 'moving' || mode === 'paged';
    root.replaceChildren(); stage = null; track = null;
    root.style.display = moving && available >= cardHeight ? 'block' : 'grid';
    root.style.gridTemplateColumns = `repeat(${columns}, minmax(0, ${Math.min(width,root.clientWidth)}px))`;
    navigation.hidden = !moving || available < cardHeight;
    items.forEach(item => { prepare(item); item.className = ''; item.style.removeProperty('--prototype-y'); });
    if (moving && available >= cardHeight) {
      track = document.createElement('div'); track.className = 'prototype-track';
      stage = document.createElement('div'); stage.className = 'prototype-stage';
      const height = cardHeight + slots * offset;
      const rows = Math.ceil(items.length / columns);
      track.style.height = `${(mode === 'moving' ? pane.clientHeight : height) + (mode === 'moving' ? Math.max(0, rows - slots - 1) * offset : 0)}px`;
      stage.style.height = `${height}px`;
      stage.style.gridTemplateColumns = `repeat(${columns}, minmax(0, ${Math.min(width,root.clientWidth)}px))`;
      for (let i=0;i<columns;i++) { const c=document.createElement('div'); c.className='prototype-column'; stage.append(c); }
      track.append(stage); root.append(track); draw();
    } else if (mode === 'stacked') {
      for(let c=0;c<columns;c++) {
        const stack=document.createElement('div'); stack.className='activity-stack';
        const bucket=items.filter((_,i)=>i%columns===c);
        stack.style.setProperty('--stack-depth',bucket.length-1);
        bucket.forEach((item,i)=>{ item.className='activity-stack__layer'; item.style.setProperty('--stack-index',i); item.style.setProperty('--stack-z',i+1); stack.append(item); });
        root.append(stack);
      }
    } else { root.append(...items); }
    if (focus && root.contains(focus)) focus.focus({preventScroll:true});
    pane.scrollTop = savedScroll;
    controls.querySelectorAll('[name=prototype-mode]').forEach(input=>input.checked=input.value===mode);
    requestAnimationFrame(report);
  }
  pane.addEventListener('scroll', () => {
    if (!frame) frame = requestAnimationFrame(draw);
  }, {passive:true});
  function jump(direction) {
    const row=Math.floor(Math.max(0,pane.scrollTop-top())/offset);
    const max=Math.max(0,Math.ceil(items.length/columns)-slots-1);
    start=Math.max(0,Math.min(max,(mode==='paged'?start:row)+direction*(slots+1)));
    if(mode==='moving') pane.scrollTop=top()+start*offset; else draw();
  }
  controls.querySelector('[data-prototype-previous]').addEventListener('click',()=>jump(-1));
  controls.querySelector('[data-prototype-next]').addEventListener('click',()=>jump(1));
  controls.querySelectorAll('[name=prototype-mode]').forEach(input=>input.addEventListener('change',()=>{
    mode=input.value; start=0; layout();
  }));
  function simulate() {
    const token=++generation;
    simulation=Number(countInput.value)>0; wanted=Number(countInput.value)||originals.length;
    selected=null; start=0; started=performance.now(); firstDisplay=undefined;
    if(!simulation) {items=originals;layout();return;}
    items=[];
    function append() {
      if(token!==generation)return;
      const end=Math.min(wanted,items.length+(batches.checked?24:wanted));
      for(let i=items.length;i<end;i++) {
        const item=originals[i%originals.length].cloneNode(true);
        item.removeAttribute('data-prototype-prepared'); item.removeAttribute('data-selected');
        item.dataset.simulated = 'true';
        item.querySelectorAll('[id]').forEach(node=>node.removeAttribute('id'));
        item.querySelectorAll('form').forEach(form=>form.remove());
        item.querySelectorAll('a').forEach(a=>{a.removeAttribute('href');a.removeAttribute('hx-get');});
        item.querySelectorAll('button,input,summary').forEach(node=>{node.tabIndex=-1;if('disabled' in node)node.disabled=true;});
        item.querySelector('h2 a').textContent=`Simulation ${i+1}: ${originals[i%originals.length].querySelector('h2').textContent.trim()}`;
        // Preserve the same card bands/assets, but no copied business actions.
        item.addEventListener('click',event=>event.preventDefault());
        items.push(item);
      }
      layout();
      if(items.length<wanted)setTimeout(append,300);
    }
    append();
  }
  countInput.addEventListener('change',simulate); batches.addEventListener('change',simulate);
  window.addEventListener('belong:discovery-layout',layout);
  narrow.addEventListener('change',()=>{mode=narrow.matches?'all':'moving';layout();});
  layout();
})();
