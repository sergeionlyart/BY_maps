'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useLang, useT } from '@/lib/i18n';
import MethodDrawer from '@/components/MethodDrawer';
import CityFootprint from '@/components/urban/CityFootprint';
import OverhangScatter from '@/components/urban/OverhangScatter';
import OverhangClock from '@/components/urban/OverhangClock';
import CoreEdgePanel from '@/components/urban/CoreEdgePanel';
import RoadsNow from '@/components/urban/RoadsNow';
import ConfidenceMap from '@/components/urban/ConfidenceMap';
import PairsBlock from '@/components/urban/PairsBlock';
import { fmtNum, ratePct, Story } from '@/components/urban/types';

/** INF-12 «Цена пустеющей карты»: лонгрид с интерактивами.
 *  Данные: /data/urban_overhang.json (story) + /data/urban/city_<id>.json
 *  (сетки, лениво). Состояние выбранного города/года кодируется в URL. */
export default function UrbanOverhangView() {
  const t = useT();
  const lang = useLang();
  const [story, setStory] = useState<Story | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch('/data/urban_overhang.json')
      .then((r) => r.json())
      .then((s: Story) => {
        if (!alive) return;
        setStory(s);
        const url = new URL(window.location.href);
        const q = url.searchParams.get('city');
        if (q && s.cities[q]) setSelected(q);
        else {
          const ne = s.cases.find((c) => c.role === 'northeast');
          setSelected(ne?.city_id ?? 'c-minsk');
        }
      })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  // deep-link: запись ВЫБРАННОГО ГОРОДА (?city=) с дебаунсом (ловушка
  // history.replaceState); год/слой героя в URL не кодируются
  useEffect(() => {
    if (!selected) return;
    const id = window.setTimeout(() => {
      try {
        const url = new URL(window.location.href);
        url.searchParams.set('city', selected);
        window.history.replaceState(null, '', url.toString());
      } catch { /* лимит браузера на replaceState - пропускаем тик */ }
    }, 350);
    return () => window.clearTimeout(id);
  }, [selected]);

  const nat = story?.national;
  const counter = useMemo(
    () => story?.cases.find((c) => c.role === 'counterexample'),
    [story],
  );

  if (!story || !nat) return <p className="hint">{t('Загрузка данных…')}</p>;

  const cityName = (id: string) =>
    lang === 'be' ? story.cities[id]?.be || story.cities[id]?.ru : story.cities[id]?.ru;

  return (
    <div className="urban-view">
      {/* ------- ключевые числа ------- */}
      <div className="stat-row" role="list">
        <div className="stat-tile" role="listitem">
          <div className="st-label">{t('городов класса A/B в панели 1990–2020')}</div>
          <div className="st-value">{nat.n_cities}</div>
        </div>
        <div className="stat-tile" role="listitem">
          <div className="st-label">{t('сокращались по населению в 1990–2020')}</div>
          <div className="st-value">{nat.n_declining}</div>
        </div>
        <div className="stat-tile" role="listitem">
          <div className="st-label">{t('из них — с устойчиво положительным навесом')}</div>
          <div className="st-value">{nat.n_overhang_robust}</div>
        </div>
        <div className="stat-tile" role="listitem">
          <div className="st-label">{t('медианных м² застройки на жителя, 1990 → 2020')}</div>
          <div className="st-value">
            {fmtNum(nat.median_bpc_1990, 0)}&nbsp;→&nbsp;{fmtNum(nat.median_bpc_2020, 0)}
          </div>
        </div>
      </div>

      <section>
        <h2 id="sled">{t('Физический след города')}</h2>
        <p>
          <span className="chip-tag chip-data">{t('данные')}</span>{' '}
          {t('Спутниковый продукт GHS-BUILT-S фиксирует накопленную застроенную поверхность каждые 5 лет с 1975 по 2020 год в ячейках 100×100 м. Выберите город и посмотрите, как рос его физический след — и что в это время происходило с населением. Промежуточные кадры анимации интерполированы; расчёты выполняются только по опорным годам.')}
        </p>
        <CityFootprint
          story={story}
          selected={selected ?? 'c-minsk'}
          onSelect={setSelected}
        />
      </section>

      <section>
        <h2 id="scatter">{t('Люди и физический город: 92 траектории')}</h2>
        <p>
          <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
          {t('Каждая точка — город: по горизонтали изменение населения 1990–2020, по вертикали — изменение накопленной застройки в сопоставимой рамке (объединение контуров всех эпох + 1 км). Диагональ — «фонд растёт в темп населения». Всё, что выше диагонали, — рост фонда на жителя; правый нижний квадрант (физическое сжатие) продукт измерить не может по построению — застройка в нём почти не убывает.')}
        </p>
        <OverhangScatter story={story} selected={selected} onSelect={setSelected} />
      </section>

      <section>
        <h2 id="clock">{t('Часы материального навеса')}</h2>
        <p>
          <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
          {t('Индексы к 1990 году (=100): население, накопленный фонд и фонд на жителя. Числитель и знаменатель показаны отдельно, чтобы рост «на жителя» не маскировал свой механизм: в большинстве сокращающихся городов фонд продолжал расти, пока население убывало.')}
        </p>
        <OverhangClock story={story} selected={selected} onSelect={setSelected} />
      </section>

      <section>
        <h2 id="core-edge">{t('Ядро и край: куда смещается активность')}</h2>
        <p>
          <span className="chip-tag chip-model">{t('модель')}</span>{' '}
          {t('Ядро — контур города 1975 года; край — всё, что вошло в фонд позже. Ночная светимость VIIRS (2012–2024) на единицу застройки — прокси интенсивности использования: в части городов она смещается из исторического ядра к периферии. Свет не показывает численность людей; энергоэффективность и промышленные источники вносят свой вклад.')}
        </p>
        <CoreEdgePanel story={story} selected={selected} onSelect={setSelected} />
      </section>

      <section>
        <h2 id="roads">{t('Инфраструктура сегодня: дороги и сервисы на оставшихся')}</h2>
        <p>
          <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
          {t('Современный срез OpenStreetMap (снимок июля 2026): километры улично-дорожной сети и точки сервисов на тысячу текущих жителей. Это не история строительства — только сегодняшняя география, поделённая на сегодняшнее население. Полнота OSM неоднородна; отсутствие точки на карте не означает отсутствия сервиса.')}
        </p>
        <RoadsNow story={story} selected={selected} onSelect={setSelected} />
      </section>

      <section>
        <h2 id="pairs">{t('Сопоставленные пары: сокращающийся город и его двойник')}</h2>
        <p>
          <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
          {t('Каждому сокращающемуся городу подобран максимально похожий на него в 1990 году стабильный или растущий (размер, фонд на жителя, плотность, удалённость от Минска; калипер по размеру). При сходных стартовых характеристиках города пошли по разным траекториям — сравнение описательное, о причинах оно не говорит.')}
        </p>
        <PairsBlock story={story} />
      </section>

      <section>
        <h2 id="confidence">{t('Карта типов и уверенности')}</h2>
        <p>
          <span className="chip-tag chip-calc">{t('расчёт')}</span>{' '}
          {t('Каждому городу присвоен тип траектории по прозрачным правилам — и класс качества данных. Тип публикуется только если он устойчив к границам, порогам застройки и временному согласованию; неустойчивые случаи честно помечены как TX. Города класса C не участвуют в рейтингах.')}
        </p>
        <ConfidenceMap story={story} selected={selected} onSelect={setSelected} />
      </section>

      <section>
        <h2 id="counterexample">{t('Где гипотеза не сработала')}</h2>
        {counter && !counter.strict ? (
          <p>
            {t('Строгого контрпримера — сокращающегося города, где фонд на жителя не растёт, — в выборке не нашлось: у всех сокращающихся городов панели A/B материальный навес устойчиво положителен. Это само по себе результат: накопление фонда в Беларуси 1990–2020 не разворачивалось вспять нигде. Ближайший к нулю случай — ')}
            <b>{cityName(counter.city_id)}</b>
            {t(': минимальный навес среди сокращающихся (см. карточку города выше). Важная оговорка: спутниковый ряд по построению почти не умеет убывать, поэтому «отрицательный навес» мог бы возникнуть только за счёт роста населения.')}
          </p>
        ) : counter ? (
          <p>
            {t('Контрпример: ')}<b>{cityName(counter.city_id)}</b>
            {t(' — население сокращается, но устойчивого роста фонда на жителя нет.')}
          </p>
        ) : null}
      </section>

      <section>
        <h2 id="limits">{t('Что это исследование не утверждает')}</h2>
        <ul className="limit-list">
          <li>{t('Не измеряет денежную стоимость: «цена» — метафора удельной нагрузки. Бюджеты, тарифы и расходы на содержание сетей в MVP не подключены.')}</li>
          <li>{t('Не измеряет снос и физическое сжатие: исторический GHSL построен как накопительный ряд.')}</li>
          <li>{t('Не датирует строительство по OSM: дорожно-сервисный срез — только современный.')}</li>
          <li>{t('Не читает ночной свет как численность населения: это прокси интенсивности использования со своими искажениями.')}</li>
          <li>{t('Не делает причинных выводов: пары городов описывают расхождение траекторий, а не его причину.')}</li>
        </ul>
        <p className="hint">
          {t('Полный список ограничений, допущений и способов их проверить — в пакете артефактов.')}{' '}
          <Link href={lang === 'be' ? '/be/artifacts/urban-overhang' : '/artifacts/urban-overhang'}>
            {t('Скачать данные и код')}
          </Link>
        </p>
      </section>

      <p className="hint attribution">
        {t('Источники: GHS-BUILT-S R2023A (Европейская комиссия, JRC, CC BY 4.0); ряды населения BY Maps (переписи и оценки Белстата, компиляция pop-stat.mashke.org); ночные огни DMSP/VIIRS (вырезки INF-08); © OpenStreetMap contributors (ODbL). Эпохи GHSL 2025/2030 — модельные, в исследовании не используются.')}
      </p>

      <MethodDrawer slug="urban-overhang" />
    </div>
  );
}
