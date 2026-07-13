import type { Metadata } from 'next';
import MigrationView from '@/components/MigrationView';
import ResearchShell from '@/components/ResearchShell';
import { authors } from '@/lib/seo';

export const metadata: Metadata = {
  authors,
  title: 'Унутраная і знешняя міграцыя — Насельніцтва Беларусі',
  description:
    'Міграцыйная лесвіца вёска → райцэнтр → аблцэнтр → Мінск за 1959–2026, сальда раёнаў, міжабласныя патокі перапісу-2019 і знешняя хваля 2020+ у інтэрвальных ацэнках люстранай статыстыкі.',
  alternates: { languages: { ru: '/research/migration', be: '/be/research/migration' } },
};

export default function MigrationPage() {
  return (
    <ResearchShell
      code="INF-05"
      version="v1.0.0"
      title="Миграция: лестница длиной в полвека и волна 2020+"
      lead="Полвека внутренняя миграция Беларуси работала как лестница: село отдавало людей райцентрам, райцентры — облцентрам и Минску; село с 1959 года сжалось с 5,5 до 1,9 млн, Минск вырос вчетверо. С 2020 года у лестницы появилась новая вершина — зарубеж: официальная статистика показывает миграционный прирост, но действующие ВНЖ граждан РБ в одном только ЕС выросли со 134 до 387 тысяч, а интервальные оценки незарегистрированного оттока — от 100 до 600 тысяч человек. Данные о миграции за 2020–2023 годы Белстат не публиковал вовсе."
    >
      <MigrationView />
    </ResearchShell>
  );
}
