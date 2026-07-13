/** Встраивает JSON-LD (schema.org) в статический HTML. Серверный компонент —
 *  скрипт попадает в пререндер без выполнения JS на клиенте. */
export default function JsonLd({ data }: { data: object | object[] }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
