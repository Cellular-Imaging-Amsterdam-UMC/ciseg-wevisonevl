const catalogElement = document.getElementById('gallery-data');
if (catalogElement) {
  const catalog = JSON.parse(catalogElement.textContent);
  const samples = new Map(catalog.examples.map(item => [item.name, item]));
  for (const card of document.querySelectorAll('.sample')) {
    const sample = samples.get(card.dataset.name);
    const select = card.querySelector('[data-label]');
    const refresh = () => {
      const label = sample.labels[Number(select.value)];
      const figure = card.querySelector('[data-prediction]');
      figure.replaceChildren();
      if (label.overlay) {
        const image = document.createElement('img'); image.src = label.overlay;
        image.alt = `${sample.name}: ${label.name}, werkelijke modelvoorspelling`;
        const link = document.createElement('a'); link.href = label.overlay; link.target = '_blank'; link.rel = 'noopener';
        link.append(image); figure.append(link);
      } else {
        const placeholder = document.createElement('div'); placeholder.className = 'empty-image';
        placeholder.textContent = label.status === 'failed' ? 'Geen voltooid masker voor deze prompt' : 'Berekening nog niet voltooid';
        figure.append(placeholder);
      }
      const caption = document.createElement('figcaption'); caption.textContent = 'MODELVOORSPELLING · ROZE'; figure.append(caption);
      card.querySelector('[data-prompt]').textContent = `“${label.text}” · kanaal ${label.channels.join(', ')}`;
      const status = card.querySelector('[data-status]'); status.textContent = label.message; status.className = 'status ' + label.status;
      const download = card.querySelector('[data-mask-download]'); download.hidden = !label.download;
      if (label.download) download.href = label.download;
    };
    select.addEventListener('change', refresh); refresh();
  }
  const search = document.querySelector('[data-search]');
  const category = document.querySelector('[data-category]');
  const statusFilter = document.querySelector('[data-status-filter]');
  const filter = () => {
    const query = search.value.toLowerCase(); let count = 0;
    for (const card of document.querySelectorAll('.sample')) {
      const sample = samples.get(card.dataset.name);
      const match = (!query || sample.search.toLowerCase().includes(query)) && (!category.value || sample.category === category.value) &&
        (!statusFilter.value || sample.labels.some(label => label.status === statusFilter.value));
      card.hidden = !match; count += Number(match);
    }
    document.querySelector('[data-count]').textContent = `${count} / ${catalog.examples.length} beelden`;
  };
  search.addEventListener('input', filter); category.addEventListener('change', filter); statusFilter.addEventListener('change', filter); filter();
}
