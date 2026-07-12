import type { Metadata, Viewport } from 'next';
import SiteNav from '@/components/SiteNav';
import Footer from '@/components/Footer';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://by-population-maps.vercel.app'),
  title: 'Население Беларуси, 1897–2026',
  description:
    'Интерактивная карта изменения численности и плотности населения Беларуси за 120 лет: страна, области, районы и города. Переписи 1897–2019 и текущие оценки.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <SiteNav />
        {children}
        <Footer />
      </body>
    </html>
  );
}
