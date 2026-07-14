"""Сцена 9: финал и CTA (62-65 c). QR читается >= 3 c (плюс оверлеп с
предыдущей сцены); обязательное раскрытие синтетического голоса."""
from render import W, H, INK, DIM, AMBER, font


def render(ctx, img, d, p, t):
    ui = ctx.ui.resize((W, int(ctx.ui.height * W / ctx.ui.width)))
    img.paste(ui.crop((0, 0, W, 980)), (0, 120))
    d.rectangle([0, 120, W - 1, 1100], outline=(70, 60, 48), width=2)
    ctx.center(d, "Где данные расходятся —", 1140, 56, fill=INK)
    ctx.center(d, "там начинается исследование", 1208, 56, fill=AMBER)
    ctx.center(d, "Выберите район · Сравните сценарии · Проверьте методику",
               1290, 38, fill=DIM)
    ctx.qr_block(img, d, size=300, y=1360)
    ctx.center(d, "Озвучка создана синтетическим голосом OpenAI",
               H - 90, 30, fill=DIM)
