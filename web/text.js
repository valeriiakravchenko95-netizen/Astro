// Как текст из файла трактовок превращается в абзацы на странице.
//
// Формат нарочно простой, чтобы писать его руками в JSON:
//   пустая строка (\n\n)        - новый абзац;
//   строка, начатая с «· »      - пункт списка;
//   {женская|мужская}           - слово в роде читателя.
// Род выбирается в форме и нигде не сохраняется.

let gender = 'f';

export function setGender(value) {
  gender = value === 'm' ? 'm' : 'f';
}

export function inGender(raw) {
  return String(raw).replace(/\{([^|{}]*)\|([^|{}]*)\}/g,
    (whole, female, male) => (gender === 'm' ? male : female));
}

// Возвращает узлы, готовые к вставке. Разметку не разбирает как HTML:
// всё идёт через textContent, так что символы из файла вреда не причинят.
export function textNodes(raw) {
  const nodes = [];
  for (const block of inGender(raw).split(/\n\s*\n/)) {
    const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);
    let list = null;
    for (const line of lines) {
      if (line.startsWith('·')) {
        if (!list) {
          list = document.createElement('ul');
          nodes.push(list);
        }
        const item = document.createElement('li');
        item.textContent = line.replace(/^·\s*/, '');
        list.append(item);
      } else {
        list = null;
        const paragraph = document.createElement('p');
        paragraph.textContent = line;
        nodes.push(paragraph);
      }
    }
  }
  return nodes;
}
