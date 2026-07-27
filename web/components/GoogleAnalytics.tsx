'use client';

import Script from 'next/script';
import { useEffect, useState } from 'react';

// Do not load analytics until the visitor opts in; advertising storage is unused.
const MEASUREMENT_ID = 'G-D27077RPNV';
const CONSENT_KEY = 'by-maps-analytics-consent';

type Consent = 'granted' | 'denied' | null;

export default function GoogleAnalytics() {
  const [consent, setConsent] = useState<Consent>(null);

  useEffect(() => {
    const savedConsent = window.localStorage.getItem(CONSENT_KEY);
    if (savedConsent === 'granted' || savedConsent === 'denied') {
      setConsent(savedConsent);
    }
  }, []);

  const chooseConsent = (value: Exclude<Consent, null>) => {
    window.localStorage.setItem(CONSENT_KEY, value);
    setConsent(value);
  };

  return (
    <>
      {consent === 'granted' && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}`}
            strategy="afterInteractive"
          />
          <Script id="google-analytics" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${MEASUREMENT_ID}');
            `}
          </Script>
        </>
      )}

      {consent === null && (
        <>
          <section className="analytics-consent" aria-label="Настройки аналитики">
            <p>
              Разрешить анонимную аналитику посещений? Она помогает улучшать карты и
              исследования. Рекламные инструменты не используются.
            </p>
            <div className="analytics-consent-actions">
              <button type="button" onClick={() => chooseConsent('denied')}>
                Отклонить
              </button>
              <button
                type="button"
                className="primary"
                onClick={() => chooseConsent('granted')}
              >
                Разрешить
              </button>
            </div>
          </section>
          <style jsx>{`
            .analytics-consent {
              position: fixed;
              left: max(16px, env(safe-area-inset-left));
              right: max(16px, env(safe-area-inset-right));
              bottom: max(16px, env(safe-area-inset-bottom));
              z-index: 100;
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 18px;
              max-width: 760px;
              margin: 0 auto;
              padding: 14px 16px;
              color: var(--ink);
              background: color-mix(in srgb, var(--surface-1) 96%, transparent);
              border: 1px solid var(--border);
              border-radius: 14px;
              box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
              backdrop-filter: blur(12px);
            }

            p {
              margin: 0;
              font-size: 14px;
              line-height: 1.45;
            }

            .analytics-consent-actions {
              display: flex;
              flex: 0 0 auto;
              gap: 8px;
            }

            button {
              min-height: 40px;
              padding: 8px 13px;
              border: 1px solid var(--border);
              border-radius: 9px;
              background: var(--surface-1);
              color: var(--ink);
              cursor: pointer;
            }

            button.primary {
              border-color: transparent;
              background: var(--accent);
              color: #fff;
            }

            @media (max-width: 640px) {
              .analytics-consent {
                align-items: stretch;
                flex-direction: column;
                gap: 12px;
              }

              .analytics-consent-actions {
                justify-content: flex-end;
              }
            }
          `}</style>
        </>
      )}
    </>
  );
}
