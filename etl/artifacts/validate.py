"""Валидатор проверяемого пакета (ARTIFACT_STANDARD.md §9).

Проверяет: схему манифеста, соответствие файлов и контрольных сумм,
обязательный состав, непустые LIMITATIONS.md/AGENT.md, а затем выполняет
полный прогон `run.sh` в чистой временной директории и сверяет
воспроизведённые результаты с checks/expected_results.json в допусках.

Запуск:  python -m etl.artifacts.validate <zip>|--all [--no-run]
Код выхода 0 - пакет валиден.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from ..common import ROOT
from .build import REQUIRED, ARTIFACTS_OUT

MANIFEST_REQUIRED_FIELDS = [
    "schema_version", "id", "title", "version", "released", "git_tag",
    "landing_url", "authors", "files", "sources", "entrypoints",
    "environment", "expected_results", "limitations_file", "agent_instructions",
]

# машиночитаемая схема: etl/artifacts/schema/manifest.schema.json
FILE_ROLES = {"raw", "intermediate", "final", "code", "params", "docs", "checks"}
SEMVER_RE = r"^\d+\.\d+\.\d+$"


class ValidationError(Exception):
    pass


def _fail(msg: str) -> None:
    raise ValidationError(msg)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_manifest_schema(m: dict) -> None:
    import re
    for field in MANIFEST_REQUIRED_FIELDS:
        if field not in m:
            _fail(f"manifest.json: нет обязательного поля '{field}'")
    if m["schema_version"] != "1.0":
        _fail(f"manifest.json: неизвестная schema_version {m['schema_version']}")
    if not re.fullmatch(SEMVER_RE, m["version"]):
        _fail(f"manifest.json: version '{m['version']}' не semver")
    if m["git_tag"] != f"artifact-{m['id']}-v{m['version']}":
        _fail(f"manifest.json: git_tag '{m['git_tag']}' не соответствует id/version")
    if not m["expected_results"]:
        _fail("manifest.json: expected_results пуст")
    for er in m["expected_results"]:
        for k in ("metric", "value", "tolerance", "description"):
            if k not in er:
                _fail(f"expected_results: у метрики нет поля '{k}': {er}")
    for f in m["files"]:
        for k in ("path", "sha256", "role"):
            if k not in f:
                _fail(f"files[]: нет поля '{k}': {f}")
        if f["role"] not in FILE_ROLES:
            _fail(f"files[]: недопустимая роль '{f['role']}' у {f['path']}")
    for s in m["sources"]:
        for k in ("id", "url", "accessed"):
            if k not in s:
                _fail(f"sources[]: нет поля '{k}': {s}")


def validate_tree(root: Path) -> dict:
    """Структурные проверки распакованного пакета. Возвращает манифест."""
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        _fail("нет manifest.json")
    m = json.loads(manifest_path.read_text())
    validate_manifest_schema(m)

    missing = [r for r in REQUIRED if not (root / r).is_file()]
    if missing:
        _fail(f"отсутствуют обязательные файлы: {missing}")

    for name in ("LIMITATIONS.md", "AGENT.md"):
        if len((root / name).read_text().strip()) < 200:
            _fail(f"{name} пустой или формальный (<200 символов)")

    # 1) файлы манифеста существуют и суммы сходятся
    listed = set()
    for f in m["files"]:
        p = root / f["path"]
        if not p.is_file():
            _fail(f"manifest.files: файла нет в пакете: {f['path']}")
        actual = _sha256(p)
        if actual != f["sha256"]:
            _fail(f"sha256 не совпадает: {f['path']}: манифест {f['sha256'][:12]}…, "
                  f"фактически {actual[:12]}…")
        listed.add(f["path"])
    # 2) в пакете нет файлов, не описанных в манифесте
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if rel not in listed and rel not in ("manifest.json", "checks/checksums.sha256"):
                _fail(f"файл в пакете не описан в манифесте: {rel}")
    # 3) checksums.sha256 согласован
    for line in (root / "checks" / "checksums.sha256").read_text().splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(None, 1)
        p = root / rel.strip()
        if not p.is_file():
            _fail(f"checksums.sha256: файла нет: {rel}")
        if _sha256(p) != digest:
            _fail(f"checksums.sha256: сумма не совпадает: {rel}")
    return m


def run_reproduction(root: Path, m: dict) -> None:
    """Полный прогон run.sh + сверка с expected_results в допусках."""
    run = root / m["entrypoints"]["reproduce"]
    proc = subprocess.run(["bash", str(run)], cwd=root, capture_output=True,
                          text=True, timeout=600)
    if proc.returncode != 0:
        _fail(f"run.sh завершился с ошибкой:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")

    computed_path = root / "data" / "final" / "computed_results.json"
    if not computed_path.is_file():
        _fail("после прогона нет data/final/computed_results.json")
    computed = {r["metric"]: r["value"] for r in json.loads(computed_path.read_text())}

    for er in m["expected_results"]:
        metric, expected, tol = er["metric"], er["value"], er["tolerance"]
        if metric not in computed:
            _fail(f"прогон не воспроизвёл метрику '{metric}'")
        got = computed[metric]
        if abs(got - expected) > tol:
            _fail(f"метрика '{metric}': воспроизведено {got}, заявлено {expected} "
                  f"(допуск ±{tol})")


def validate_zip(zip_path: Path, run: bool = True) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        entries = [p for p in Path(tmp).iterdir() if p.is_dir()]
        if len(entries) != 1:
            _fail("в корне архива должна быть ровно одна директория пакета")
        root = entries[0]
        m = validate_tree(root)
        expected_name = f"by-maps-{m['id']}-v{m['version']}.zip"
        if zip_path.name != expected_name:
            _fail(f"имя архива {zip_path.name} не соответствует манифесту ({expected_name})")
        if run:
            run_reproduction(root, m)
    print(f"OK: {zip_path.name} валиден" + ("" if run else " (без прогона)"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-run", action="store_true",
                    help="только структурные проверки, без прогона run.sh")
    args = ap.parse_args()
    targets = (sorted(ARTIFACTS_OUT.glob("by-maps-*.zip")) if args.all
               else [Path(args.zip)])
    if not targets or targets == [None]:
        ap.error("укажите путь к zip или --all")
    failed = False
    for t in targets:
        try:
            validate_zip(t, run=not args.no_run)
        except ValidationError as e:
            print(f"FAIL: {t.name}: {e}", file=sys.stderr)
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
