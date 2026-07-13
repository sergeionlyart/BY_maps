import type { Metadata, Viewport } from 'next';
import SiteNav from '@/components/SiteNav';
import Footer from '@/components/Footer';
import { LangProvider } from '@/lib/i18n';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://by-population-maps.vercel.app'),
  title: 'Население Беларуси, 1897–2026',
  description:
    'Интерактивная карта изменения численности и плотности населения Беларуси за 120 лет: страна, области, районы и города. Переписи 1897–2019 и текущие оценки.',
  openGraph: {
    type: 'website',
    siteName: 'BY Maps',
    locale: 'ru_RU',
    images: [{ url: '/og.png', width: 1200, height: 630 }],
  },
  twitter: { card: 'summary_large_image', images: ['/og.png'] },
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
        <LangProvider>
          <SiteNav />
          {children}
          <Footer />
        </LangProvider>
      </body>
    </html>
  );
}
