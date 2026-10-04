"""Каталог опубликованных пакетов из ФАКТИЧЕСКИХ архивов.

Перегенерирует web/public/artifacts/catalog.json и checksums.txt по
web/public/artifacts/by-maps-*.zip: размер и sha256 считаются от файлов,
последняя версия каждого пакета идёт в `packages`, остальные — в
`archive_versions`. Описательные поля пакета (code, title_ru, research_url)
берутся из текущего catalog.json, а для пакетов, которых там нет, — из
реестра исследований web/lib/research.ts.

Раньше каталог правили вручную и он отставал от архивов (не было grid,
pension); запускайте после каждой сборки нового пакета или версии.

Запуск:  python -m etl.artifacts.catalog [--date YYYY-MM-DD] [--check]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys

from ..common import ROOT
from .build import ARTIFACTS_OUT

CATALOG = ARTIFACTS_OUT / "catalog.json"
CHECKSUMS = ARTIFACTS_OUT / "checksums.txt"
RESEARCH_TS = ROOT / "web" / "lib" / "research.ts"
ZIP_RE = re.compile(r"^by-maps-(?P<slug>[a-z][a-z-]*[a-z])-v(?P<ver>\d+\.\d+\.\d+)\.zip$")


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _research_meta() -> dict[str, dict]:
    """slug пакета -> {code, title_ru, research_url} из web/lib/research.ts."""
    src = RESEARCH_TS.read_text(encoding="utf-8")
    out = {}
    for block in re.findall(r"\{[^{}]*?slug:\s*'[^']+'[^{}]*?(?:\{[^{}]*\}[^{}]*)?\}", src, re.S):
        slug = re.search(r"slug:\s*'([^']+)'", block).group(1)
        code = re.search(r"code:\s*'([^']+)'", block)
        title = re.search(r"title:\s*'([^']+)'", block)
        pkg = re.search(r"artifactSlug:\s*'([^']+)'", block)
        out[pkg.group(1) if pkg else slug] = {
            "code": code.group(1) if code else slug,
            "title_ru": title.group(1) if title else slug,
            "research_path": f"/research/{slug}",
        }
    return out


def _ver_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def build_catalog(date: str) -> tuple[dict, str]:
    old = json.loads(CATALOG.read_text(encoding="utf-8"))
    base = old["base_url"]
    known = {}
    for p in old.get("packages", []):
        m = ZIP_RE.match(p["file"])
        if m:
            known[m["slug"]] = {k: p[k] for k in ("code", "title_ru", "research_url") if k in p}
    research = _research_meta()

    by_slug: dict[str, list[tuple[str, str]]] = {}
    for z in sorted(ARTIFACTS_OUT.glob("by-maps-*.zip")):
        m = ZIP_RE.match(z.name)
        if not m:
            raise SystemExit(f"неожиданное имя архива: {z.name}")
        by_slug.setdefault(m["slug"], []).append((m["ver"], z.name))

    def entry(name: str, ver: str) -> dict:
        path = ARTIFACTS_OUT / name
        return {"file": name, "url": f"{base}/artifacts/{name}", "size_bytes": path.stat().st_size,
                "sha256": _sha256(path), "version": ver}

    packages, archive = [], []
    for slug, vers in by_slug.items():
        vers.sort(key=lambda x: _ver_key(x[0]))
        latest_ver, latest_name = vers[-1]
        e = entry(latest_name, latest_ver)
        if slug in known:
            e.update(known[slug])
        elif slug in research:
            r = research[slug]
            e.update({"code": r["code"], "title_ru": r["title_ru"], "research_url": base + r["research_path"]})
        else:
            raise SystemExit(f"{slug}: нет описания ни в catalog.json, ни в web/lib/research.ts")
        packages.append(e)
        archive += [entry(n, v) for v, n in vers[:-1]]
    packages.sort(key=lambda e: e["file"])
    archive.sort(key=lambda e: e["file"])

    cat = {
        "project": old["project"],
        "generated": date,
        "base_url": base,
        "note": old["note"],
        "site_data": old["site_data"],
        "packages": packages,
        "archive_versions": archive,
        "repository": old["repository"],
    }
    lines = [f"{e['sha256']}  {e['file']}" for e in sorted(packages + archive, key=lambda e: e["file"])]
    return cat, "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="поле generated (YYYY-MM-DD)")
    ap.add_argument("--check", action="store_true",
                    help="не писать, а проверить, что catalog.json/checksums.txt соответствуют архивам")
    a = ap.parse_args()
    cat, sums = build_catalog(a.date)
    if a.check:
        old = json.loads(CATALOG.read_text(encoding="utf-8"))
        bad = []
        if CHECKSUMS.read_text(encoding="utf-8") != sums:
            bad.append("checksums.txt")
        for k in ("packages", "archive_versions"):
            if old.get(k) != cat[k]:
                bad.append(f"catalog.json:{k}")
        if bad:
            sys.exit(f"каталог не соответствует архивам: {', '.join(bad)} - "
                     f"перегенерируйте: python -m etl.artifacts.catalog")
        print(f"OK --check: каталог соответствует {len(sums.splitlines())} архивам")
        return
    # без завершающего перевода строки - как в исторической версии файла
    CATALOG.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    CHECKSUMS.write_text(sums, encoding="utf-8")
    print(f"OK: {len(cat['packages'])} пакетов, {len(cat['archive_versions'])} архивных версий, "
          f"{len(sums.splitlines())} строк в checksums.txt")


if __name__ == "__main__":
    main()
