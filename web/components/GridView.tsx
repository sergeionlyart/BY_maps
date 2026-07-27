'use client';

/**
 * «Полотно» (INF-15): карта расселения Беларуси по сетке 1 км, 1975-2050,
 * без административных границ (тумблер - по умолчанию выключен).
 *
 * - дискретный ползунок по 16 узлам данных (наблюдаемые 1975-2020 с шагом 5
 *   + прогнозные 2026-2050 с шагом 5, вариант А по итогам аудита B-1,
 *   docs/decisions/INF-15.md) - визуально разделены штриховкой+подписью;
 * - переключатель метрики: люди в клетке / класс плотности / метры сети на
 *   жителя (снимок 2026 года - ползунок лет в этом режиме заблокирован);
 * - переключатели сценария (2026+) и варианта прогноза A/Б;
 * - кнопка ▶ - автовоспроизведение 16 узлов, ~700 мс/кадр, останов на 2050,
 *   пауза при любом действии пользователя, доступна и при reduced-motion
 *   (просто не стартует сама - тут она никогда не стартует сама);
 * - кнопка «центр масс населения» - трек с коридором погрешности (ширина
 *   полосы = собственный err_km точки), подписями ключевых лет, автозумом;
 * - плашка честности - видна без прокрутки, не только в подвале;
 * - клик по клетке - точная история клетки; клик по району в режиме сети -
 *   его показатель;
 * - легенда под картой, своя для каждого режима;
 * - deep-link ?year=&metric=&scenario=&variant=&borders=&track=, дебаунс
 *   350 мс (регресс INF-08/INF-11 - без дебаунса скраббинг ронял историю);
 *   год вне узлов данных - снап к ближайшему с краткой подписью (B-1).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useT, useLang } from '@/lib/i18n';
import MethodDrawer from './MethodDrawer';
import GridMap from './grid/GridMap';
import {
  useGridData, frameKey, loadCellGrid, cellHasBinary, lonLatToCellIndex,
  cellValue, fmtInt, fmtPct, ALL_YEARS, nearestYear, networkLegendStops,
  type Scenario, type Variant, type Metric,
} from '@/lib/grid';

const SCN_RU: Record<Scenario, string> = { base: 'базовый', optimistic: 'оптимистичный', negative: 'негативный' };
const METRIC_RU: Record<Metric, string> = {
  pop: 'Люди в клетке', density: 'Класс плотности', network: 'Метры сети на жителя',
};
const PLAY_FRAME_MS = 700;

const CLAIM_LABEL_RU: Record<string, string> = {
  'C-001': 'люди концентрируются быстрее, чем пустеет территория',
  'C-002': 'доля пустеющей территории растёт непрерывно с 1975 года',
  'C-003': 'дорожной сети на жителя больше там, где сильнее убыль',
};
const CLAIM_STATUS_RU: Record<string, string> = {
  open_question: 'Открытый вопрос', verified: 'Подтверждено',
};

interface FrameMeta {
  bounds_lonlat: [number, number, number, number];
  vmax: number;
  gamma: number;
  density_classes: { min: number; max: number | null; color: string; label: string }[];
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

export default function GridView() {
  const t = useT();
  const lang = useLang();
  const data = useGridData();
  const geoRef = useRef<{ adm1: GeoJSON.FeatureCollection; adm2: GeoJSON.FeatureCollection } | null>(null);
  const [geoLoaded, setGeoLoaded] = useState(false);
  const reducedMotion = useReducedMotion();

  const [idx, setIdx] = useState(ALL_YEARS.indexOf(2020));
  const year = ALL_YEARS[idx];
  const [metric, setMetric] = useState<Metric>('pop');
  const [scenario, setScenario] = useState<Scenario>('base');
  const [variant, setVariant] = useState<Variant>('A');
  const [showBorders, setShowBorders] = useState(false);
  const [showTrack, setShowTrack] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [cell, setCell] = useState<{ lon: number; lat: number; value: number | null; exact: boolean } | null>(null);
  const [territory, setTerritory] = useState<{ id: string; name: string; value: number | null } | null>(null);
  const [snapNotice, setSnapNotice] = useState<string | null>(null);
  const initDone = useRef(false);
  const territoryNames = useRef<Record<string, { ru: string; be: string }> | null>(null);

  useEffect(() => {
    Promise.all([
      fetch('/data/geo/adm1.geojson').then((r) => r.json()),
      fetch('/data/geo/adm2.geojson').then((r) => r.json()),
    ]).then(([adm1, adm2]) => { geoRef.current = { adm1, adm2 }; setGeoLoaded(true); });
  }, []);

  // режим «сеть» - имена районов подгружаются лениво, только когда
  // действительно понадобятся (клик по хороплету), чтобы не тянуть общий
  // справочник территорий (~400 КБ) ради режима, которым могут не пользоваться
  useEffect(() => {
    if (metric !== 'network' || territoryNames.current) return;
    fetch('/data/data.json').then((r) => r.json()).then((d) => {
      const m: Record<string, { ru: string; be: string }> = {};
      for (const [id, tr] of Object.entries(d.territories as Record<string, { ru: string; be: string }>)) {
        m[id] = { ru: tr.ru, be: tr.be };
      }
      territoryNames.current = m;
    });
  }, [metric]);

  // deep-link: чтение при монтировании
  useEffect(() => {
    if (!data || initDone.current) return;
    initDone.current = true;
    const p = new URLSearchParams(window.location.search);
    const yRaw = parseInt(p.get('year') ?? '', 10);
    if (Number.isFinite(yRaw)) {
      const snapped = nearestYear(yRaw);
      setIdx(ALL_YEARS.indexOf(snapped));
      if (snapped !== yRaw) {
        setSnapNotice(t('данные с шагом 5 лет — показан') + ` ${snapped}`);
      }
    }
    const m = p.get('metric');
    if (m === 'pop' || m === 'density' || m === 'network') setMetric(m);
    const s = p.get('scenario') as Scenario | null;
    if (s && ['base', 'optimistic', 'negative'].includes(s)) setScenario(s);
    const v = p.get('variant') as Variant | null;
    if (v === 'A' || v === 'B') setVariant(v);
    if (p.get('borders') === '1') setShowBorders(true);
    if (p.get('track') === '1') setShowTrack(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  // deep-link: запись, с дебаунсом 350 мс (обязательно - см. докстринг)
  useEffect(() => {
    if (!data) return;
    const id = window.setTimeout(() => {
      const url = new URL(window.location.href);
      url.searchParams.set('year', String(year));
      url.searchParams.set('metric', metric);
      if (year > 2020) {
        url.searchParams.set('scenario', scenario);
        url.searchParams.set('variant', variant);
      } else {
        url.searchParams.delete('scenario');
        url.searchParams.delete('variant');
      }
      if (showBorders) url.searchParams.set('borders', '1'); else url.searchParams.delete('borders');
      if (showTrack) url.searchParams.set('track', '1'); else url.searchParams.delete('track');
      try { window.history.replaceState(null, '', url); } catch { /* лимит истории - следующая запись догонит */ }
    }, 350);
    return () => window.clearTimeout(id);
  }, [data, year, metric, scenario, variant, showBorders, showTrack]);

  const isForecast = year > 2020;
  const key = data ? frameKey(year, scenario, variant) : null;
  const frameUrl = data && key && metric !== 'network'
    ? (data.frames[metric === 'density' ? 'density' : 'pop'][key] ?? null)
    : null;
  const [frameMeta, setFrameMeta] = useState<FrameMeta | null>(null);
  useEffect(() => {
    fetch('/data/grid_frames/meta.json').then((r) => r.json()).then((m) => setFrameMeta(m as FrameMeta));
  }, []);

  // автовоспроизведение: 16 узлов, ~700 мс/кадр, стоп на последнем узле
  useEffect(() => {
    if (!playing) return;
    const id = window.setTimeout(() => {
      if (idx + 1 >= ALL_YEARS.length) { setPlaying(false); return; }
      setIdx((i) => i + 1);
    }, PLAY_FRAME_MS);
    return () => window.clearTimeout(id);
  }, [playing, idx]);

  // префетч соседних кадров текущего показателя (нет смысла для «сети» -
  // там кадров нет вообще, один хороплет-снимок)
  useEffect(() => {
    if (!data || metric === 'network') return;
    for (let d = -2; d <= 3; d++) {
      const i = idx + d;
      if (i < 0 || i >= ALL_YEARS.length || i === idx) continue;
      const y = ALL_YEARS[i];
      const k = frameKey(y, scenario, variant);
      const url = data.frames[metric][k];
      if (url) new Image().src = url;
    }
  }, [data, idx, metric, scenario, variant]);

  const networkValues = useMemo(() => {
    if (!data) return null;
    const m: Record<string, number | null> = {};
    for (const [id, tv] of Object.entries(data.territories)) {
      m[id] = tv.network_per_capita?.road_km_per_1000 ?? null;
    }
    return m;
  }, [data]);

  function pauseUser() { setPlaying(false); }

  async function handleMapClick(lon: number, lat: number) {
    pauseUser();
    if (!data) return;
    setTerritory(null);
    setCell({ lon, lat, value: null, exact: false });
    const idx2 = lonLatToCellIndex(lon, lat, data.grid);
    if (!idx2) return;
    if (cellHasBinary(key ?? '')) {
      const arr = await loadCellGrid(key!);
      if (arr) {
        const v = cellValue(arr, idx2.row, idx2.col, data.grid);
        setCell({ lon, lat, value: v, exact: true });
        return;
      }
    }
    setCell({ lon, lat, value: null, exact: false });
  }

  function handleTerritoryClick(id: string) {
    pauseUser();
    if (!data) return;
    setCell(null);
    const names = territoryNames.current;
    const name = names?.[id]?.[lang] ?? names?.[id]?.ru ?? id;
    const value = data.territories[id]?.network_per_capita?.road_km_per_1000 ?? null;
    setTerritory({ id, name, value });
  }

  if (!data) {
    return <p className="hint" role="status">{t('Загрузка данных сетки…')}</p>;
  }

  const below5 = data.national.area_share_below['5'][key ?? String(year)];
  const below1 = data.national.area_share_below['1'][key ?? String(year)];
  const pwDensity = data.national.population_weighted_density[key ?? String(year)] ?? data.national.population_weighted_density[String(year)];
  const arithDensity = data.national.arithmetic_density[key ?? String(year)] ?? data.national.arithmetic_density[String(year)];
  const settlement = data.national.settlement_components[key ?? String(year)] ?? data.national.settlement_components[String(year)];
  const g3 = data.validation.g3_nightlights_crosscheck;
  const c3 = data.validation.c3_correlation;
  const g6 = data.validation.g6_network;
  const visibleTrack = data.national.centroid_track.filter((p) => p.year <= year);
  const lastTrackPt = visibleTrack[visibleTrack.length - 1];

  return (
    <div className="gv-root">
      <div className="gv-honesty" role="note">
        <strong>{t('Важно.')}</strong>{' '}
        {t('Карта построена дазиметрически из официальной статистики (GHS-POP), а не измерена независимо — она достоверно показывает рисунок расселения, но не является независимой проверкой численности населения.')}
        {' '}
        {t('Проверка по независимому сенсору (ночные огни) не подтвердила совпадение направления изменений — выводы о концентрации населения и росте пустеющей территории публикуются как открытый вопрос.')}
      </div>

      <div className="gv-chips" aria-label={t('Статус утверждений')}>
        {data.meta.claims.map((cid) => {
          const status = data.meta.claims_status[cid];
          return (
            <span key={cid} className={`gv-chip gv-chip-${status}`}>
              <strong>{t(CLAIM_STATUS_RU[status] ?? status)}</strong> — {t(CLAIM_LABEL_RU[cid] ?? cid)}
            </span>
          );
        })}
      </div>

      <div className="gv-howto">
        <div className="gv-howto-title">{t('Как читать эту карту')}</div>
        <p><strong>{t('1. Цвет')}</strong> — {t('сколько людей живёт в квадрате один на один километр. Чем ярче, тем плотнее. Шкала обрезана сверху: иначе Минск засветил бы всё остальное.')}</p>
        <p><strong>{t('2. Кнопка ▶')}</strong> — {t('карта пройдёт весь период (1975–2050) примерно за 11 секунд. Всё, что после 2020 года, — модель, помечена штриховкой и словом «МОДЕЛЬ».')}</p>
        <p><strong>{t('3. Клик по клетке')}</strong> — {t('сколько людей в этом квадрате в выбранном году. В режиме «метры сети на жителя» клик по району показывает его собственное число.')}</p>
      </div>

      <div className="gv-toolbar">
        <div className="gv-metric-switch" role="group" aria-label={t('Показатель')}>
          {(['pop', 'density', 'network'] as const).map((m) => (
            <button key={m} className={`btn${metric === m ? ' active' : ''}`}
              aria-pressed={metric === m} onClick={() => { pauseUser(); setMetric(m); }}>
              {t(METRIC_RU[m])}
            </button>
          ))}
        </div>
        <button className="play-btn gv-play" onClick={() => {
          if (!playing && idx >= ALL_YEARS.length - 1) setIdx(0);
          setPlaying((p) => !p);
        }} aria-label={playing ? t('пауза') : t('воспроизвести')}>
          {playing ? '❚❚' : '▶'}
        </button>
        <label className="gv-toggle">
          <input type="checkbox" checked={showBorders} onChange={(e) => { pauseUser(); setShowBorders(e.target.checked); }} />
          {t('Границы районов')}
        </label>
        <button className={`btn${showTrack ? ' active' : ''}`} aria-pressed={showTrack}
          onClick={() => { pauseUser(); setShowTrack((v) => !v); }}>
          {t('Центр масс населения')}
        </button>
        <MethodDrawer slug="grid" />
      </div>

      <GridMap
        frameUrl={frameUrl}
        boundsLonLat={frameMeta?.bounds_lonlat ?? null}
        metric={metric}
        networkValues={networkValues}
        reducedMotion={reducedMotion}
        showBorders={showBorders}
        showCentroidTrack={showTrack}
        centroidTrack={data.national.centroid_track}
        centroidUpToYear={year}
        onMapClick={handleMapClick}
        onTerritoryClick={handleTerritoryClick}
        adm1={geoLoaded ? geoRef.current!.adm1 : null}
        adm2={geoLoaded ? geoRef.current!.adm2 : null}
      />

      <div className="gv-legend" aria-label={t('Легенда')}>
        {metric === 'pop' && (
          <>
            <span className="gv-legend-title">{t('людей на км²:')}</span>
            {['0', '10', '100', '1000', '5000+'].map((v) => <span key={v} className="gv-legend-tick">{v}</span>)}
            <span className="hint gv-legend-note">{t('шкала нелинейная (γ = 0,92), верх обрезан на 5000 — иначе Минск засветил бы всю палитру')}</span>
          </>
        )}
        {metric === 'density' && frameMeta && (
          <>
            {frameMeta.density_classes.map((c) => (
              <span key={c.label} className="gv-legend-row">
                <span className="gv-legend-swatch" style={{ background: c.color }} />
                {t(c.label)} <span className="hint">({c.min}{c.max != null ? `–${c.max}` : '+'} {t('чел/км²')})</span>
              </span>
            ))}
          </>
        )}
        {metric === 'network' && (
          <>
            {networkLegendStops().map((s) => (
              <span key={s.label} className="gv-legend-row">
                <span className="gv-legend-swatch" style={{ background: s.color }} />
                {s.label} {t('км/1000 чел.')}
              </span>
            ))}
            <span className="hint gv-legend-note">{t('снимок OpenStreetMap на 2026 год, истории сети у нас нет')}</span>
          </>
        )}
      </div>

      <div className="gv-slider-zone">
        <input
          className="nlv3-range gv-range"
          type="range" min={0} max={ALL_YEARS.length - 1} step={1} value={idx}
          disabled={metric === 'network'}
          aria-label={t('Год')}
          onChange={(e) => { pauseUser(); setIdx(parseInt(e.target.value, 10)); }}
        />
        <div className="gv-slider-track">
          {ALL_YEARS.map((y) => (
            <span key={y} className={`gv-slider-node${y > 2020 ? ' model' : ''}`} style={{ left: `${(ALL_YEARS.indexOf(y) / (ALL_YEARS.length - 1)) * 100}%` }} title={String(y)} />
          ))}
          <div className="gv-slider-observed" style={{ width: `${(ALL_YEARS.indexOf(2020) / (ALL_YEARS.length - 1)) * 100}%` }} />
          <div className="gv-slider-model" style={{ width: `${100 - (ALL_YEARS.indexOf(2020) / (ALL_YEARS.length - 1)) * 100}%` }}>
            {t('модель')}
          </div>
        </div>
        <div className="gv-year-label">{year}{isForecast && <span className="urban-badge model">{t('МОДЕЛЬ')}</span>}</div>
        {metric === 'network' && (
          <p className="hint gv-network-note">{t('Дороги — снимок 2026 года, временной ползунок для этого показателя недоступен.')}</p>
        )}
        {snapNotice && <p className="hint gv-snap-notice" role="status">{snapNotice}</p>}
      </div>

      {isForecast && (
        <div className="gv-scn-switch">
          <div role="group" aria-label={t('Сценарий')}>
            {(['base', 'optimistic', 'negative'] as const).map((s) => (
              <button key={s} className={`btn${scenario === s ? ' active' : ''}`}
                aria-pressed={scenario === s} onClick={() => { pauseUser(); setScenario(s); }}>
                {t(SCN_RU[s])}
              </button>
            ))}
          </div>
          <div role="group" aria-label={t('Вариант прогноза')}>
            {(['A', 'B'] as const).map((v) => (
              <button key={v} className={`btn${variant === v ? ' active' : ''}`}
                aria-pressed={variant === v} onClick={() => { pauseUser(); setVariant(v); }}>
                {v === 'A' ? t('A — инерция') : t('Б — пригороды/периферия')}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="gv-panel">
        <div className="gv-stat">
          <div className="gv-stat-value">{below5 != null ? fmtPct(below5) : '—'}</div>
          <div className="hint">{t('страны, где живёт меньше 5 человек на км² — фактически пустая территория')}{below1 != null ? ` (${t('из них ниже 1')}: ${fmtPct(below1)})` : ''}</div>
        </div>
        <div className="gv-stat">
          <div className="gv-stat-value">{pwDensity != null ? fmtInt(pwDensity) : '—'}</div>
          <div className="hint">{t('плотность вокруг среднего жителя — насколько тесно живёт обычный человек')}</div>
        </div>
        <div className="gv-stat">
          <div className="gv-stat-value">{arithDensity != null ? arithDensity.toFixed(1) : '—'}</div>
          <div className="hint">{t('если поделить всех жителей на всю площадь страны')}</div>
        </div>
        <div className="gv-stat">
          <div className="gv-stat-value">{settlement ? fmtInt(settlement.n_components) : '—'}</div>
          <div className="hint">
            {t('отдельных «островов» расселения — связных пятен, где вообще живут люди')}
            {settlement ? ` — ${t('крупнейший')}: ${fmtPct(settlement.largest_share_of_pop)} ${t('населения на')} ${fmtPct(settlement.largest_share_of_area)} ${t('площади')}` : ''}
          </div>
        </div>
      </div>

      <div className="gv-finding" role="note">
        <strong>{t('Два разных ответа на вопрос «насколько плотно живёт Беларусь».')}</strong>
        <p>
          {t('Если поделить всех жителей на всю площадь страны, получится около')} 45 {t('человек на квадратный километр — и это число за 45 лет почти не изменилось (44,6 в 1975-м, 44,9 в 2020-м). Похоже, что ничего не происходит.')}
        </p>
        <p>
          {t('Но если спросить иначе — «а какая плотность вокруг обычного, среднего жителя?» — ответ за те же годы вырос почти вдвое: с 3 106 до 5 657 человек на квадратный километр. Средний житель Беларуси живёт заметно теснее, чем в 1975 году.')}
        </p>
        <p>
          {t('Противоречия здесь нет. Это два разных процесса, идущих одновременно: территория пустеет, а люди собираются вместе — и собираются быстрее, чем пустеет территория. Доля страны, где живёт меньше пяти человек на квадратный километр, выросла с 71,6% до 74,2%, а к 2050 году по базовому сценарию доходит до 84,9%. Крупнейший связный «остров» расселения в 2020 году вмещает 45,5% населения страны на 10,7% её площади.')}
        </p>
        <p className="hint">
          {t('Рост плотности вокруг среднего жителя к 2050 году (почти втрое от уровня 2020-го) — следствие модельной экстраполяции тренда, а не наблюдение; относитесь к этому числу как к сценарию, а не к факту.')}
        </p>
      </div>

      <div className="gv-g3-callout" role="note">
        <strong>{t('Что здесь не сходится.')}</strong>{' '}
        {t('В 63.9% районов официальная численность падает, а ночная светимость (независимый спутниковый сенсор) растёт — согласие направления изменений всего')} {g3.pct_agree}% {t('при пороге 70%. Вероятная причина — модернизация освещения (переход на LED) и рост инфраструктурной активности, не связанные с числом жителей; причина установлена не окончательно.')}
      </div>

      {c3?.supports_c3 && (
        <div className="gv-network-callout" role="note">
          <strong>{t('Дороги остаются, плательщики уезжают.')}</strong>{' '}
          {t('Чем сильнее район обезлюдел с 1989 года, тем больше километров дороги приходится на одного оставшегося жителя (коэффициент Спирмена')} {c3.spearman_rho.toFixed(2)}
          {t(', 118 районов, вероятность случайности исчезающе мала).')}
          {g6 && ` ${t('Снимок дорожной сети OpenStreetMap на 2026 год —')} ${fmtInt(g6.osm_total_km)} ${t('км против')} ${fmtInt(g6.official_total_km)} ${t('км официальной статистики (расхождение')} ${Math.abs(g6.delta_pct).toFixed(1)}%, ${t('в пределах допуска).')}`}
        </div>
      )}

      {cell && (
        <div className="gv-cell-card" role="status">
          <button className="gv-cell-close" onClick={() => setCell(null)} aria-label={t('закрыть')}>×</button>
          {cell.exact && cell.value != null ? (
            <p>{year}{isForecast ? ` (${t(SCN_RU[scenario])}, ${variant})` : ''} — <strong>{fmtInt(cell.value)}</strong> {t('человек в клетке 1×1 км')} <span className={`urban-badge${isForecast ? ' model' : ''}`}>{isForecast ? t('модель') : t('данные')}</span></p>
          ) : (
            <p className="hint">{t('Точное число для этой комбинации года/сценария не подгружено — показаны только национальные показатели выше.')}</p>
          )}
        </div>
      )}

      {territory && (
        <div className="gv-cell-card" role="status">
          <button className="gv-cell-close" onClick={() => setTerritory(null)} aria-label={t('закрыть')}>×</button>
          <p>
            <strong>{territory.name}</strong> — {territory.value != null ? (
              <>{territory.value.toFixed(1)} {t('км дороги на 1000 жителей')}</>
            ) : t('данных по сети нет')} <span className="urban-badge">{t('снимок 2026')}</span>
          </p>
        </div>
      )}

      {showTrack && lastTrackPt && (
        <p className="hint gv-track-caption">
          {t('За')} {lastTrackPt.year - visibleTrack[0].year} {t('лет центр тяжести населения сместился на несколько километров в сторону Минска — направление устойчивое, а величина для новейшего периода сопоставима с собственной погрешностью метода (±')}{lastTrackPt.err_km}{t(' км), поэтому мы не подаём её как точную. Узлы 1897 и 1970 построены другим методом (см. методблок) и обведены более широким коридором.')}
        </p>
      )}

      <div className="gv-next" role="note">
        <strong>{t('Смежные материалы.')}</strong>{' '}
        {t('«Цена пустеющей карты» (INF-12) — тот же процесс изнутри городов;')}{' '}
        <a href={lang === 'be' ? '/be/research/urban-overhang' : '/research/urban-overhang'}>{t('открыть')}</a>.{' '}
        {t('«Беларусь из космоса» (INF-08) — независимый спутниковый сенсор, который и обнаружил расхождение выше;')}{' '}
        <a href={lang === 'be' ? '/be/research/nightlights' : '/research/nightlights'}>{t('открыть')}</a>.
      </div>

      <div className="hint src-note">
        {t('Клетки населения — GHS-POP R2023A (Joint Research Centre, Еврокомиссия, CC BY 4.0), эпохи 1975–2020, приведены к официальным рядам Белстата по каждому району. Прогноз клеток 2026–2050 нормирован к районной модели проекта v2026.4. Дороги — снимок OpenStreetMap на 2026 год (классы motorway…tertiary), сверено с данными РУП «Белдорцентр». Ночные огни — VIIRS VNL v2.1 (исследование INF-08). Полные оговорки — в методблоке и в LIMITATIONS.md пакета артефактов.')}
      </div>

      <div className="hint gv-reduced-motion-note" aria-hidden={!reducedMotion}>
        {reducedMotion && t('Системная настройка «уменьшить движение» включена — автовоспроизведение ▶ по-прежнему запускается только вручную, плавный переход между кадрами отключён.')}
      </div>
    </div>
  );
}
