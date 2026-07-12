#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-09 с заявленными (в допусках)."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def computed_metrics() -> dict:
    s = json.loads((PKG / "web" / "public" / "data" / "shocks.json").read_text())
    ser = s["series"]
    census = s["census1897"]
    pinsk = next(c["jewishShare"] for c in census if c["id"] == "c-pinsk")
    return {
        "n_events": len(s["events"]),
        "n_census": len(census),
        "n_holocaust": len(s["holocaust"]),
        "pop_1940": ser["1940"], "pop_1950": ser["1950"],
        "wwii_loss": ser["1940"] - ser["1950"],
        "top_share_1897": census[0]["jewishShare"],
        "pinsk_share_1897": pinsk,
    }


def main() -> None:
    computed = computed_metrics()
    final_dir = PKG / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "computed_results.json").write_text(json.dumps(
        [{"metric": k, "value": v} for k, v in sorted(computed.items())],
        ensure_ascii=False, indent=1))
    expected = json.loads((PKG / "checks" / "expected_results.json").read_text())
    failed = []
    for e in expected:
        got = computed.get(e["metric"])
        if got is None or abs(got - e["value"]) > e["tolerance"]:
            failed.append((e["metric"], e["value"], got))
    if failed:
        for m_, want, got in failed:
            print(f"РАСХОЖДЕНИЕ {m_}: заявлено {want}, получено {got}", file=sys.stderr)
        sys.exit(1)
    print(f"Все {len(expected)} контрольных метрик воспроизведены в допусках.")


if __name__ == "__main__":
    main()
