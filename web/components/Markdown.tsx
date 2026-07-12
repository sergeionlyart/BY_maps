'use client';

import { useMemo } from 'react';
import { slugify } from '@/lib/slug';

/** Минимальный безопасный рендерер Markdown для методблоков, методики и
 *  контентных страниц: заголовки (с якорями), абзацы, списки, таблицы,
 *  жирный/курсив/код, ссылки, hr, цитаты-плашки [Данные]/[Расчёт]/[Модель]/
 *  [Интерпретация]. Собирает React-элементы (не innerHTML) - содержимое
 *  экранировано по построению. */

const CHIP: Record<string, string> = {
  'Данные': 'data', 'Расчёт': 'calc', 'Модель': 'model',
  'Интерпретация': 'interp', 'Гипотеза': 'interp',
};

function inline(text: string, key = 0): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  // ссылки, жирный, курсив, код - по очереди через один общий regex
  const re = /\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1] !== undefined) {
      const href = m[2];
      const external = /^https?:/.test(href);
      out.push(
        <a key={`${key}-${i++}`} href={href} target={external ? '_blank' : undefined}
          rel={external ? 'noreferrer' : undefined}>{inline(m[1], key + 1)}</a>,
      );
    } else if (m[3] !== undefined) {
      out.push(<strong key={`${key}-${i++}`}>{inline(m[3], key + 1)}</strong>);
    } else if (m[4] !== undefined) {
      out.push(<em key={`${key}-${i++}`}>{inline(m[4], key + 1)}</em>);
    } else if (m[5] !== undefined) {
      out.push(<code key={`${key}-${i++}`}>{m[5]}</code>);
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({ text }: { text: string }) {
  const blocks = useMemo(() => {
    const lines = text.split('\n');
    const out: React.ReactNode[] = [];
    let i = 0;
    let k = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (!line.trim()) { i++; continue; }
      if (line.startsWith('```')) {
        const buf: string[] = [];
        i++;
        while (i < lines.length && !lines[i].startsWith('```')) buf.push(lines[i++]);
        i++;
        out.push(<pre key={k++}><code>{buf.join('\n')}</code></pre>);
        continue;
      }
      const h = line.match(/^(#{1,4})\s+(.*)/);
      if (h) {
        const Tag = (['h1', 'h2', 'h3', 'h4'] as const)[h[1].length - 1];
        const id = h[1].length >= 2 ? slugify(h[2]) : undefined;
        out.push(<Tag key={k++} id={id}>{inline(h[2], k)}</Tag>);
        i++;
        continue;
      }
      if (/^(-{3,}|\*{3,})\s*$/.test(line)) { out.push(<hr key={k++} />); i++; continue; }
      // цитата: собираем блок '>' -> абзацы; абзацы с префиксом **[Метка]**
      // рендерятся плашками-«чипами», прочие — обычной цитатой
      if (/^>\s?/.test(line)) {
        const raw: string[] = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          raw.push(lines[i].replace(/^>\s?/, ''));
          i++;
        }
        // разбить на абзацы по пустым строкам
        const paras: string[] = [];
        let cur = '';
        for (const l of raw) {
          if (!l.trim()) { if (cur) { paras.push(cur); cur = ''; } }
          else cur += (cur ? ' ' : '') + l.trim();
        }
        if (cur) paras.push(cur);
        for (const p of paras) {
          const cm = p.match(/^\*\*\[([^\]]+)\]\*\*\s*(.*)$/);
          if (cm && CHIP[cm[1]]) {
            out.push(
              <div className={`chip chip-${CHIP[cm[1]]}`} key={k++}>
                <span className="chip-tag">{cm[1]}</span>
                <span>{inline(cm[2], k)}</span>
              </div>,
            );
          } else {
            out.push(<blockquote key={k++}>{inline(p, k)}</blockquote>);
          }
        }
        continue;
      }
      if (/^[-*]\s+/.test(line)) {
        const items: string[] = [];
        while (i < lines.length && (/^[-*]\s+/.test(lines[i]) || /^\s{2,}\S/.test(lines[i]))) {
          if (/^[-*]\s+/.test(lines[i])) items.push(lines[i].replace(/^[-*]\s+/, ''));
          else items[items.length - 1] += ' ' + lines[i].trim();
          i++;
        }
        out.push(<ul key={k++}>{items.map((it, j) => <li key={j}>{inline(it, j)}</li>)}</ul>);
        continue;
      }
      if (/^\d+\.\s+/.test(line)) {
        const items: string[] = [];
        while (i < lines.length && (/^\d+\.\s+/.test(lines[i]) || /^\s{2,}\S/.test(lines[i]))) {
          if (/^\d+\.\s+/.test(lines[i])) items.push(lines[i].replace(/^\d+\.\s+/, ''));
          else items[items.length - 1] += ' ' + lines[i].trim();
          i++;
        }
        out.push(<ol key={k++}>{items.map((it, j) => <li key={j}>{inline(it, j)}</li>)}</ol>);
        continue;
      }
      if (line.trimStart().startsWith('|')) {
        const rows: string[][] = [];
        while (i < lines.length && lines[i].trimStart().startsWith('|')) {
          const cells = lines[i].trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
          if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells);
          i++;
        }
        out.push(
          <div className="md-table-wrap" key={k++}>
            <table>
              <thead><tr>{rows[0]?.map((c, j) => <th key={j}>{inline(c, j)}</th>)}</tr></thead>
              <tbody>
                {rows.slice(1).map((r, ri) => (
                  <tr key={ri}>{r.map((c, j) => <td key={j}>{inline(c, j)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>,
        );
        continue;
      }
      // абзац: собираем до пустой строки
      const buf: string[] = [];
      while (i < lines.length && lines[i].trim() &&
             !/^(#{1,4}\s|[-*]\s|\d+\.\s|\||```|-{3,}\s*$)/.test(lines[i].trimStart())) {
        buf.push(lines[i].trim());
        i++;
      }
      out.push(<p key={k++}>{inline(buf.join(' '), k)}</p>);
    }
    return out;
  }, [text]);

  return <div className="md">{blocks}</div>;
}
