"""Сборка проверяемого пакета артефактов из декларативного описания.

Источник истины - artifacts/<slug>/artifact.yaml: файлы с ролями, источники,
точки входа, окружение, ожидаемые результаты. Сборщик копирует файлы,
считает sha256, генерирует manifest.json и checksums.sha256 и упаковывает
ДЕТЕРМИНИРОВАННЫЙ zip (фиксированные mtime и порядок файлов): повторная
сборка из того же коммита даёт байт-в-байт тот же архив - это проверяется
в CI (--check).

Запуск:  python -m etl.artifacts.build <slug> [--check] | --all [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import yaml

from ..common import ROOT

ARTIFACTS_SRC = ROOT / "artifacts"
ARTIFACTS_OUT = ROOT / "web" / "public" / "artifacts"

# фиксированная метка времени внутри zip - для воспроизводимости побайтно
ZIP_DATE = (2026, 1, 1, 0, 0, 0)

# обязательный состав пакета (ARTIFACT_STANDARD.md §3 must + §8 CHANGELOG;
# data/final представлен файлом контрольных метрик)
REQUIRED = [
    "README.md", "manifest.json", "AGENT.md", "LIMITATIONS.md", "LICENSE.md",
    "CHANGELOG.md", "sources/registry.csv", "code/run.sh",
    "code/requirements.lock", "data/final/computed_results.json",
    "checks/expected_results.json", "checks/checksums.sha256",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_spec(slug: str) -> dict:
    spec_path = ARTIFACTS_SRC / slug / "artifact.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    assert spec["id"] == slug, f"id в {spec_path} не совпадает со слагом"
    return spec


def stage(slug: str, spec: dict, dest: Path) -> None:
    """Собирает дерево пакета в dest."""
    src_dir = ARTIFACTS_SRC / slug
    for f in spec["files"]:
        src = ROOT / f["from"] if "from" in f else src_dir / f["path"]
        target = dest / f["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            raise FileNotFoundError(f"{slug}: нет исходного файла {src}")
        shutil.copy2(src, target)

    # checks/expected_results.json - из спеки (единый источник истины)
    er = dest / "checks" / "expected_results.json"
    er.parent.mkdir(parents=True, exist_ok=True)
    er.write_text(json.dumps(spec["expected_results"], ensure_ascii=False, indent=2))

    # manifest.json
    files_meta = []
    for p in sorted(x for x in dest.rglob("*") if x.is_file()):
        rel = p.relative_to(dest).as_posix()
        role = next((f.get("role", "docs") for f in spec["files"] if f["path"] == rel),
                    "checks" if rel.startswith("checks/") else "docs")
        entry = {"path": rel, "sha256": sha256_file(p), "role": role}
        lic = next((f.get("license") for f in spec["files"] if f["path"] == rel), None)
        if lic:
            entry["license"] = lic
        files_meta.append(entry)

    manifest = {
        "schema_version": "1.0",
        "id": spec["id"],
        "title": spec["title"],
        "version": spec["version"],
        "released": spec["released"],
        "git_tag": f"artifact-{spec['id']}-v{spec['version']}",
        "landing_url": spec["landing_url"],
        "authors": spec["authors"],
        "files": files_meta,
        "sources": spec["sources"],
        "entrypoints": spec["entrypoints"],
        "environment": spec["environment"],
        "expected_results": spec["expected_results"],
        "limitations_file": "LIMITATIONS.md",
        "agent_instructions": "AGENT.md",
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))

    # checksums.sha256 - все файлы, кроме самого себя
    lines = []
    for p in sorted(x for x in dest.rglob("*") if x.is_file()):
        rel = p.relative_to(dest).as_posix()
        if rel == "checks/checksums.sha256":
            continue
        lines.append(f"{sha256_file(p)}  {rel}")
    (dest / "checks" / "checksums.sha256").write_text("\n".join(lines) + "\n")

    missing = [r for r in REQUIRED if not (dest / r).is_file()]
    if missing:
        raise FileNotFoundError(f"{slug}: обязательные файлы отсутствуют: {missing}")


def make_zip(dest: Path, slug: str, version: str) -> bytes:
    """Детерминированный zip: сортированные пути, фиксированный mtime."""
    root_name = f"by-maps-{slug}-v{version}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(x for x in dest.rglob("*") if x.is_file()):
            rel = p.relative_to(dest).as_posix()
            info = zipfile.ZipInfo(f"{root_name}/{rel}", date_time=ZIP_DATE)
            info.external_attr = (0o755 if rel.endswith(".sh") else 0o644) << 16
            zf.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                        compresslevel=9)
    return buf.getvalue()


def build(slug: str, check: bool = False) -> Path:
    spec = load_spec(slug)
    zip_name = f"by-maps-{slug}-v{spec['version']}.zip"
    out_path = ARTIFACTS_OUT / zip_name
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "pkg"
        dest.mkdir()
        stage(slug, spec, dest)
        data = make_zip(dest, slug, spec["version"])
    if check:
        if not out_path.exists():
            raise SystemExit(f"{zip_name}: опубликованного архива нет, а --check запрошен")
        if sha256_file(out_path) != hashlib.sha256(data).hexdigest():
            raise SystemExit(
                f"{zip_name}: пересборка не воспроизводит опубликованный архив. "
                f"Изменились данные/код/параметры - поднимите версию пакета "
                f"(ARTIFACT_STANDARD.md §8: опубликованная версия неизменяема).")
        print(f"OK --check: {zip_name} воспроизводится байт-в-байт")
    else:
        ARTIFACTS_OUT.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        print(f"OK: {out_path.relative_to(ROOT)} ({len(data) // 1024} КБ, "
              f"sha256 {hashlib.sha256(data).hexdigest()[:16]}…)")
    return out_path


def all_slugs() -> list[str]:
    return sorted(p.parent.name for p in ARTIFACTS_SRC.glob("*/artifact.yaml"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="не публиковать, а сверить с опубликованным архивом")
    args = ap.parse_args()
    slugs = all_slugs() if args.all else [args.slug]
    if not slugs or slugs == [None]:
        ap.error("укажите slug или --all")
    for slug in slugs:
        build(slug, check=args.check)


if __name__ == "__main__":
    main()
