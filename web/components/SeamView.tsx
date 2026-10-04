'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import MethodDrawer from './MethodDrawer';
import { useT, useLang } from '@/lib/i18n';

/** INF-20 «Шов на карте»: вердикты гипотез, главные оценки разрыва на пяти
 *  границах и иллюстрации. Данные — /data/seam.json (etl/seam.py; тот же файл
 *  воспроизводит пакет by-maps-seam). Все русские строки — через t(). */

interface Est {
  outcome: string;
  seg: string;
  spec: string;
  added?: boolean;
  tau: number | null;
  se?: number;
  p?: number | null;
  n_by?: number;
  n_nb?: number;
  clusters?: number;
}
interface SeamMeta {
  h_main_km: number;
  alpha: number;
  cells_total: number;
  cells_by_segment: Record<string, { by: number; nb: number }>;
  outcomes: Record<string, { label: string; family: string }>;
  segments: Record<string, string>;
}
interface Hyp {
  verdict: string;
  sig_segments?: string[];
  did?: Record<string, { raw: boolean }>;
  neg_segments?: string[];
  neg_segments_built_only?: string[];
  pl_tau?: number | null;
  ua?: Est | null;
  checks?: Record<string, boolean | null>;
}
interface SeamData {
  meta: SeamMeta;
  hypotheses: Record<string, Hyp>;
  estimates: Est[];
  /** блок официального населения (H5); null, пока таблиц единиц нет */
  units?: {
    twins?: unknown[];
    comparison?: Record<string, { nb_median: number | null; by_median: number | null }>;
  } | null;
}

const SEGS = ['PL', 'LT', 'LV', 'RU', 'UA'];
const MAIN_OUTCOMES = ['B_9015', 'G_7590', 'G_9015', 'L_9212', 'L_1924', 'C_0319', 'I_2019', 'lvl_crop19'];
/** исходы в п.п./% — один знак после запятой; логарифмические — три */
const PP_OUTCOMES = new Set(['C_0319', 'lvl_crop19']);
const ZIP = 'by-maps-seam-v1.0.0.zip';

/** Формулировки гипотез — сокращённо по пререгистрации (docs/preregistration/seam-v0.1.md, §4). */
const HYP_TEXT: Record<string, string> = {
  H1: 'Государство против географии: скачок в росте застройки 1990→2015 значим хотя бы на 3 из 5 границ, а на бывших советских границах после 1991 года он больше, чем до',
  H2: 'Удержание пашни: у России, Литвы, Латвии и Украины доля пашни 2003→2019 у самой линии падает сильнее, чем на белорусской стороне; на польской границе разница меньше 2 п.п.',
  H3: 'Огни ≠ благосостояние: при равной застройке и населении белорусская сторона светится ярче хотя бы на 4 из 5 границ',
  H4: '2020+: за 2019→2024 огни на украинской стороне падают относительно белорусской',
  H5: 'Официальное население: в приграничье Литвы, Латвии и России убывает быстрее, чем в белорусских районах напротив, в Польше — медленнее (описательно)',
};

const GALLERY: { file: string; caption: string }[] = [
  { file: 'cover', caption: 'Доля пашни в квадратах по 1 км в полосе ±50 км вокруг Беларуси, 2019 год' },
  { file: 'fields', caption: 'Находка 1. Шов виден в полях: скачок изменения доли пашни 2003→2019, сосед минус Беларусь' },
  { file: 'houses', caption: 'Находка 2. В застройке шва почти нет: в основной оценке скачок в росте застройки WSF 1990→2015 не значим ни на одной границе' },
  { file: 'lights', caption: 'Находка 3. Огни: 2019→2024 (вверху) и 1992→2012 (внизу); устойчив разлом на украинском участке' },
  { file: 'light_policy', caption: 'Находка 4. Огни без «пересвета»: в основной оценке скачка яркости при равной застройке нет ни на одной границе' },
  { file: 'scorecard', caption: 'Вердикты по гипотезам, записанным до расчёта' },
  // рисуется только вместе с блоком официального населения (seam.json → units.twins);
  // без него карточка не показывается и файл не запрашивается
  { file: 'twins', caption: 'Пары-близнецы: население районов-соседей через линию, первый год = 100' },
];

