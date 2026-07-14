#!/usr/bin/env python3
"""Сверка воспроизведённых кандидатов H1-H3 с заявленными (в допусках).

Пишет data/final/computed_results.json и сравнивает каждую метрику
с checks/expected_results.json.
"""
import json
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent

CAUSAL_RU = ["из-за", "вызвано", "вызвал", "привело", "привела",
             "потому что", "по причине", "доказывает, что",
             "объясняется тем"]


def computed_metrics() -> dict:
    nl = PKG / "web" / "public" / "data" / "nightlights"
    cands = json.loads(
        (nl / "research_candidates.json").read_text())["candidates"]
    decomp = json.loads(
        (nl / "divergence_decomposition.json").read_text())
    out = {
        "candidates_total": len(cands),
        "release_approved_all": int(all(c["releaseApproved"]
                                        for c in cands)),
        "decomposition_zones": len(decomp["rows"]),
        "causal_wording_violations": sum(
            1 for c in cands for w in CAUSAL_RU
            if w in json.dumps(c, ensure_ascii=False).lower()),
    }
    for c in cands:
        out[f"residual_pct_{c['id']}"] = c["metrics"]["lightResidualPct"]
        out[f"alt_residual_pct_{c['id']}"] = c["metrics"]["altResidualPct"]
        out[f"beta_{c['id']}"] = c["metrics"]["betaUsed"]

    ext = json.loads((nl / "external_checks.json").read_text())
    def find(cid, metric, zone):
        case = next(c for c in ext["cases"] if c["caseId"] == cid)
        return next(ch for ch in case["checks"]
                    if ch["metric"] == metric and ch["zone"] == zone)
    out["ext_checks_total"] = sum(len(c["checks"]) for c in ext["cases"])
    out["ext_ipi_zhodino"] = find(
        "smolevichi-zhodino", "industrial_production_index",
        "c-zhodzina")["value"]
    out["ext_ipi_smalavicki"] = find(
        "smolevichi-zhodino", "industrial_production_index",
        "r-smalavicki")["value"]
    out["ext_ipi_astravets"] = find(
        "astravets", "industrial_production_index",
        "r-astraviecki")["value"]
    out["ext_empl_astravets"] = find(
        "astravets", "employment", "r-astraviecki")["value"]
    out["ext_elec_verdict_context"] = int(find(
        "astravets", "electricity_production_oblast",
        "BY-HR")["verdict"] == "context")
    return out


def main() -> None:
    computed = computed_metrics()
    final_dir = PKG / "data" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "computed_results.json").write_text(json.dumps(
        [{"metric": k, "value": v} for k, v in sorted(computed.items())],
        ensure_ascii=False, indent=1))
    expected = json.loads(
        (PKG / "checks" / "expected_results.json").read_text())
    failures = []
    for er in expected:
        got = computed.get(er["metric"])
        if got is None:
            failures.append(f"{er['metric']}: не вычислена")
        elif abs(got - er["value"]) > er["tolerance"]:
            failures.append(
                f"{er['metric']}: {got} != {er['value']} "
                f"(допуск {er['tolerance']})")
    if failures:
        print("РАСХОЖДЕНИЯ:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"OK: {len(expected)} метрик совпадают с заявленными.")


if __name__ == "__main__":
    main()
