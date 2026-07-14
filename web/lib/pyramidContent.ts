/** Разбор контентного файла pyramid.md (серверный код): интро до
 *  раздела аннотаций, тексты A1–A7, методблок. Тексты утверждены —
 *  парсер только раскладывает их по местам страницы. */

export interface ParsedPyramidContent {
  heading: string;
  intro: string;          // markdown до «## Аннотации…»
  annotations: Record<string, { title: string; text: string }>;
  method: string;         // markdown методблока (список)
}

export function parsePyramidContent(body: string): ParsedPyramidContent {
  const lines = body.split('\n');
  let heading = '';
  const intro: string[] = [];
  const method: string[] = [];
  const annotations: Record<string, { title: string; text: string }> = {};
  let section: 'intro' | 'ann' | 'method' = 'intro';
  for (const line of lines) {
    const h1 = line.match(/^#\s+(.+)$/);
    if (h1) { heading = h1[1].trim(); continue; }
    if (/^##\s/.test(line)) {
      section = /Методблок|Метадблок/i.test(line) ? 'method' : 'ann';
      continue;
    }
    if (section === 'intro') intro.push(line);
    else if (section === 'method') method.push(line);
    else {
      const m = line.match(/^\*\*(A\d)\s*·\s*(.+?)\*\*\s*(.+)$/);
      if (m) {
        annotations[m[1]] = {
          title: m[2].trim().replace(/\.$/, ''),
          text: m[3].trim(),
        };
      }
    }
  }
  return {
    heading,
    intro: intro.join('\n').trim(),
    annotations,
    method: method.join('\n').trim(),
  };
}
