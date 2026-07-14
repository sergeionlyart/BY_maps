#!/usr/bin/env python3
"""Сверка воспроизведённых результатов INF-08 v2 с заявленными."""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG))


def computed_metrics() -> dict:
    from etl import nightlights_harmonize as H
    from etl import nightlights_model as M

    v = H.validation()
    n = json.loads((PKG / "web" / "public" / "data"
                    / "nightlights_v2.json").read_text())
    rows = {r["id"]: r for r in n["rows"]}
    assump = M.load_assumptions()
    cross = M.estimate_beta_cross(assump)
    fl = M.load_floor()
    fs = sum(x["floor"] for x in fl.values())
    bs = sum(x["bright"] for x in fl.values())
    manifest = json.loads((PKG / "web/public/data/nightlights"
                           / "nightlights_manifest.json").read_text())
    events = json.loads((PKG / "web/public/data/nightlights"
                         / "nightlights_events.json").read_text())
    return {
        "n_zones": len(n["rows"]),
        "n_frames_manifest": len(manifest["frames"]),
        "n_events_total": len(events["events"]),
        "n_events_regional": sum(1 for e in events["events"]
                                 if e["kind"] == "regional_change"),
        "bridge_r2": round(v["bridge"]["r2"], 4),
        "bridge_b": round(v["bridge"]["b"], 4),
        "f18_factor": round(v["f18"], 4),
        "seam_gap": round(v["seam_gap"], 4),
        "nat_light_1992": n["natLight"]["1992"],
        "nat_light_2024": n["natLight"]["2024"],
        "div_minsk": rows["BY-HM"]["div"],
        "div_smalavicki": rows["r-smalavicki"]["div"],
        "lr_smalavicki": rows["r-smalavicki"]["lightRatio"],
        "div_salihorski": rows["r-salihorski"]["div"],
        "beta_industrial": round(cross["industrial"]["beta"], 4),
        "beta_rural": round(cross["rural"]["beta"], 4),
        "floor_share_2024": round(fs / (fs + bs), 4),
        "model_2075_base": n["natModel"]["official"]["base"]["2075"],
        "model_2075_negative": n["natModel"]["official"]["negative"]["2075"],
        "model_2075_optimistic":
            n["natModel"]["official"]["optimistic"]["2075"],
    }


def main() -> None:
    computed = computed_metrics()
    final_dir = PKG / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "computed_results.json").write_text(json.dumps(
        [{"metric": k, "value": v} for k, v in sorted(computed.items())],
        ensure_ascii=False, indent=1))
    expected = json.loads(
        (PKG / "checks" / "expected_results.json").read_text())

    failed = []
    for e in expected:
        got = computed.get(e["metric"])
        if got is None or abs(got - e["value"]) > e["tolerance"]:
            failed.append((e["metric"], e["value"], got))
    if failed:
        for m_, want, got in failed:
            print(f"РАСХОЖДЕНИЕ {m_}: заявлено {want}, получено {got}",
                  file=sys.stderr)
        sys.exit(1)
    print(f"Все {len(expected)} контрольных метрик воспроизведены "
          f"в допусках.")


if __name__ == "__main__":
    main()
