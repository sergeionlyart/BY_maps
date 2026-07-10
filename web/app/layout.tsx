import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Население Беларуси, 1897–2026',
  description:
    'Интерактивная карта изменения численности и плотности населения Беларуси за 120 лет: страна, области, районы и города. Переписи 1897–2019 и текущие оценки.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
