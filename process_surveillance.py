#!/usr/bin/env python3
"""
Download and process surveillance datasets from data.gouv.fr.
Produces surveillance.json indexed by INSEE code.

Data sources:
- Police municipale effectifs 2024 (Ministere de l'Interieur, ODS)
- Population legale INSEE 2021 (XLSX)
"""
import json
import sys
import unicodedata
import urllib.request
import tempfile
import os

# URLs
POLICE_MUN_URL = "https://www.data.gouv.fr/api/1/datasets/r/081e94fe-b257-4ae7-bc31-bf1f2eb6c968"
POPULATION_URL = "https://www.data.gouv.fr/api/1/datasets/r/be303501-5c46-48a1-87b4-3d198423ff49"

# Winsorize ratio at this value (agents per 10k inhabitants)
RATIO_CAP = 50


def normalize(name):
    """Normalize commune name for fuzzy matching."""
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.upper().strip()
    if "(" in name:
        name = name[:name.index("(")].strip()
    name = name.replace("-", " ").replace("'", " ").replace("\u2019", " ").replace("\u2018", " ").replace("`", " ")
    while "  " in name:
        name = name.replace("  ", " ")
    name = name.replace("ST ", "SAINT ").replace("STE ", "SAINTE ")
    return name.strip()


def build_insee_lookup(maires_path):
    """Build (dept_num, normalized_name) -> INSEE code lookup from maires.json."""
    with open(maires_path, encoding="utf-8") as f:
        maires = json.load(f)

    lookup = {}
    for code, info in maires.items():
        name = info["n"]
        if code.startswith("97"):
            dept = code[:3]
        elif code.startswith("2A") or code.startswith("2B"):
            dept = code[:2]
        else:
            dept = code[:2]

        dept_num = dept.lstrip("0") if dept.isdigit() else dept
        lookup[(dept_num, normalize(name))] = code
    return lookup


def parse_police_municipale(ods_path, lookup):
    """Parse police municipale ODS file. Returns dict {insee: {pm, asvp}}."""
    import pandas as pd

    df = pd.read_excel(ods_path, engine="odf", header=None)
    result = {}
    matched = 0
    unmatched = []

    for i in range(10, len(df)):
        row = df.iloc[i]
        dept_raw = row.iloc[0]
        name_raw = row.iloc[3]

        if not isinstance(dept_raw, (int, float)):
            continue
        if pandas_isna(name_raw):
            continue

        dept = str(int(dept_raw))
        name = str(name_raw).strip()
        pm = safe_int(row.iloc[6])
        asvp = safe_int(row.iloc[7])

        key = (dept, normalize(name))
        insee = lookup.get(key)

        if insee:
            result[insee] = {"pm": pm, "asvp": asvp}
            matched += 1
        else:
            unmatched.append(f"  {dept} / {name}")

    print(f"Police municipale: {matched} matched, {len(unmatched)} unmatched", file=sys.stderr)
    if unmatched[:10]:
        print("First unmatched:", file=sys.stderr)
        for u in unmatched[:10]:
            print(u, file=sys.stderr)

    return result


def parse_population(xlsx_path):
    """Parse INSEE population XLSX. Returns dict {insee_code: population}."""
    import pandas as pd
    import re

    df = pd.read_excel(xlsx_path, engine="openpyxl")
    result = {}

    pop_cols = [c for c in df.columns if str(c).startswith("pop_municipale") or str(c).startswith("pmun") or re.match(r"^p\d+_pop$", str(c))]
    if not pop_cols:
        for col in df.columns:
            print(f"  Column: {col}", file=sys.stderr)
        raise ValueError("Cannot find population column. See column names above.")

    pop_col = pop_cols[-1]
    code_col = None
    for candidate in ["codgeo", "CODGEO", "code_commune", "COM"]:
        if candidate in df.columns:
            code_col = candidate
            break

    if code_col is None:
        for col in df.columns:
            print(f"  Column: {col}", file=sys.stderr)
        raise ValueError("Cannot find code commune column. See column names above.")

    for _, row in df.iterrows():
        code = str(row[code_col]).strip()
        pop = safe_int(row[pop_col])
        if code and pop > 0:
            result[code] = pop

    print(f"Population: {len(result)} communes loaded", file=sys.stderr)
    return result


def safe_int(val):
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return 0
        return int(val)
    except (ValueError, TypeError):
        return 0


def pandas_isna(val):
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return True
    except (TypeError, ValueError):
        pass
    return val is None or (isinstance(val, str) and val.strip() == "")


def main():
    maires_path = os.path.join(os.path.dirname(__file__), "maires.json")
    output_path = os.path.join(os.path.dirname(__file__), "surveillance.json")

    print("Building INSEE lookup from maires.json...", file=sys.stderr)
    lookup = build_insee_lookup(maires_path)
    print(f"  {len(lookup)} communes indexed", file=sys.stderr)

    print("Downloading police municipale 2024 ODS...", file=sys.stderr)
    tmp = tempfile.NamedTemporaryFile(suffix=".ods", delete=False)
    urllib.request.urlretrieve(POLICE_MUN_URL, tmp.name)
    police_data = parse_police_municipale(tmp.name, lookup)
    os.unlink(tmp.name)

    print("Downloading population INSEE XLSX...", file=sys.stderr)
    tmp_pop = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    urllib.request.urlretrieve(POPULATION_URL, tmp_pop.name)
    population = parse_population(tmp_pop.name)
    os.unlink(tmp_pop.name)

    result = {}
    all_codes = set(police_data.keys())

    for code in all_codes:
        entry = {}
        entry["pm"] = police_data[code]["pm"]
        entry["asvp"] = police_data[code]["asvp"]
        if code in population:
            entry["pop"] = population[code]
            agents = entry["pm"] + entry["asvp"]
            if agents > 0 and population[code] > 0:
                ratio = agents / population[code] * 10000
                entry["r"] = round(min(ratio, RATIO_CAP), 1)
                if ratio > RATIO_CAP:
                    entry["r_raw"] = round(ratio, 1)
        result[code] = entry

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nOutput: {output_path} ({size_kb:.0f} KB)", file=sys.stderr)
    print(f"  {len(police_data)} communes with police municipale data", file=sys.stderr)
    pop_count = sum(1 for v in result.values() if "pop" in v)
    ratio_count = sum(1 for v in result.values() if "r" in v)
    capped = sum(1 for v in result.values() if "r_raw" in v)
    print(f"  {pop_count} communes with population data", file=sys.stderr)
    print(f"  {ratio_count} communes with agent/population ratio", file=sys.stderr)
    print(f"  {capped} communes with ratio capped at {RATIO_CAP}", file=sys.stderr)
    print(f"  {len(result)} communes total in output", file=sys.stderr)


if __name__ == "__main__":
    main()
