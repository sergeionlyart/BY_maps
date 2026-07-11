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
    artifact: { file: 'by-maps-aging-v1.0.0.zip', version: '1.0.0', sizeKb: 710 },
  },
  {
    slug: 'wages',
    code: 'INF-03',
    title: 'Зарплата × динамика населения',
    question:
      'Следует ли население за деньгами: эластичность десятилетней динамики района по зарплатному дифференциалу к Минску и аномалии (моногорода, агрогородки)?',
    status: 'planned',
    stage: 6,
  },
  {
    slug: 'access',
    code: 'INF-04',
    title: 'Транспортная доступность и «тень Минска»',
    question:
      'Пригород (<45 мин) растёт, кольцо 1,5–2,5 ч убывает быстрее всего? Как закрытие границ с ЕС изменило положение западных районов?',
    status: 'planned',
    stage: 6,
  },
  {
    slug: 'migration',
    code: 'INF-05',
    title: 'Внутренняя и внешняя миграция',
    question:
      'Как устроена «лестница» село → райцентр → облцентр → Минск → зарубеж; каковы масштабы и география волны 2020+?',
    status: 'planned',
    stage: 7,
  },
  {
    slug: 'monotowns',
    code: 'INF-06',
    title: 'Моногорода и градообразующие предприятия',
    question:
      'Насколько траектория моногорода определяется состоянием градообразующего предприятия; кто в зоне риска при негативном сценарии?',
    status: 'planned',
    stage: 8,
  },
  {
    slug: 'chernobyl',
    code: 'INF-07',
    title: 'Чернобыльский след',
    question:
      'Как отселение изменило траектории юго-восточных районов относительно демографически схожих незагрязнённых?',
    status: 'published',
    stage: 4,
    artifact: { file: 'by-maps-chernobyl-v1.0.0.zip', version: '1.0.0', sizeKb: 613 },
  },
  {
    slug: 'nightlights',
    code: 'INF-08',
    title: 'Ночные огни против официальной статистики',
    question:
      'Где динамика ночной светимости (VIIRS) расходится с официальной динамикой населения — кандидаты на недоучтённый отток?',
    status: 'planned',
    stage: 7,
  },
  {
    slug: 'shocks',
    code: 'INF-09',
    title: 'Демографические шоки XX века',
    question:
      'Вклад Первой мировой, границы 1921–1939, репрессий, Второй мировой, Холокоста и «неперспективных деревень» в сегодняшнюю карту?',
    status: 'planned',
    stage: 8,
  },
];
