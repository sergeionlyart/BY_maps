import type { Metadata } from 'next';
import ForecastArtifactBody from '@/components/artifacts/ForecastArtifactBody';

export const metadata: Metadata = {
  title: 'Пакет forecast — версіі і склад',
  description: 'Правяральны пакет прагнозу насельніцтва Беларусі 2026–2075 (v2026.4, узроўні 0–3, шэрагі official/adjusted, імавернасны веер).',
  alternates: { languages: { ru: '/artifacts/forecast', be: '/be/artifacts/forecast' } },
};

export default function Page() {
  return <ForecastArtifactBody />;
}
