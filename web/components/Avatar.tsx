'use client';

import { useEffect, useState } from 'react';

/** Аватар автора. По умолчанию (SSR и первый клиентский рендер) — инициалы на
 *  медном фоне: краулеры и no-JS видят чистую подпись, а не битую картинку и
 *  без 404 в статическом HTML. Если фото /author.jpg реально загружается —
 *  подменяем на него после монтирования. */
export default function Avatar({
  size = 96,
  src = '/author.jpg',
  initials = 'СА',
  alt = 'Сергей Авдейчик',
}: {
  size?: number;
  src?: string;
  initials?: string;
  alt?: string;
}) {
  const [photoOk, setPhotoOk] = useState(false);
  useEffect(() => {
    if (!src) return;
    const img = new Image();
    img.onload = () => setPhotoOk(true);
    img.src = src;
  }, [src]);

  if (photoOk) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img className="avatar" src={src} alt={alt} width={size} height={size} />
    );
  }
  return (
    <div
      className="avatar avatar-initials"
      style={{ width: size, height: size, fontSize: Math.round(size * 0.4) }}
      role="img"
      aria-label={alt}
    >
      {initials}
    </div>
  );
}
