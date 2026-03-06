#!/usr/bin/env python3
"""
Download and process communal crime statistics from Ministere de l'Interieur.
Produces delinquance.json indexed by 5-digit INSEE code.

Data source:
- Bases statistiques communales de la delinquance enregistree (police + gendarmerie)
  Parquet file from data.gouv.fr
"""
import json
import os
import sys

import pandas as pd

# ---------------------------------------------------------------------------
# Data source URL
# ---------------------------------------------------------------------------

PARQUET_URL = (
    "https://static.data.gouv.fr/resources/"
    "bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-"
    "enregistree-par-la-police-et-la-gendarmerie-nationales/"
    "20250710-144903/"
    "donnee-comm-data.gouv-parquet-2024-geographie2025-produit-le2025-06-04.parquet"
)

# ---------------------------------------------------------------------------
# Mapping from long indicateur names to short keys
# ---------------------------------------------------------------------------

INDICATEUR_MAP = {
    "Cambriolages de logement": "cambr",
    "Destructions et dégradations volontaires": "destr",
    "Escroqueries et fraudes aux moyens de paiement": "escro",
    "Trafic de stupéfiants": "traf_stup",
    "Usage de stupéfiants": "usage_stup",
    "Usage de stupéfiants (AFD)": "usage_stup_afd",
    "Violences physiques hors cadre familial": "viol_phys",
    "Violences physiques intrafamiliales": "viol_intraf",
    "Violences sexuelles": "viol_sex",
    "Vols avec armes": "vols_armes",
    "Vols d'accessoires sur véhicules": "vols_acc_veh",
    "Vols dans les véhicules": "vols_ds_veh",
    "Vols de véhicule": "vols_veh",
    "Vols sans violence contre des personnes": "vols_sv",
    "Vols violents sans arme": "vols_viol",
}

