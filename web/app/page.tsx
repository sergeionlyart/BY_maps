'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import type { DataFile, Metric, MapLevel, RaionMode } from '@/lib/types';
import TimeBar from '@/components/TimeBar';
import TerritoryCard from '@/components/TerritoryCard';
import ComparePanel from '@/components/ComparePanel';
import UrbanPanel from '@/components/UrbanPanel';

const MapView = dynamic(() => import('@/components/MapView'), { ssr: false });

type Tab = 'territory' | 'compare' | 'urban';

interface GeoBundle {
  adm1: GeoJSON.FeatureCollection;
  adm2: GeoJSON.FeatureCollection;
  border1921: GeoJSON.FeatureCollection;
}

const BASE_YEARS = [1897, 1959, 1970, 1979, 1989, 1999, 2009, 2019];

export default function Page() {
  const [data, setData] = useState<DataFile | null>(null);
  const [geo, setGeo] = useState<GeoBundle | null>(null);
  const [year, setYear] = useState(2019);
  // стартовый вид - главный сюжет проекта: плотность сельской части районов
  // (без городских центров) + города точками поверх
  const [metric, setMetric] = useState<Metric>('density');
  const [level, setLevel] = useState<MapLevel>('raion');
  const [raionMode, setRaionMode] = useState<RaionMode>('noCenter');
  const [baseYear, setBaseYear] = useState(1989);
  const [showBorder, setShowBorder] = useState(false);
  const [showCities, setShowCities] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [compare, setCompare] = useState<string[]>([]);
  const [tab, setTab] = useState<Tab>('territory');

  useEffect(() => {
    Promise.all([
      fetch('data/data.json').then((r) => r.json()),
      fetch('data/geo/adm1.geojson').then((r) => r.json()),
      fetch('data/geo/adm2.geojson').then((r) => r.json()),
      fetch('data/geo/border1921.geojson').then((r) => r.json()),
    ]).then(([d, adm1, adm2, border1921]) => {
      setData(d);
      setGeo({ adm1, adm2, border1921 });
    });
  }, []);

  const select = (id: string | null) => {
    setSelected(id);
    if (id) setTab('territory');
  };

  const metricSafe: Metric = level === 'city' && metric === 'density' ? 'pop' : metric;

  const compareAdd = (id: string) =>
    setCompare((c) => (c.includes(id) || c.length >= 4 ? c : [...c, id]));

  const loaded = data && geo;

  return (
    <div className="app">
      <header className="app-header">
        <h1>Население Беларуси, 1897–2026</h1>
        <p>
          Численность, плотность и концентрация населения за 120 лет: страна,
          области, {`118`} районов и {`220+`} городов. Переписи 1897–2019, оценки до 2026.
        </p>
      </header>

      <div className="controls">
        <div className="control-group">
          <span className="control-label">Показатель</span>
          <div className="seg">
            <button className={metricSafe === 'pop' ? 'on' : ''} onClick={() => setMetric('pop')}>Численность</button>
            <button
              className={metricSafe === 'density' ? 'on' : ''}
              onClick={() => setMetric('density')}
              disabled={level === 'city'}
            >
              Плотность
            </button>
            <button className={metricSafe === 'change' ? 'on' : ''} onClick={() => setMetric('change')}>Изменение</button>
          </div>
        </div>

        <div className="control-group">
          <span className="control-label">Уровень</span>
          <div className="seg">
            <button className={level === 'oblast' ? 'on' : ''} onClick={() => setLevel('oblast')}>Области</button>
            <button className={level === 'raion' ? 'on' : ''} onClick={() => setLevel('raion')}>Районы</button>
            <button className={level === 'city' ? 'on' : ''} onClick={() => setLevel('city')}>Города</button>
          </div>
        </div>

        {level === 'raion' && (
          <div className="control-group">
            <div className="seg">
              <button className={raionMode === 'total' ? 'on' : ''} onClick={() => setRaionMode('total')}>Весь район</button>
              <button className={raionMode === 'noCenter' ? 'on' : ''} onClick={() => setRaionMode('noCenter')}>Без центра</button>
            </div>
          </div>
        )}

        {metricSafe === 'change' && (
          <div className="control-group">
            <span className="control-label">База</span>
            <select className="base-year" value={baseYear} onChange={(e) => setBaseYear(+e.target.value)}>
              {BASE_YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        )}

        {level !== 'city' && (
          <label className="toggle">
            <input type="checkbox" checked={showCities} onChange={(e) => setShowCities(e.target.checked)} />
            города точками
          </label>
        )}

        <label className="toggle">
          <input type="checkbox" checked={showBorder} onChange={(e) => setShowBorder(e.target.checked)} />
          граница 1921–1939
        </label>
      </div>

      <div className="main">
        {loaded ? (
          <MapView
            data={data}
            geo={geo}
            year={year}
            metric={metricSafe}
            level={level}
            raionMode={raionMode}
            baseYear={baseYear}
            showBorder1921={showBorder}
            showCities={showCities}
            selected={selected}
            onSelect={select}
          />
        ) : (
          <div className="map-wrap" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span className="hint">Загрузка данных…</span>
          </div>
        )}

        <aside className="side">
          <div className="side-tabs" role="tablist">
            <button className={tab === 'territory' ? 'on' : ''} onClick={() => setTab('territory')}>Территория</button>
            <button className={tab === 'compare' ? 'on' : ''} onClick={() => setTab('compare')}>
              Сравнение{compare.length ? ` (${compare.length})` : ''}
            </button>
            <button className={tab === 'urban' ? 'on' : ''} onClick={() => setTab('urban')}>Урбанизация</button>
          </div>
          <div className="side-body">
            {!loaded ? (
              <p className="hint">Загрузка…</p>
            ) : tab === 'territory' ? (
              <TerritoryCard
                data={data}
                id={selected}
                year={year}
                baseYear={baseYear}
                raionMode={raionMode}
                compare={compare}
                onCompareAdd={compareAdd}
                onSelect={select}
              />
            ) : tab === 'compare' ? (
              <ComparePanel
                data={data}
                compare={compare}
                onRemove={(id) => setCompare((c) => c.filter((x) => x !== id))}
              />
            ) : (
              <UrbanPanel data={data} year={year} />
            )}
          </div>
        </aside>
      </div>

      {data && (
        <TimeBar
          year={year}
          range={[data.yearRange[0], data.yearRange[1]]}
          censusYears={data.censusYears}
          onChange={setYear}
        />
      )}

      <footer className="footer">
        Исследовательский проект. Данные: переписи 1897–2019 и оценки Белстата
        (компиляция <a href="https://pop-stat.mashke.org/" target="_blank" rel="noreferrer">pop-stat.mashke.org</a>,{' '}
        <a href="http://www.demoscope.ru/weekly/ssp/census_types.php" target="_blank" rel="noreferrer">Демоскоп Weekly</a>),
        границы: <a href="https://www.geoboundaries.org/" target="_blank" rel="noreferrer">geoBoundaries</a> (CC BY),
        OSM (ODbL), координаты: Wikidata (CC0).{' '}
        <a href="https://github.com/sergeionlyart/BY_maps" target="_blank" rel="noreferrer">Методика и код</a>.
      </footer>
    </div>
  );
}
