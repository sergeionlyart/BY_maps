import Avatar from '@/components/Avatar';

/** Посадочная шапка /author (релиз 1.2, B-3): хиро-карточка + контакты-кнопки
 *  + секция «Чем могу быть полезен». Серверный компонент. */

const MAIL = 'chatwebmarket@gmail.com';
const mailto = (subject: string) => `mailto:${MAIL}?subject=${encodeURIComponent(subject)}`;

type Lang = 'ru' | 'be';

const LINKS = {
  linkedin: 'https://www.linkedin.com/in/sergei-audzeichyk',
  github: 'https://github.com/sergeionlyart',
  medium: 'https://medium.com/@onlyartpl',
  facebook: 'https://www.facebook.com/share/1C5Ev1hwPw/?mibextid=wwXIfr',
};

const T: Record<Lang, {
  name: string; role: string;
  chips: string[];
  email: string;
  servicesTitle: string;
  services: { title: string; text: string; subject: string; cta: string }[];
}> = {
  ru: {
    name: 'Сергей Авдейчик',
    role: 'к.т.н., AI/ML-инженер, разработчик AI-продуктов',
    chips: ['LLM и агентные системы', 'RAG', 'LegalTech', 'EduTech', 'Computer Vision', 'Edge AI', 'Python'],
    email: 'Email',
    servicesTitle: 'Чем могу быть полезен',
    services: [
      {
        title: 'Менторинг',
        text: 'Вход в AI-инженерию и работу с LLM: персональный план, разбор ваших проектов, код-ревью, подготовка к собеседованиям.',
        subject: 'BY Maps → менторинг',
        cta: 'Написать про менторинг →',
      },
      {
        title: 'Разработка',
        text: 'AI-копилоты, RAG-системы, агентные конвейеры и автоматизация профессиональных процессов — от прототипа до продакшена.',
        subject: 'BY Maps → разработка',
        cta: 'Обсудить разработку →',
      },
      {
        title: 'Исследования и аналитика',
        text: 'Data-driven исследования под ключ по модели BY Maps: открытые источники, LLM-агенты, проверяемые артефакты.',
        subject: 'BY Maps → исследование',
        cta: 'Заказать исследование →',
      },
    ],
  },
  be: {
    name: 'Сяргей Аўдзейчык',
    role: 'к.т.н., AI/ML-інжынер, распрацоўшчык AI-прадуктаў',
    chips: ['LLM і агентныя сістэмы', 'RAG', 'LegalTech', 'EduTech', 'Computer Vision', 'Edge AI', 'Python'],
    email: 'Email',
    servicesTitle: 'Чым магу быць карысны',
    services: [
      {
        title: 'Ментарынг',
        text: 'Уваход у AI-інжынерыю і працу з LLM: персанальны план, разбор вашых праектаў, код-рэўю, падрыхтоўка да сумоўяў.',
        subject: 'BY Maps → менторинг',
        cta: 'Напісаць пра ментарынг →',
      },
      {
        title: 'Распрацоўка',
        text: 'AI-капілоты, RAG-сістэмы, агентныя канвееры і аўтаматызацыя прафесійных працэсаў — ад прататыпа да прадакшэна.',
        subject: 'BY Maps → разработка',
        cta: 'Абмеркаваць распрацоўку →',
      },
      {
        title: 'Даследаванні і аналітыка',
        text: 'Data-driven даследаванні пад ключ па мадэлі BY Maps: адкрытыя крыніцы, LLM-агенты, правяральныя артэфакты.',
        subject: 'BY Maps → исследование',
        cta: 'Замовіць даследаванне →',
      },
    ],
  },
};

export default function AuthorLanding({ lang = 'ru' }: { lang?: Lang }) {
  const t = T[lang];
  return (
    <>
      <section className="author-hero">
        <Avatar size={96} />
        <div className="ah-body">
          <h1 className="ah-name">{t.name}</h1>
          <div className="ah-role">{t.role}</div>
          <div className="ah-chips">
            {t.chips.map((c) => <span className="ah-chip" key={c}>{c}</span>)}
          </div>
          <div className="author-contacts">
            <a className="btn primary" href={mailto('BY Maps')}>{t.email}</a>
            <a className="btn" href={LINKS.linkedin} target="_blank" rel="noreferrer">LinkedIn</a>
            <a className="btn" href={LINKS.github} target="_blank" rel="noreferrer">GitHub</a>
            <a className="btn" href={LINKS.medium} target="_blank" rel="noreferrer">Medium</a>
            <a className="btn" href={LINKS.facebook} target="_blank" rel="noreferrer">Facebook</a>
          </div>
        </div>
      </section>

      <section className="author-services">
        <h2>{t.servicesTitle}</h2>
        <div className="cards">
          {t.services.map((s) => (
            <a className="card service-card" key={s.title} href={mailto(s.subject)}>
              <div className="card-title">{s.title}</div>
              <p>{s.text}</p>
              <div className="sc-cta">{s.cta}</div>
            </a>
          ))}
        </div>
      </section>
    </>
  );
}