# Preferred unite_de_compte per indicateur. We pick the primary counting
# unit so we don't double-count the same crime in different units.
# For person-based crimes we prefer "Victime"; for property we prefer
# "Infraction" or the vehicle-based unit.
PREFERRED_UNIT = {
    "Cambriolages de logement": "Infraction",
    "Destructions et dégradations volontaires": "Infraction",
    "Escroqueries et fraudes aux moyens de paiement": "Infraction",
    "Trafic de stupéfiants": "Infraction",
    "Usage de stupéfiants": "Mis en cause",
    "Usage de stupéfiants (AFD)": "Mis en cause",
    "Violences physiques hors cadre familial": "Victime",
    "Violences physiques intrafamiliales": "Victime",
    "Violences sexuelles": "Victime",
    "Vols avec armes": "Victime",
    "Vols d'accessoires sur véhicules": "Infraction",
    "Vols dans les véhicules": "Infraction",
    "Vols de véhicule": "Véhicule",
    "Vols sans violence contre des personnes": "Victime",
    "Vols violents sans arme": "Victime",
}


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base_dir, "delinquance.json")

    # ------------------------------------------------------------------
    # 1. Load parquet
    # ------------------------------------------------------------------
    print("Downloading parquet from data.gouv.fr...", file=sys.stderr)
    df = pd.read_parquet(PARQUET_URL)
    print(f"  Loaded {len(df)} rows, {df['CODGEO_2025'].nunique()} communes", file=sys.stderr)

    # Detect commune code column
    code_col = None
    for candidate in ["CODGEO_2025", "codgeo_2025", "CODGEO", "codgeo", "Code.commune"]:
        if candidate in df.columns:
            code_col = candidate
            break
    if code_col is None:
        print("ERROR: cannot find commune code column among:", list(df.columns), file=sys.stderr)
        sys.exit(1)
    print(f"  Using code column: {code_col}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 2. Filter to latest year
    # ------------------------------------------------------------------
    latest_year = int(df["annee"].max())
    print(f"  Latest year: {latest_year}", file=sys.stderr)
    df = df[df["annee"] == latest_year].copy()
    print(f"  Rows for {latest_year}: {len(df)}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 3. Check for unmapped indicateurs
    # ------------------------------------------------------------------
    all_indicateurs = set(df["indicateur"].unique())
    mapped = set(INDICATEUR_MAP.keys())
    unmapped = all_indicateurs - mapped
    if unmapped:
        print(f"\n  WARNING: {len(unmapped)} unmapped indicateurs:", file=sys.stderr)
        for u in sorted(unmapped):
            print(f"    \"{u}\"", file=sys.stderr)
        print(file=sys.stderr)

    # ------------------------------------------------------------------
    # 4. Keep only mapped indicateurs and preferred unit per indicateur
    # ------------------------------------------------------------------
    df = df[df["indicateur"].isin(mapped)].copy()

    # For each indicateur, pick the preferred unite_de_compte
    keep_mask = pd.Series(False, index=df.index)
    for ind, unit in PREFERRED_UNIT.items():
        mask = (df["indicateur"] == ind) & (df["unite_de_compte"] == unit)
        if mask.sum() == 0:
            # Fallback: use whatever unit is available
            mask = df["indicateur"] == ind
        keep_mask |= mask
    df = df[keep_mask].copy()

    print(f"  Rows after filtering: {len(df)}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 5. Use nombre where available (est_diffuse == 'diff'),
    #    for non-diffused rows nombre is NaN — skip them (privacy masking)
    # ------------------------------------------------------------------
    # The 'nombre' field is NaN for ndiff communes (too small to publish).
    # We keep only rows with actual numbers.
    df = df[df["nombre"].notna()].copy()
    print(f"  Rows with nombre (diffused): {len(df)}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 6. Zero-pad commune codes to 5 digits
    # ------------------------------------------------------------------
    df[code_col] = df[code_col].astype(str).str.zfill(5)

    # ------------------------------------------------------------------
    # 7. Build per-commune aggregation
    # ------------------------------------------------------------------
    # Get population per commune (take first non-zero)
    pop_df = df.drop_duplicates(subset=[code_col])[[code_col, "insee_pop"]].copy()
    pop_map = dict(zip(pop_df[code_col], pop_df["insee_pop"]))

    # Build short-key column
    df["short_key"] = df["indicateur"].map(INDICATEUR_MAP)

    # Aggregate nombre per commune per category
    agg = df.groupby([code_col, "short_key"])["nombre"].sum().reset_index()

    result = {}
    for code, group in agg.groupby(code_col):
        cats = {}
        total = 0
        for _, row in group.iterrows():
            val = int(row["nombre"])
            if val > 0:
                cats[row["short_key"]] = val
                total += val

        if total == 0:
            continue

        pop = int(pop_map.get(code, 0))
        entry = {"total": total, "cats": cats}
        if pop > 0:
            entry["pop"] = pop
            entry["r"] = round(total / pop * 10000, 1)
        entry["year"] = str(latest_year)
        result[code] = entry

    # ------------------------------------------------------------------
    # 8. Write output
    # ------------------------------------------------------------------
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nOutput: {output_path} ({size_kb:.0f} KB)", file=sys.stderr)
    print(f"  {len(result)} communes with crime data", file=sys.stderr)
    pop_count = sum(1 for v in result.values() if "pop" in v)
    ratio_count = sum(1 for v in result.values() if "r" in v)
    print(f"  {pop_count} communes with population", file=sys.stderr)
    print(f"  {ratio_count} communes with ratio", file=sys.stderr)

    # Show category counts
    cat_totals = {}
    for v in result.values():
        for k, val in v["cats"].items():
            cat_totals[k] = cat_totals.get(k, 0) + val
    print(f"\n  Category totals:", file=sys.stderr)
    for k in sorted(cat_totals, key=cat_totals.get, reverse=True):
        # Find long name
        long_name = next((ln for ln, sk in INDICATEUR_MAP.items() if sk == k), k)
        print(f"    {k:15s} {cat_totals[k]:>10,d}  ({long_name})", file=sys.stderr)

    # Sample entries
    sample_codes = ["75056", "13055", "69123", "31555", "59350"]
    print(f"\n  Sample entries:", file=sys.stderr)
    for code in sample_codes:
        if code in result:
            print(f"    {code}: {json.dumps(result[code], ensure_ascii=False)}", file=sys.stderr)


if __name__ == "__main__":
    main()
