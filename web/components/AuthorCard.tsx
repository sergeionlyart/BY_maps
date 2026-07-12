import Link from 'next/link';
import Avatar from '@/components/Avatar';

/** Переиспользуемая карточка автора / бренд-CTA (релиз 1.2, B-1/B-5).
 *  Серверный компонент: текст попадает в статический HTML. Медный акцент. */

const MAIL = 'chatwebmarket@gmail.com';
const mailto = (subject: string) => `mailto:${MAIL}?subject=${encodeURIComponent(subject)}`;

type Lang = 'ru' | 'be';
type Variant = 'full' | 'compact' | 'callout';

const T: Record<Lang, {
  name: string; role: string; authorHref: string;
  about: string; write: string;
  compactBlurb: string; fullCta: string;
  calloutTitle: string; calloutText: string; calloutCta: string;
  subjWrite: string; subjPipeline: string;
}> = {
  ru: {
    name: 'Сергей Авдейчик',
    role: 'к.т.н., AI/ML-инженер',
    authorHref: '/author',
    about: 'Об авторе →',
    write: 'Написать',
    compactBlurb: 'Проект сделан связкой OSINT + LLM-агенты + проверяемые артефакты.',
    fullCta: 'Понравился подход? Я помогаю командам и специалистам строить такие же конвейеры: LLM-агенты, RAG, автоматизация аналитики и профессиональных процессов. Пишите — обсудим вашу задачу, или приходите на менторинг.',
    calloutTitle: 'Как это сделано',
    calloutText: 'Весь конвейер проекта — ETL, модели, тесты, пакеты — построен с LLM-агентами. Хотите такой же для ваших данных?',
    calloutCta: 'Обсудить →',
    subjWrite: 'BY Maps',
    subjPipeline: 'BY Maps → LLM-конвейер',
  },
  be: {
    name: 'Сяргей Аўдзейчык',
    role: 'к.т.н., AI/ML-інжынер',
    authorHref: '/be/author',
    about: 'Пра аўтара →',
    write: 'Напісаць',
    compactBlurb: 'Праект зроблены звязкай OSINT + LLM-агенты + правяральныя артэфакты.',
    fullCta: 'Спадабаўся падыход? Я дапамагаю камандам і спецыялістам будаваць такія ж канвееры: LLM-агенты, RAG, аўтаматызацыя аналітыкі і прафесійных працэсаў. Пішыце — абмяркуем вашу задачу, або прыходзьце на ментарынг.',
    calloutTitle: 'Як гэта зроблена',
    calloutText: 'Увесь канвеер праекта — ETL, мадэлі, тэсты, пакеты — пабудаваны з LLM-агентамі. Хочаце такі ж для вашых даных?',
    calloutCta: 'Абмеркаваць →',
    subjWrite: 'BY Maps',
    // subject — канонический (RU) для единой классификации лидов, как в AuthorLanding
    subjPipeline: 'BY Maps → LLM-конвейер',
  },
};

export default function AuthorCard({ variant = 'compact', lang = 'ru' }: { variant?: Variant; lang?: Lang }) {
  const t = T[lang];

  if (variant === 'callout') {
    return (
      <aside className="author-card author-callout" aria-label={t.calloutTitle}>
        <div className="ac-body">
          <div className="ac-callout-title">{t.calloutTitle}</div>
          <p className="ac-callout-text">{t.calloutText}</p>
          <a className="btn primary ac-btn" href={mailto(t.subjPipeline)}>{t.calloutCta}</a>
        </div>
      </aside>
    );
  }

  if (variant === 'full') {
    return (
      <aside className="author-card author-full" aria-label={t.name}>
        <Avatar size={72} />
        <div className="ac-body">
          <div className="ac-name">{t.name}</div>
          <div className="ac-role">{t.role}</div>
          <p className="ac-cta">{t.fullCta}</p>
          <div className="ac-actions">
            <Link className="btn primary ac-btn" href={t.authorHref}>{t.about}</Link>
            <a className="btn ac-btn" href={mailto(t.subjWrite)}>{t.write}</a>
          </div>
        </div>
      </aside>
    );
  }

  // compact
  return (
    <aside className="author-card author-compact" aria-label={t.name}>
      <Avatar size={48} />
      <div className="ac-body">
        <p className="ac-line">
          <strong>{t.name}</strong> — {t.role}. {t.compactBlurb}
        </p>
        <div className="ac-actions">
          <Link className="btn ac-btn" href={t.authorHref}>{t.about}</Link>
          <a className="btn ac-btn" href={mailto(t.subjWrite)}>{t.write}</a>
        </div>
      </div>
    </aside>
  );
}
