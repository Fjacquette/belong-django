/* #92 experiment: native scroll advances F; only explicit set buttons advance A. */
(() => {
  const controls = document.querySelector('[data-prototype-controls]');
  const root = document.querySelector('[data-stack-root]');
  const viewport = document.querySelector('[data-prototype-scroll]');
  if (!controls || !root || !viewport) return;
  const originals = [...root.querySelectorAll('[data-stack-item]')];
  const fallback = document.querySelector('[data-prototype-demo-template]')?.content.firstElementChild;
  const countInput = controls.querySelector('[data-simulation-count]');
  const batches = controls.querySelector('[data-simulation-batches]');
  const metrics = controls.querySelector('[data-prototype-metrics]');
  const position = controls.querySelector('[data-prototype-position]');
  const navigation = controls.querySelector('[data-prototype-navigation]');
  const previous = controls.querySelector('[data-prototype-previous]');
  const next = controls.querySelector('[data-prototype-next]');
  const narrow = matchMedia('(max-width:639px)');
  const tokens = getComputedStyle(root);
  const number = name => parseFloat(tokens.getPropertyValue(name));
  const width = number('--card-min-width'), gap = number('--stack-gap');
  const cardHeight = number('--card-height');
  const read = key => { try { return localStorage.getItem(key); } catch { return null; } };
  const save = (key, value) => { try { localStorage.setItem(key, value); } catch { /* Storage is optional. */ } };
  const savedMode = read('belong-prototype-card-view');
  let explicitMode = ['moving','paged','stacked','all'].includes(savedMode);
  let mode = explicitMode ? savedMode : narrow.matches ? 'all' : 'moving';
  let density = read('belong-prototype-stack-density') === 'tight' ? 'tight' : 'regular';
  let offset = number('--band-1') + (density === 'regular' ? number('--band-2') : 0);
  let hovered;
  let items = [], columns = 1, slots = 0, pageStart = 0, generation = 0, frame;
  let stage, selected, wanted = 0, started, firstDisplay, actualStack = false;
  controls.querySelector('[data-prototype-modes]').hidden = false;
  controls.querySelector('[data-prototype-simulation]').hidden = false;
  controls.querySelector('[data-prototype-density]').hidden = false;
  function report() {
    firstDisplay ??= Math.round(performance.now() - started);
    const real = items.filter(item => !item.hasAttribute('data-simulated')).length;
    metrics.textContent = `${real} real + ${items.length-real} demo cards (${items.length}/${wanted} loaded); ${root.querySelectorAll('.activity-card').length} attached; first layout ${firstDisplay}ms. Demo cards have no actions.${Number(root.dataset.available) < cardHeight && mode !== 'all' ? ' Short stage: full-card scrolling fallback.' : ''}`;
  }
  function dismiss(moveFocus = false) {
    if (!selected) return;
    if (moveFocus && selected.contains(document.activeElement)) viewport.focus({preventScroll:true});
    selected.querySelectorAll('details[open]').forEach(menu => { menu.open = false; });
    selected.removeAttribute('data-selected');
    selected = null;
  }
  function toggle(item) {
    const closing = selected === item;
    dismiss();
    if (!closing) { selected = item; item.dataset.selected = ''; }
    if (stage) draw(); else paint();
  }
  function prepare(item) {
    if (item.querySelector('[data-prototype-expose]')) return;
    item.dataset.prototypePrepared = 'true';
    item.removeAttribute('tabindex');
    item.setAttribute('role', 'group');
    const title = item.querySelector('h2').textContent.trim();
    item.setAttribute('aria-label', title);
    // A separate native button keeps title links, menus and response actions honest.
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'ui-disclosure prototype-expose';
    button.dataset.prototypeExpose = '';
    button.dataset.cardTitle = title;
    button.addEventListener('click', () => toggle(item));
    button.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
    const header = item.querySelector('.activity-card__band-1');
    header.append(button);
    header.addEventListener('click', event => {
      if (root.dataset.renderedMode === 'all' || event.target.closest('a,button,input,summary,label,details,form')) return;
      toggle(item);
    });
  }
  function paint() {
    root.querySelectorAll('[data-stack-item]').forEach(item => {
      prepare(item);
      const overlap = root.dataset.renderedMode !== 'all';
      const active = selected ? item === selected : item.hasAttribute('data-foreground');
      item.toggleAttribute('data-covered', overlap && !active);
      item.toggleAttribute('data-pointer-active', overlap && item === hovered);
      item.toggleAttribute('data-prototype-raised', overlap && item === selected);
      const button = item.querySelector('[data-prototype-expose]');
      const expanded = item === selected;
      button.setAttribute('aria-expanded', String(expanded));
      button.setAttribute('aria-label', `${expanded ? 'Return card to stack' : 'Show full card'}: ${button.dataset.cardTitle}`);
      button.title = expanded ? 'Return card to stack' : 'Show full card';
      // Classic stacks keep their natural geometry except for the one explicit
      // exposure, fitted to the current visible viewport. Closing removes it.
      item.style.removeProperty('top');
      if (!stage && overlap && expanded) {
        const top = viewport.getBoundingClientRect().top - item.parentElement.getBoundingClientRect().top;
        const rest = Number(item.style.getPropertyValue('--stack-index')) * offset;
        item.style.top = `${Math.max(top, Math.min(top + Number(root.dataset.available) - cardHeight, rest))}px`;
      }
    });
  }
  function draw() {
    frame = null;
    if (!stage) return;
    const maxRow = Math.max(0, Math.ceil(items.length / columns) - slots - 1);
    const relative = viewport.scrollTop;
    const row = mode === 'moving' ? Math.min(maxRow, Math.floor(relative / offset)) : Math.floor(pageStart / columns);
    const fraction = mode === 'moving' && row < maxRow ? relative % offset : 0;
    const end = Math.min(items.length, (row + slots + 1) * columns);
    const visibleEnd = Math.min(items.length, end + (fraction > 0 ? columns : 0));
    const visible = items.slice(row * columns, visibleEnd);
    const front = new Map();
    visible.forEach(item => front.set(items.indexOf(item) % columns, item));
    const retainedSelection = selected && !visible.includes(selected) ? selected : null;
    if (retainedSelection) visible.push(retainedSelection);
    // Retain keyboard focus without automatically exposing that card.
    const focused = items.find(item => item.contains(document.activeElement));
    const retainedFocus = focused && !visible.includes(focused) ? focused : null;
    if (retainedFocus) visible.push(retainedFocus);
    const keep = new Set(visible);
    stage.querySelectorAll('[data-stack-item]').forEach(item => { if (!keep.has(item)) item.remove(); });
    visible.forEach(item => {
      const index = items.indexOf(item), local = Math.floor(index / columns) - row;
      const foreground = front.get(index % columns) === item;
      item.toggleAttribute('data-foreground', foreground);
      let y = local * offset - fraction;
      // Only covered headers may enter/leave clipped. Let the complete
      // foreground move continuously once it reaches the fitting boundary.
      if (foreground) y = Math.max(0, Math.min(stage.clientHeight-cardHeight, y));
      if (item === selected)
        y = Math.max(0, Math.min(stage.clientHeight-cardHeight, y));
      item.className = 'prototype-item';
      item.style.setProperty('--prototype-y', `${y}px`);
      item.style.setProperty('--prototype-z', Math.max(1, local + 1));
      const column = stage.children[index % columns];
      if (item.parentElement !== column) column.append(item);
    });
    root.dataset.firstIndex = row * columns;
    root.dataset.fraction = fraction;
    position.textContent = `${row * columns + 1}–${visibleEnd} / ${items.length}${retainedSelection ? ` · exposed #${items.indexOf(retainedSelection)+1}` : ''}${retainedFocus ? ` · focused #${items.indexOf(retainedFocus)+1}` : ''}`;
    paint();
    previous.disabled = pageStart === 0;
    next.disabled = end >= items.length;
    report();
  }
  function layout() {
    if (!root.clientWidth || !viewport.clientHeight) return;
    const focus = document.activeElement, oldScroll = viewport.scrollTop;
    const oldOffset = offset;
    const anchor = stage ? Number(root.dataset.firstIndex || 0) : Math.floor(oldScroll / oldOffset) * columns;
    const fraction = stage ? Number(root.dataset.fraction || 0) / oldOffset : oldScroll % oldOffset / oldOffset;
    offset = number('--band-1') + (density === 'regular' ? number('--band-2') : 0);
    root.style.setProperty('--stack-offset', `${offset}px`);
    const oldColumns = columns, hadStage = !!stage;
    columns = Math.max(1, Math.min(Number(root.dataset.maxColumns), Math.floor((root.clientWidth + gap) / (width + gap))));
    const style = getComputedStyle(viewport);
    const available = viewport.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
    slots = Math.max(0, Math.floor((available - cardHeight) / offset));
    actualStack = (mode === 'moving' || mode === 'paged') && available >= cardHeight;
    root.replaceChildren(); stage = null;
    root.style.display = actualStack ? 'block' : 'grid';
    root.style.gridTemplateColumns = `repeat(${columns}, minmax(0, ${Math.min(width,root.clientWidth)}px))`;
    navigation.hidden = mode !== 'paged';
    previous.disabled = !actualStack; next.disabled = !actualStack;
    root.dataset.mode = mode;
    root.dataset.renderedMode = available < cardHeight ? 'all' : mode;
    root.dataset.density = density;
    root.dataset.columns = columns;
    root.dataset.strips = slots;
    root.dataset.available = available;
    items.forEach((item,index) => { prepare(item); item.dataset.prototypeIndex=index+1; item.className = ''; item.removeAttribute('data-foreground'); item.style.removeProperty('--prototype-y'); });
    if (actualStack) {
      const track = document.createElement('div'); track.className = 'prototype-track';
      stage = document.createElement('div'); stage.className = 'prototype-stage';
      const maxRow = Math.max(0, Math.ceil(items.length / columns) - slots - 1);
      // Padding + viewport-height stage make the final row land exactly at the
      // scrollbar end. A has no artificial scroll runway at all.
      track.style.height = `${available + (mode === 'moving' ? maxRow * offset : 0)}px`;
      stage.style.height = `${available}px`;
      stage.style.gridTemplateColumns = root.style.gridTemplateColumns;
      for (let i=0;i<columns;i++) { const c=document.createElement('div'); c.className='prototype-column'; stage.append(c); }
      track.append(stage); root.append(track);
      if (mode === 'paged') {
        pageStart = Math.floor(pageStart / (columns*(slots+1))) * columns*(slots+1);
        pageStart = Math.min(pageStart, Math.floor(Math.max(0,items.length-1)/(columns*(slots+1)))*columns*(slots+1));
        viewport.scrollTop = 0;
      } else {
        const desired = hadStage && (columns !== oldColumns || offset !== oldOffset) ? Math.floor(anchor/columns)*offset+fraction*offset : oldScroll;
        viewport.scrollTop = Math.min(maxRow*offset, desired);
      }
      draw();
    } else if (mode === 'stacked' && available >= cardHeight) {
      for(let c=0;c<columns;c++) {
        const stack=document.createElement('div'); stack.className='activity-stack';
        const bucket=items.filter((_,i)=>i%columns===c);
        stack.style.setProperty('--stack-depth',bucket.length-1);
        bucket.forEach((item,i)=>{ item.className='activity-stack__layer'; item.style.setProperty('--stack-index',i); item.style.setProperty('--stack-z',i+1); item.toggleAttribute('data-foreground',i===bucket.length-1); stack.append(item); });
        root.append(stack);
      }
      viewport.scrollTop = Math.floor(anchor/columns)*offset+fraction*offset;
      position.textContent = `${items.length} cards`;
    } else {
      root.append(...items); viewport.scrollTop = oldScroll;
      position.textContent = `${items.length} cards`;
    }
    if (focus && root.contains(focus)) focus.focus({preventScroll:true});
    controls.querySelectorAll('[name=prototype-mode]').forEach(input=>input.checked=input.value===mode);
    controls.querySelectorAll('[name=prototype-density]').forEach(input=>input.checked=input.value===density);
    paint(); report();
  }
  viewport.addEventListener('scroll', () => {
    hovered = null; paint();
    if (!frame) frame = requestAnimationFrame(draw);
  }, {passive:true});
  viewport.addEventListener('pointermove', event => {
    if (event.pointerType !== 'mouse' || (!event.movementX && !event.movementY)) return;
    hovered = event.target.closest('[data-stack-item]');
    paint();
  });
  viewport.addEventListener('pointerleave', () => { hovered=null; paint(); });
  // Dismiss on user intent before scrolling. Scroll events alone also come
  // from resize/reflow/programmatic positioning and must not dismiss exposure.
  function browse() {
    if (mode !== 'moving' && mode !== 'stacked') return;
    dismiss(true); hovered = null;
    if (stage) draw(); else paint();
  }
  viewport.addEventListener('wheel', event => { if (event.deltaY && !event.ctrlKey) browse(); }, {passive:true});
  viewport.addEventListener('touchmove', browse, {passive:true});
  viewport.addEventListener('keydown', event => {
    if (event.target.closest('input,select,textarea')) return;
    if (event.key === ' ' && event.target.closest('button,a,summary')) return;
    if (['ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '].includes(event.key)) browse();
  });
  viewport.addEventListener('pointerdown', event => {
    if (event.clientX >= viewport.getBoundingClientRect().left + viewport.clientWidth) browse();
  });
  function jump(direction) {
    dismiss(); hovered = null;
    const size = columns * (slots + 1);
    pageStart = Math.max(0, Math.min(Math.floor((items.length-1)/size)*size, pageStart + direction*size));
    draw();
  }
  previous.addEventListener('click',()=>jump(-1));
  next.addEventListener('click',()=>jump(1));
  controls.querySelectorAll('[name=prototype-mode]').forEach(input=>input.addEventListener('change',()=>{
    dismiss(); mode=input.value; explicitMode=true; save('belong-prototype-card-view',mode); hovered=null; pageStart=0; viewport.scrollTop=0; layout();
  }));
  controls.querySelectorAll('[name=prototype-density]').forEach(input=>input.addEventListener('change',()=>{
    density=input.value; save('belong-prototype-stack-density',density); hovered=null; layout();
  }));
  const names = ['Creek trail walk', 'Board games together', 'Coffee and sketching', 'Riverside bike ride',
    'Park picnic', 'Evening book chat', 'Garden volunteer morning', 'Local photography stroll'];
  function demo(index) {
    const source = originals.length ? originals[index % originals.length] : fallback;
    const item = source.cloneNode(true);
    item.removeAttribute('data-prototype-prepared'); item.removeAttribute('data-selected');
    item.querySelector('[data-prototype-expose]')?.remove();
    item.dataset.simulated = 'true';
    item.querySelectorAll('[id]').forEach(node=>node.removeAttribute('id'));
    item.querySelectorAll('form').forEach(form=>form.remove());
    item.querySelector('.card-context-menu')?.remove();
    item.querySelectorAll('[hx-get],[hx-post]').forEach(node=>{node.removeAttribute('hx-get');node.removeAttribute('hx-post');});
    item.querySelectorAll('a').forEach(a=>a.removeAttribute('href'));
    item.querySelectorAll('button,input,summary').forEach(node=>{node.tabIndex=-1;if('disabled' in node)node.disabled=true;});
    const title = `Demo ${items.length+1}: ${names[index % names.length]}`;
    const heading = item.querySelector('h2 a'); heading.textContent=title; heading.dataset.fullText=title;
    item.querySelector('.activity-card__cta').textContent='Demo only · no actions';
    item.querySelector('.activity-card').removeAttribute('aria-live');
    item.addEventListener('click',event=>event.preventDefault());
    return item;
  }
  function collection() {
    const token=++generation, setting=countInput.value;
    dismiss();
    pageStart=0; viewport.scrollTop=0; root.dataset.firstIndex=0; root.dataset.fraction=0;
    started=performance.now(); firstDisplay=undefined;
    items = setting === '0' || setting === 'real' ? [...originals] : [];
    wanted = setting === 'real' ? originals.length : setting === '0' ? Math.max(64,originals.length) : Number(setting);
    let demoIndex=0;
    function append() {
      if(token!==generation)return;
      const end=Math.min(wanted,items.length+(batches.checked?24:wanted));
      while(items.length<end)items.push(demo(demoIndex++));
      layout();
      if(items.length<wanted)setTimeout(append,300);
    }
    append();
  }
  document.addEventListener('htmx:afterSwap', event => {
    if (root.contains(event.target)) { if (stage) draw(); else paint(); }
  });
  countInput.addEventListener('change',collection); batches.addEventListener('change',collection);
  window.addEventListener('belong:discovery-layout',layout);
  new ResizeObserver(layout).observe(viewport);
  narrow.addEventListener('change',()=>{if(!explicitMode)mode=narrow.matches?'all':'moving';layout();});
  collection();
})();
