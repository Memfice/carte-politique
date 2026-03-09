#!/usr/bin/env python3
"""
Compute peer groups, benchmarks, and narrative flags for each commune.
Produces insights.json indexed by INSEE code.

Inputs: maires.json, surveillance.json, prospection.json, delinquance.json, enrichment.json
Output: insights.json
"""
import json
import math
import os
import sys


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    base = os.path.dirname(__file__) or "."
    print("Loading data files...", file=sys.stderr)
    maires = load_json(os.path.join(base, "maires.json"))
    surv = load_json(os.path.join(base, "surveillance.json"))
    prosp = load_json(os.path.join(base, "prospection.json"))
    delinq = load_json(os.path.join(base, "delinquance.json"))
    enrich = load_json(os.path.join(base, "enrichment.json"))

    all_codes = set(maires) | set(surv) | set(prosp) | set(delinq) | set(enrich)
    print(f"  {len(all_codes)} total commune codes", file=sys.stderr)

    # Step 1: Build feature vectors for peer matching
    vectors = {}
    pops = {}
    for code in all_codes:
        pop = 0
        if code in prosp and prosp[code].get("pop"):
            pop = prosp[code]["pop"]
        elif code in surv and surv[code].get("pop"):
            pop = surv[code]["pop"]
        elif code in delinq and delinq[code].get("pop"):
            pop = delinq[code]["pop"]
        if pop <= 0:
            continue
        pops[code] = pop

        en = enrich.get(code, {})
        rev = en.get("rev_med")
        pauv = en.get("tx_pauv")
        fam = maires[code]["f"] if code in maires and "f" in maires[code] else None

        if rev is None and pauv is None:
            continue

        vectors[code] = {
            "log_pop": math.log(pop),
            "rev_med": rev,
            "tx_pauv": pauv,
            "famille": fam,
        }

    print(f"  {len(vectors)} communes with feature vectors", file=sys.stderr)

    # Compute z-scores
    rev_vals = [v["rev_med"] for v in vectors.values() if v["rev_med"] is not None]
    pauv_vals = [v["tx_pauv"] for v in vectors.values() if v["tx_pauv"] is not None]
    logpop_vals = [v["log_pop"] for v in vectors.values()]

    def mean_std(vals):
        n = len(vals)
        if n == 0:
            return 0, 1
        m = sum(vals) / n
        variance = sum((x - m) ** 2 for x in vals) / n
        return m, max(math.sqrt(variance), 0.001)

    lp_mean, lp_std = mean_std(logpop_vals)
    rev_mean, rev_std = mean_std(rev_vals)
    pauv_mean, pauv_std = mean_std(pauv_vals)

    for v in vectors.values():
        v["lp_z"] = (v["log_pop"] - lp_mean) / lp_std
        v["rev_z"] = (v["rev_med"] - rev_mean) / rev_std if v["rev_med"] is not None else 0.0
        v["pauv_z"] = (v["tx_pauv"] - pauv_mean) / pauv_std if v["tx_pauv"] is not None else 0.0

    # Step 2: Find 20 nearest peers
    WEIGHTS = {"lp_z": 0.4, "rev_z": 0.25, "pauv_z": 0.25}
    FAMILY_BONUS = -0.3
    N_PEERS = 20

    def distance(a, b):
        d = 0.0
        for dim, w in WEIGHTS.items():
            d += w * (a[dim] - b[dim]) ** 2
        if a["famille"] and b["famille"] and a["famille"] == b["famille"]:
            d += FAMILY_BONUS
        return max(d, 0.0)

    codes_list = list(vectors.keys())
    print(f"  Computing peer groups for {len(codes_list)} communes...", file=sys.stderr)

    peers = {}
    for i, code in enumerate(codes_list):
        if (i + 1) % 5000 == 0:
            print(f"    {i + 1}/{len(codes_list)}...", file=sys.stderr)
        va = vectors[code]
        dists = []
        for other in codes_list:
            if other == code:
                continue
            d = distance(va, vectors[other])
            dists.append((d, other))
        dists.sort(key=lambda x: x[0])
        peers[code] = [c for _, c in dists[:N_PEERS]]

    # Step 3: Compute benchmarks and flags
    print("  Computing benchmarks and flags...", file=sys.stderr)
    result = {}

    for code in codes_list:
        peer_codes = peers[code]
        if not peer_codes:
            continue

        rec = {}
        top5 = peer_codes[:5]
        rec["peers"] = top5
        rec["peer_names"] = []
        for pc in top5:
            name = ""
            if pc in maires:
                name = maires[pc].get("n", pc)
            elif pc in prosp:
                name = pc
            rec["peer_names"].append(name or pc)

        bench = {}

        # Crime ratio
        my_crime = delinq.get(code, {}).get("r")
        peer_crimes = sorted([delinq[pc]["r"] for pc in peer_codes if pc in delinq and "r" in delinq[pc]])
        if my_crime is not None and len(peer_crimes) >= 3:
            med = peer_crimes[len(peer_crimes) // 2]
            pct = sum(1 for v in peer_crimes if v < my_crime) / len(peer_crimes) * 100
            bench["crime_r"] = {"val": round(my_crime, 1), "med": round(med, 1), "pct": round(pct)}

        # PM ratio
        my_surv = surv.get(code, {})
        my_pop = pops.get(code, 0)
        my_pm_r = None
        if my_pop > 0 and code in surv:
            my_pm_r = ((my_surv.get("pm", 0) + my_surv.get("asvp", 0)) / my_pop) * 10000
        peer_pm_r = []
        for pc in peer_codes:
            ps = surv.get(pc, {})
            pp = pops.get(pc, 0)
            if pp > 0 and pc in surv:
                peer_pm_r.append(((ps.get("pm", 0) + ps.get("asvp", 0)) / pp) * 10000)
        peer_pm_r.sort()
        if my_pm_r is not None and len(peer_pm_r) >= 3:
            med = peer_pm_r[len(peer_pm_r) // 2]
            pct = sum(1 for v in peer_pm_r if v < my_pm_r) / len(peer_pm_r) * 100
            bench["pm_r"] = {"val": round(my_pm_r, 1), "med": round(med, 1), "pct": round(pct)}

        # Accidents ratio
        my_acc = prosp.get(code, {}).get("accidents")
        if my_acc is not None and my_pop > 0:
            my_acc_r = my_acc / my_pop * 10000
            peer_acc_r = []
            for pc in peer_codes:
                pa = prosp.get(pc, {}).get("accidents")
                pp = pops.get(pc, 0)
                if pa is not None and pp > 0:
                    peer_acc_r.append(pa / pp * 10000)
            peer_acc_r.sort()
            if len(peer_acc_r) >= 3:
                med = peer_acc_r[len(peer_acc_r) // 2]
                pct = sum(1 for v in peer_acc_r if v < my_acc_r) / len(peer_acc_r) * 100
                bench["accidents_r"] = {"val": round(my_acc_r, 1), "med": round(med, 1), "pct": round(pct)}

        # Income
        my_rev = enrich.get(code, {}).get("rev_med")
        peer_revs = sorted([enrich[pc]["rev_med"] for pc in peer_codes if pc in enrich and "rev_med" in enrich[pc]])
        if my_rev is not None and len(peer_revs) >= 3:
            med = peer_revs[len(peer_revs) // 2]
            pct = sum(1 for v in peer_revs if v < my_rev) / len(peer_revs) * 100
            bench["rev_med"] = {"val": round(my_rev), "med": round(med), "pct": round(pct)}

        # Poverty
        my_pauv = enrich.get(code, {}).get("tx_pauv")
        peer_pauvs = sorted([enrich[pc]["tx_pauv"] for pc in peer_codes if pc in enrich and "tx_pauv" in enrich[pc]])
        if my_pauv is not None and len(peer_pauvs) >= 3:
            med = peer_pauvs[len(peer_pauvs) // 2]
            pct = sum(1 for v in peer_pauvs if v < my_pauv) / len(peer_pauvs) * 100
            bench["tx_pauv"] = {"val": round(my_pauv, 1), "med": round(med, 1), "pct": round(pct)}

        rec["bench"] = bench

        # Narrative flags
        flags = {}
        if "crime_r" in bench:
            flags["crime_above_peers"] = bench["crime_r"]["pct"] > 75

        has_pm = code in surv and (surv[code].get("pm", 0) + surv[code].get("asvp", 0)) > 0
        peers_with_pm = sum(1 for pc in peer_codes if pc in surv and (surv[pc].get("pm", 0) + surv[pc].get("asvp", 0)) > 0)
        peers_pm_pct = round(peers_with_pm / len(peer_codes) * 100) if peer_codes else 0
        flags["no_pm_peers_have"] = (not has_pm) and peers_pm_pct > 50
        flags["peers_pm_pct"] = peers_pm_pct

        has_vv = prosp.get(code, {}).get("videoverb", False)
        peers_with_vv = sum(1 for pc in peer_codes if prosp.get(pc, {}).get("videoverb", False))
        peers_vv_pct = round(peers_with_vv / len(peer_codes) * 100) if peer_codes else 0
        flags["no_vv_peers_have"] = (not has_vv) and peers_vv_pct > 30
        flags["peers_vv_pct"] = peers_vv_pct

        pm_trend = prosp.get(code, {}).get("pm_trend", [])
        flags["pm_growing"] = len(pm_trend) >= 2 and pm_trend[-1] > pm_trend[0]

        if "accidents_r" in bench:
            flags["high_accident_rate"] = bench["accidents_r"]["pct"] > 50

        my_dgf = enrich.get(code, {}).get("dgf_hab")
        peer_dgfs = sorted([enrich[pc]["dgf_hab"] for pc in peer_codes if pc in enrich and "dgf_hab" in enrich[pc]])
        if my_dgf is not None and len(peer_dgfs) >= 3:
            dgf_med = peer_dgfs[len(peer_dgfs) // 2]
            flags["budget_capacity"] = my_dgf > dgf_med

        if "tx_pauv" in bench:
            flags["high_poverty"] = bench["tx_pauv"]["pct"] > 60

        peers_with_sp = sum(1 for pc in peer_codes if prosp.get(pc, {}).get("stat_payant", False))
        flags["peers_stat_payant_pct"] = round(peers_with_sp / len(peer_codes) * 100) if peer_codes else 0

        rec["flags"] = flags
        result[code] = rec

    output_path = os.path.join(base, "insights.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nOutput: {output_path} ({size_kb:.0f} KB)", file=sys.stderr)
    print(f"  {len(result)} communes with insights", file=sys.stderr)

    if "11069" in result:
        print(f"\n  Sample (Carcassonne 11069):", file=sys.stderr)
        print(json.dumps(result["11069"], indent=2, ensure_ascii=False), file=sys.stderr)
    elif "75056" in result:
        print(f"\n  Sample (Paris 75056):", file=sys.stderr)
        print(json.dumps(result["75056"], indent=2, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
