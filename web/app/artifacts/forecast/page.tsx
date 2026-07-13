import type { Metadata } from 'next';
import ForecastArtifactBody from '@/components/artifacts/ForecastArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет forecast — версии и состав',
  description: 'Проверяемый пакет прогноза населения Беларуси 2026–2075 (v2026.4, уровни 0–3, ряды official/adjusted, вероятностный веер).',
  alternates: { languages: { ru: '/artifacts/forecast', be: '/be/artifacts/forecast' } },
};

export default function ForecastArtifactPage() {
  return <ForecastArtifactBody />;
}