const MINUS = '−';

/** Число со знаком и десятичной запятой: +13,4 / −0,268; ноль без знака. */
function fmtNum(v: number, d: number, signed = true): string {
  const s = Math.abs(v).toFixed(d).replace('.', ',');
  if (!signed || /^0(,0+)?$/.test(s)) return s;
  return (v < 0 ? MINUS : '+') + s;
}
function fmtP(p: number): string {
  return p < 0.001 ? 'p < 0,001' : `p = ${p.toFixed(3).replace('.', ',')}`;
}
const fmtInt = (n: number) => n.toLocaleString('ru-RU');

function verdictClass(v: string): string {
  if (v.startsWith('подтверждена')) return 'pos';
  if (v.startsWith('не подтверждена')) return 'neg';
  return '';
}

export default function SeamView() {
  const t = useT();
  const be = useLang() === 'be';
  const p = (path: string) => (be ? '/be' + path : path);
  const [data, setData] = useState<SeamData | null>(null);
  const [failed, setFailed] = useState(false);
  const [missing, setMissing] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetch('/data/seam.json')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <p className="hint">{t('Не удалось загрузить данные исследования.')}</p>;
  if (!data) return <p className="hint">{t('Загрузка данных…')}</p>;

  const { meta, hypotheses: H, estimates } = data;
  const get = (o: string, s: string, spec = 'main') =>
    estimates.find((e) => e.outcome === o && e.seg === s && e.spec === spec);
  const isSig = (e?: Est) => !!e && e.tau != null && e.p != null && e.p < meta.alpha;
  const segName = (s: string) => t(meta.segments[s] ?? s);
  const segList = (xs: string[] | undefined) => (xs && xs.length ? xs.map(segName).join(', ') : '—');
  const tauOf = (o: string, s: string) => get(o, s)?.tau ?? null;

  // ---- итог расчёта по каждой гипотезе (числа — из seam.json)
  const h1 = H.H1, h2 = H.H2, h3 = H.H3, h4 = H.H4, h5 = H.H5;
  const did = Object.values(h1?.did ?? {});
  const cropPos = SEGS.filter((s) => {
    const e = get('C_0319', s);
    return isSig(e) && (e!.tau as number) > 0;
  });
  const results: Record<string, string> = {
    H1: `${t('значимых скачков:')} ${h1?.sig_segments?.length ?? 0} ${t('из 5')}; ${t('после 1991 года |τ| больше, чем до, — на')} ${did.filter((d) => d.raw).length} ${t('из')} ${did.length} ${t('бывших советских границ')}`,
    H2: `${t('значимо отрицательный скачок:')} ${segList(h2?.neg_segments)}; ${t('значимо положительный:')} ${segList(cropPos)}; ${segName('PL')}: ${h2?.pl_tau != null ? fmtNum(h2.pl_tau, 1) : '—'} ${t('п.п.')}`,
    H3: `${t('значимо отрицательных скачков:')} ${h3?.neg_segments?.length ?? 0} ${t('из 5')}` +
      (h3?.neg_segments_built_only
        ? `; ${t('при контроле только застройкой —')} ${h3.neg_segments_built_only.length} ${t('из 5')}`
        : ''),
    H4: h4?.ua?.tau != null
      ? `τ = ${fmtNum(h4.ua.tau, 2)} (${h4.ua.p != null ? fmtP(h4.ua.p) : '—'})`
      : '—',
  };
  const hypKeys = ['H1', 'H2', 'H3', 'H4'];
  if (h5 && h5.verdict !== 'нет данных') {
    const checks = Object.values(h5.checks ?? {});
    const comp = data.units?.comparison ?? {};
    const med = ['LT', 'LV', 'RU', 'PL', 'UA']
      .filter((s) => comp[s]?.nb_median != null && comp[s]?.by_median != null)
      .map((s) => `${segName(s)} ${fmtNum(comp[s].nb_median as number, 2)} / ${fmtNum(comp[s].by_median as number, 2)}`)
      .join('; ');
    results.H5 = `${t('выполнено условий:')} ${checks.filter((c) => c === true).length} ${t('из')} ${checks.filter((c) => c !== null).length}` +
      (med ? `; ${t('медиана темпа, %/год, сосед / Беларусь:')} ${med}` : '');
    hypKeys.push('H5');
  }

  const hasTwins = Array.isArray(data.units?.twins) && data.units!.twins!.length > 0;
  const gallery = GALLERY.filter((g) => (g.file !== 'twins' || hasTwins) && !missing[g.file]);
  const bSig = SEGS.filter((s) => isSig(get('B_9015', s))).length;
  const cLT = tauOf('C_0319', 'LT'), cLV = tauOf('C_0319', 'LV'), cRU = tauOf('C_0319', 'RU');
  const lUA = tauOf('L_1924', 'UA');

  return (
    <div>
      <div className="controls" style={{ marginBottom: 6 }}>
        <MethodDrawer slug="seam" />
        <a className="btn" href={`/artifacts/${ZIP}`} download>
          ⬇ {t('Проверяемый пакет (ZIP)')}
        </a>
        <Link className="btn" href={p('/artifacts/seam')}>{t('Пакет: версии и состав')}</Link>
        <Link className="btn" href={p('/article/seam')}>{t('Читать статью')}</Link>
      </div>

      <div className="stat-row">
        <div className="stat-tile">
          <div className="st-label">{t('Квадратов 1 км в полосе ±50 км')}</div>
          <div className="st-value">{fmtInt(meta.cells_total)}</div>
          <div className="st-delta">{t('пять границ: Польша, Литва, Латвия, Россия, Украина')}</div>
        </div>
        {cLT != null && (
          <div className="stat-tile">
            <div className="st-label">{t('Шов в полях: пашня 2003→2019, Литва')}</div>
            <div className="st-value">{fmtNum(cLT, 1)} {t('п.п.')}</div>
            <div className="st-delta">
              {t('сосед минус Беларусь у самой линии;')}{' '}
              {cLV != null && `${segName('LV')} ${fmtNum(cLV, 1)}`}
              {cRU != null && `, ${segName('RU')} ${fmtNum(cRU, 1)}`}
            </div>
          </div>
        )}
        <div className="stat-tile">
          <div className="st-label">{t('Шов в застройке 1990→2015')}</div>
          <div className="st-value">{bSig} {t('из 5')}</div>
          <div className="st-delta">{t('границ со значимым скачком роста застройки WSF')}</div>
        </div>
        {lUA != null && (
          <div className="stat-tile">
            <div className="st-label">{t('Огни 2019→2024, украинский участок')}</div>
            <div className="st-value">{fmtNum(lUA, 2)}</div>
            <div className="st-delta">{t('лог. пункта: война и закрытая граница, не экономика')}</div>
          </div>
        )}
      </div>

      <h2>{t('Гипотезы, записанные до расчёта')}</h2>
      <div className="zone-table-wrap">
        <table className="zone-table seam-table">
          <thead>
            <tr>
              <th>{t('Гипотеза')}</th>
              <th>{t('Формулировка (до расчёта)')}</th>
              <th>{t('Вердикт')}</th>
              <th>{t('Итог расчёта')}</th>
            </tr>
          </thead>
          <tbody>
            {hypKeys.map((k) => (
              <tr key={k}>
                <td><strong>{k}</strong></td>
                <td className="seam-wrap">{t(HYP_TEXT[k])}</td>
                <td className={verdictClass(H[k].verdict)}><strong>{t(H[k].verdict)}</strong></td>
                <td className="seam-wrap">{results[k]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>{t('Главные оценки: скачок у самой линии')}</h2>
      <div className="zone-table-wrap">
        <table className="zone-table seam-table">
          <thead>
            <tr>
              <th>{t('Исход')}</th>
              {SEGS.map((s) => <th key={s}>{segName(s)}</th>)}
            </tr>
          </thead>
          <tbody>
            {MAIN_OUTCOMES.map((o) => (
              <tr key={o}>
                <td className="seam-wrap">{t(meta.outcomes[o]?.label ?? o)}</td>
                {SEGS.map((s) => {
                  const e = get(o, s);
                  if (!e || e.tau == null) return <td key={s}>—</td>;
                  const d = PP_OUTCOMES.has(o) ? 1 : 3;
                  const v = fmtNum(e.tau, d);
                  const tip = [
                    e.p != null ? fmtP(e.p) : '',
                    e.n_by != null && e.n_nb != null ? `n = ${fmtInt(e.n_by)} / ${fmtInt(e.n_nb)}` : '',
                    e.clusters != null ? `${t('кластеров')}: ${e.clusters}` : '',
                  ].filter(Boolean).join(' · ');
                  return (
                    <td key={s} title={tip}>
                      {isSig(e) ? <strong>{v}</strong> : v}{' '}
                      <span className="hint">({fmtNum(e.se ?? 0, d, false)})</span>
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr>
              <td className="seam-wrap hint">{t('Ячеек в полосе ±52 км: Беларусь / сосед')}</td>
              {SEGS.map((s) => {
                const c = meta.cells_by_segment[s];
                return <td key={s} className="hint">{c ? `${fmtInt(c.by)} / ${fmtInt(c.nb)}` : '—'}</td>;
              })}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="hint" style={{ marginTop: 8 }}>
        {t('τ — сосед минус Беларусь у самой линии; жирным — значимо при p < 0,05, в скобках — ошибка, кластеризованная по блокам 25×25 км. Основная спецификация по пререгистрации: окно h = 25 км, треугольное ядро, без 2-километровой полосы у линии, городских ядер (5 км от городов от 50 тыс. жителей) и Чернобыльской зоны (35 км); исключение факелов двух НПЗ (2,5 км) добавлено при расчёте. Проверки устойчивости по пререгистрации — окна 15 и 50 км, равномерное ядро; дополнительно — выборка без исключений (с городами и Чернобыльской зоной) и проверки, добавленные после фиксации (подучастки 1°×1°, ложные границы ±30 км, исключение 10 км для DMSP, контроль только застройкой). Все 660 оценок — в estimates.csv пакета.')}
      </p>

      <h2>{t('Иллюстрации')}</h2>
      <div className="seam-gallery">
        {gallery.map((g) => (
          <figure key={g.file}>
            <a href={`/content/img/seam/${g.file}.webp`} target="_blank" rel="noopener noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/content/img/seam/${g.file}.webp`}
                alt={t(g.caption)}
                loading="lazy"
                onError={() => setMissing((m) => ({ ...m, [g.file]: true }))}
              />
            </a>
            <figcaption>{t(g.caption)}</figcaption>
          </figure>
        ))}
      </div>

      <div className="gv-next" role="note" style={{ marginTop: 16 }}>
        <strong>{t('Смежные материалы.')}</strong>{' '}
        {t('Статья «Шов на карте: что видно на границах Беларуси из космоса» — то же исследование простым языком;')}{' '}
        <Link href={p('/article/seam')}>{t('открыть')}</Link>.{' '}
        {t('Проверяемый пакет: таблица ячеек, код расчёта на стандартном Python и все проверки устойчивости;')}{' '}
        <Link href={p('/artifacts/seam')}>{t('открыть')}</Link>.{' '}
        {t('«Беларусь из космоса» (INF-08) — ночные огни внутри страны; проверка H3 не нашла систематического «пересвета» белорусской стороны;')}{' '}
        <Link href={p('/research/nightlights')}>{t('открыть')}</Link>.
      </div>

      <p className="src-note">
        {t('τ на государственной границе — суммарный эффект всего, чем различаются страны (институты, политика, цены, правила статистики), а не эффект конкретной меры. Застройка WSF и GHSL по построению только растёт: снос и заброшенность не измеряются. GHS-POP — только контроль: его входные единицы несопоставимы (Беларусь — 129 районов, Польша — около 2 500 гмин). Украина после 2022 года — война: падение огней не трактуется как экономика.')}
      </p>
      <p className="src-note">
        {t('Данные: WSF Evolution (DLR), GHSL R2023A BUILT-S и POP (Объединённый исследовательский центр Еврокомиссии), гармонизированный ряд ночных огней Li et al. v10 (Figshare), VIIRS VNL v2.1 (зеркало на Zenodo), пашня GLAD (Potapov et al., 2022), города GeoNames, границы соседей geoBoundaries. Полные оговорки — в методблоке и в LIMITATIONS.md пакета.')}
      </p>
    </div>
  );
}
