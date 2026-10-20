(() => {
  const root = document.documentElement;
  try { root.dataset.theme = localStorage.getItem('aa-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'); } catch (_) {}
  document.querySelector('#theme').addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('aa-theme', root.dataset.theme); } catch (_) {}
  });
  const search = document.querySelector('#search');
  const contents = document.querySelector('#contents');
  contents.addEventListener('click', () => {
    const expanded = contents.getAttribute('aria-expanded') !== 'true';
    contents.setAttribute('aria-expanded', String(expanded));
    document.querySelector('aside').dataset.expanded = String(expanded);
  });
  document.querySelectorAll('nav a').forEach(link => link.addEventListener('click', () => {
    if (matchMedia('(max-width: 850px)').matches) {
      contents.setAttribute('aria-expanded', 'false');
      document.querySelector('aside').dataset.expanded = 'false';
    }
  }));
  const cards = [...document.querySelectorAll('.searchable')];
  search.addEventListener('input', () => {
    const query = search.value.toLocaleLowerCase().trim();
    let visible = 0;
    cards.forEach(card => {
      card.hidden = query !== '' && !card.textContent.toLocaleLowerCase().includes(query);
      if (!card.hidden) visible++;
      if (query && !card.hidden) card.querySelectorAll('details').forEach(d => d.open = true);
    });
    document.querySelector('#search-status').textContent = query ? `${visible} matching sections` : '';
  });
  function revealHash() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
    const node = document.getElementById(id);
    if (!node) return;
    let parent = node;
    while (parent) {
      parent.hidden = false;
      if (parent.tagName === 'DETAILS') parent.open = true;
      parent = parent.parentElement;
    }
    node.scrollIntoView({block: 'start'});
  }
  addEventListener('hashchange', revealHash);
  if (location.hash) revealHash();
  let previousDetails = [];
  addEventListener('beforeprint', () => {
    previousDetails = [...document.querySelectorAll('details')].map(d => [d, d.open]);
    previousDetails.forEach(([d]) => d.open = true);
  });
  addEventListener('afterprint', () => previousDetails.forEach(([d, open]) => d.open = open));
  document.querySelector('#print').addEventListener('click', () => print());
})();
