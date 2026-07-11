import type { Metadata } from 'next';
import Link from 'next/link';
import { RESEARCH } from '@/lib/research';

export const metadata: Metadata = {
  title: 'Исследования — Население Беларуси',
  description: 'Галерея исследований проекта: иерархия городов, старение районов, миграция и другие.',
};

export default function ResearchPage() {
  const published = RESEARCH.filter((r) => r.status === 'published');
  const planned = RESEARCH.filter((r) => r.status === 'planned');
  return (
    <div className="page">
      <h1>Исследования</h1>
      <p className="page-lead">
        Каждое исследование публикуется с методологическим блоком (данные,
        преобразования, ограничения) и <Link href="/artifacts">проверяемым
        пакетом артефактов</Link>: данные + код + допущения, достаточные,
        чтобы воспроизвести и оспорить каждое число.
      </p>

      <div className="cards">
        {published.map((r) => (
          <Link key={r.slug} href={`/research/${r.slug}`} className="card">
            <div className="card-code">{r.code} · опубликовано</div>
            <div className="card-title">{r.title}</div>
            <p>{r.question}</p>
            <div className="card-foot">
              {r.artifact ? `пакет v${r.artifact.version}` : ''} · открыть →
            </div>
          </Link>
        ))}
      </div>

      <h2>В плане работ</h2>
      <div className="cards">
        {planned.map((r) => (
          <div key={r.slug} className="card planned">
            <div className="card-code">{r.code} · этап {r.stage} плана</div>
            <div className="card-title">{r.title}</div>
            <p>{r.question}</p>
          </div>
        ))}
      </div>
      <p className="hint">
        Порядок и зависимости этапов — в{' '}
        <a href="https://github.com/sergeionlyart/BY_maps/blob/master/docs/TASK_SPEC.md"
          target="_blank" rel="noreferrer">задании на доработку (TASK_SPEC.md)</a>.
      </p>
    </div>
  );
}
