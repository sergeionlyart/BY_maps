/** Реестр исследований (TASK_SPEC.md, Р2). Публикация требует методблока
 *  и проверяемого пакета - гейт в CI. */

export interface ResearchEntry {
  slug: string;
  code: string;
  title: string;
  question: string;
  status: 'published' | 'planned';
  /** этап приоритетного плана (TASK_SPEC §6) */
  stage: number;
  /** slug пакета артефактов, если отличается от route-slug (напр. ml → mlchallenger) */
  artifactSlug?: string;
  artifact?: { file: string; version: string; sizeKb: number };
}

export const RESEARCH: ResearchEntry[] = [
  {
    slug: 'zipf',
    code: 'INF-01',
    title: 'Иерархия городов и закон Ципфа',
    question:
      'Как менялось соответствие городской системы закону Ципфа в 1897–2026 гг. и когда возникла макроцефалия Минска (сегодня — 4× Гомеля при «ципфовском» ожидании 2×)?',
    status: 'published',
    stage: 1,
    artifact: { file: 'by-maps-zipf-v1.0.0.zip', version: '1.0.0', sizeKb: 68 },
  },
  {
    slug: 'aging',
    code: 'INF-02',
    title: 'Старение районов',
    question:
      'Где и когда возрастная структура делает депопуляцию самоподдерживающейся — естественная убыль даже при нулевой миграции?',
    status: 'published',
    stage: 4,
    artifact: { file: 'by-maps-aging-v1.0.3.zip', version: '1.0.3', sizeKb: 712 },
  },
  {
    slug: 'wages',
    code: 'INF-03',
    title: 'Зарплата × динамика населения',
    question:
      'Следует ли население за деньгами: эластичность десятилетней динамики района по зарплатному дифференциалу к Минску и аномалии (моногорода, агрогородки)?',
    status: 'published',
    stage: 6,
    artifact: { file: 'by-maps-wages-v1.0.0.zip', version: '1.0.0', sizeKb: 136 },
  },
  {
    slug: 'access',
    code: 'INF-04',
    title: 'Транспортная доступность и «тень Минска»',
    question:
      'Пригород (<45 мин) растёт, кольцо 1,5–2,5 ч убывает быстрее всего? Как закрытие границ с ЕС изменило положение западных районов?',
    status: 'published',
    stage: 6,
    artifact: { file: 'by-maps-access-v1.0.0.zip', version: '1.0.0', sizeKb: 13950 },
  },
  {
    slug: 'migration',
    code: 'INF-05',
    title: 'Внутренняя и внешняя миграция',
    question:
      'Как устроена «лестница» село → райцентр → облцентр → Минск → зарубеж; каковы масштабы и география волны 2020+?',
    status: 'published',
    stage: 7,
    artifact: { file: 'by-maps-migration-v1.0.0.zip', version: '1.0.0', sizeKb: 2402 },
  },
  {
    slug: 'monotowns',
    code: 'INF-06',
    title: 'Моногорода и градообразующие предприятия',
    question:
      'Насколько траектория моногорода определяется состоянием градообразующего предприятия; кто в зоне риска при негативном сценарии?',
    status: 'published',
    stage: 8,
    artifact: { file: 'by-maps-monotowns-v1.0.0.zip', version: '1.0.0', sizeKb: 145 },
  },
  {
    slug: 'chernobyl',
    code: 'INF-07',
    title: 'Чернобыльский след',
    question:
      'Как отселение изменило траектории юго-восточных районов относительно демографически схожих незагрязнённых?',
    status: 'published',
    stage: 4,
    artifact: { file: 'by-maps-chernobyl-v1.0.0.zip', version: '1.0.0', sizeKb: 614 },
  },
  {
    slug: 'nightlights',
    code: 'INF-08',
    title: 'Беларусь из космоса, 1992–2075',
    question:
      'Что 33 года ночной светимости (DMSP + VIIRS) говорят о расхождении света и официального населения — и как выглядела бы карта света при трёх сценариях прогноза?',
    status: 'published',
    stage: 7,
    artifact: { file: 'by-maps-nightlights-v2.0.0.zip', version: '2.0.0', sizeKb: 4606 },
  },
  {
    slug: 'shocks',
    code: 'INF-09',
    title: 'Демографические шоки XX века',
    question:
      'Вклад Первой мировой, границы 1921–1939, репрессий, Второй мировой, Холокоста и «неперспективных деревень» в сегодняшнюю карту?',
    status: 'published',
    stage: 8,
    artifact: { file: 'by-maps-shocks-v1.0.0.zip', version: '1.0.0', sizeKb: 114 },
  },
  {
    slug: 'ml',
    code: 'ML',
    title: 'ML-challenger: слепые пятна структурной модели',
    question:
      'Где когортная модель районов (CCR/Гамильтон-Перри) систематически ошибается и по какому сигналу, которого она не видит? Градиентный бустинг на её ошибке 2019→2026 — как диагностика, не как конкурирующий прогноз.',
    status: 'published',
    stage: 8,
    artifactSlug: 'mlchallenger',
    artifact: { file: 'by-maps-mlchallenger-v1.0.0.zip', version: '1.0.0', sizeKb: 872 },
  },
];
