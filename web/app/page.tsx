'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { RESEARCH } from '@/lib/research';
import BelarusOutline from '@/components/BelarusOutline';
import AuthorCard from '@/components/AuthorCard';

// U-01: домашний маршрут «/» — нарративный лендинг (без интерактивной карты).
// Карта переехала на «/map». Старые диплинки «/?sel=<id>» перенаправляем туда.
export default function LandingPage() {
  // читаем ?sel синхронно, чтобы не мигнуть лендингом перед редиректом
  const [redirecting] = useState(() =>
    typeof window !== 'undefined' &&
    !!new URLSearchParams(window.location.search).get('sel'));

  // ПЕРВЫЙ эффект — гвард редиректа старых диплинков на /map
  useEffect(() => {
    if (
      typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).get('sel')
    ) {
      window.location.replace('/map' + window.location.search);
    }
  }, []);

  if (redirecting) return null;

  return (
    <div className="page land">
      {/* ── Герой ─────────────────────────────────────────────── */}
      <section className="land-hero">
        <BelarusOutline className="land-hero-outline" strokeWidth={5} />
        <p className="land-kicker">Открытое исследование · 1897–2075</p>
        <h1 className="land-title">
          Население Беларуси за 129 лет — на проверяемых данных
        </h1>
        <p className="land-lead">
          Переписи 1897–2019 и оценки до 2026 года, десять исследований и прогноз
          до 2075-го. Каждое число сопровождается пакетом данных, кода и допущений,
          который можно скачать, воспроизвести и оспорить — без доверия к автору.
        </p>
        <div className="land-cta">
          <Link href="/map" className="btn primary">Открыть карту →</Link>
          <Link href="/article" className="btn">Читать статью</Link>
        </div>
      </section>

      {/* ── Сюжеты (ключевые числа + мини-графики) ────────────── */}
      <section className="land-sujets">
        <h2>Что показывают данные</h2>
        <div className="land-sujet-grid">
          {/* 1. Пик 1989 → убыль */}
          <div className="land-sujet sj-neg">
            <div className="land-sujet-chart">
              <svg
                viewBox="0 0 240 64"
                aria-hidden="true"
                style={{ width: '100%', height: 'auto', display: 'block' }}
              >
                <polyline
                  points="4,46 40,32 70,44 118,16 162,8 236,30"
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                <circle cx="162" cy="8" r="3" fill="var(--accent)" />
              </svg>
            </div>
            <div className="land-sujet-body">
              <div className="land-sujet-num">−1,14 млн</div>
              <p className="land-sujet-cap">
                Пик пройден в переписи 1989 года — 10,20 млн; к началу 2026-го —
                9,06 млн (−11% за 37 лет).
              </p>
              <Link href="/map" className="land-sujet-more">подробнее →</Link>
            </div>
          </div>

          {/* 2. Село −65% */}
          <div className="land-sujet sj-neg">
            <div className="land-sujet-chart">
              <svg
                viewBox="0 0 240 64"
                aria-hidden="true"
                style={{ width: '100%', height: 'auto', display: 'block' }}
              >
                <polyline
                  points="4,10 58,20 116,34 176,46 236,54"
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                <circle cx="236" cy="54" r="3" fill="var(--accent)" />
              </svg>
            </div>
            <div className="land-sujet-body">
              <div className="land-sujet-num">Село −65 %</div>
              <p className="land-sujet-cap">
                Сельское население: 5,52 млн (1959) → 1,91 млн (2026) — сокращение
                почти втрое.
              </p>
              <Link href="/research/aging" className="land-sujet-more">подробнее →</Link>
            </div>
          </div>

          {/* 3. Минск ×4 */}
          <div className="land-sujet sj-accent">
            <div className="land-sujet-chart">
              <svg
                viewBox="0 0 240 64"
                aria-hidden="true"
                style={{ width: '100%', height: 'auto', display: 'block' }}
              >
                <rect x="8"   y="48" width="26" height="12" fill="var(--accent)" opacity="0.55" />
                <rect x="46"  y="40" width="26" height="20" fill="var(--accent)" opacity="0.62" />
                <rect x="84"  y="30" width="26" height="30" fill="var(--accent)" opacity="0.7" />
                <rect x="122" y="22" width="26" height="38" fill="var(--accent)" opacity="0.8" />
                <rect x="160" y="12" width="26" height="48" fill="var(--accent)" opacity="0.9" />
                <rect x="198" y="4"  width="26" height="56" fill="var(--accent)" />
              </svg>
            </div>
            <div className="land-sujet-body">
              <div className="land-sujet-num">Минск ×4</div>
              <p className="land-sujet-cap">
                Столица выросла вчетверо за советский период — 516 тыс. (1959) →
                ~2,0 млн; сегодня Минск вчетверо больше второго города.
              </p>
              <Link href="/research/zipf" className="land-sujet-more">подробнее →</Link>
            </div>
          </div>

          {/* 4. Три сценария до 2075 */}
          <div className="land-sujet sj-multi">
            <div className="land-sujet-chart">
              <svg
                viewBox="0 0 240 64"
                aria-hidden="true"
                style={{ width: '100%', height: 'auto', display: 'block' }}
              >
                {/* оптимистический = зелёный, длинный штрих */}
                <polyline points="10,20 236,24" fill="none"
                  stroke="var(--pos)" strokeWidth="2" strokeLinecap="round"
                  strokeDasharray="7 4" />
                {/* базовый = синий, сплошной */}
                <polyline points="10,20 236,40" fill="none"
                  stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" />
                {/* негативный = терракотовый, пунктир */}
                <polyline points="10,20 236,58" fill="none"
                  stroke="var(--neg)" strokeWidth="2" strokeLinecap="round"
                  strokeDasharray="2 3" />
                <circle cx="10" cy="20" r="3" fill="var(--accent)" />
              </svg>
            </div>
            <div className="land-sujet-body">
              <div className="land-sujet-num">3 сценария</div>
              <p className="land-sujet-cap">
                Прогноз до 2075 года расходится веером: 7,11 млн (оптимистический),
                5,97 млн (базовый), 4,33 млн (негативный).
              </p>
              <Link href="/map" className="land-sujet-more">подробнее →</Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Исследования ──────────────────────────────────────── */}
      <section className="land-research">
        <h2>Исследования</h2>
        <p className="page-lead">
          Десять тем — от иерархии городов до чернобыльского следа. Каждая
          публикуется с методологическим блоком и{' '}
          <Link href="/artifacts">проверяемым пакетом артефактов</Link>.
        </p>
        <div className="cards">
          {RESEARCH.map((r) =>
            r.status === 'published' ? (
              <Link key={r.slug} href={`/research/${r.slug}`} className="card">
                <div className="card-code"><span className="ccode">{r.code}</span> · опубликовано</div>
                <div className="card-title">{r.title}</div>
                <p>{r.question}</p>
                <div className="card-foot">
                  {r.artifact ? <><span className="card-ver">пакет v{r.artifact.version}</span> · </> : null}открыть →
                </div>
              </Link>
            ) : (
              <div key={r.slug} className="card planned">
                <div className="card-code">
                  <span className="ccode">{r.code}</span> · этап {r.stage} плана{' '}
                  <span className="badge">готовится</span>
                </div>
                <div className="card-title">{r.title}</div>
                <p>{r.question}</p>
              </div>
            ),
          )}
        </div>
      </section>

      {/* ── «Проверь сам» ─────────────────────────────────────── */}
      <section className="land-verify">
        <h2>Проверь сам</h2>
        <p className="page-lead">
          К каждому исследованию и к прогнозу приложен zip-пакет по единому
          стандарту: сырые и очищенные данные, код с фиксированными зависимостями,
          все допущения в явном виде и манифест с контрольными суммами sha256.
          Пересборка в чистом окружении совпадает с опубликованной байт-в-байт.
        </p>
        <div className="land-cta">
          <Link href="/artifacts" className="btn primary">
            Скачать пакеты и проверить
          </Link>
        </div>
      </section>

      {/* ── О проекте / авторе ────────────────────────────────── */}
      <section className="land-about">
        <h2>Кто это сделал и зачем</h2>
        <p className="page-lead">
          BY Maps — самостоятельное открытое исследование демографии Беларуси на
          проверяемых данных, с явно выписанными предпосылками и ограничениями.
          Проект не заменяет профессиональную демографию: его прогнозы — условные
          сценарии, а корреляции — не причинность.
        </p>
        <AuthorCard variant="full" lang="ru" />
        <p className="land-about-note">
          BY Maps — витрина метода: так же можно разобрать ваши данные и процессы.
        </p>
        <div className="land-cta">
          <a href="https://www.linkedin.com/in/sergei-audzeichyk" target="_blank" rel="noreferrer" className="btn">LinkedIn</a>
          <Link href="/about" className="btn">О проекте</Link>
          <Link href="/methodology" className="btn">Методология</Link>
        </div>
      </section>
    </div>
  );
}
