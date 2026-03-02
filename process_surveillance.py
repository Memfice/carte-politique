#!/usr/bin/env python3
"""
Download and process surveillance datasets from data.gouv.fr.
Produces surveillance.json indexed by INSEE code.
"""
import csv
import json
import io
import sys
import unicodedata
import urllib.request
import tempfile
import os

# URLs
POLICE_MUN_URL = "https://www.data.gouv.fr/api/1/datasets/r/081e94fe-b257-4ae7-bc31-bf1f2eb6c968"
VIDEOSURV_URL = "https://www.data.gouv.fr/api/1/datasets/r/b56c1eda-6b75-468a-b33f-147d37224c9e"


def normalize(name):
    """Normalize commune name for fuzzy matching."""
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = name.upper().strip()
    if "(" in name:
        name = name[:name.index("(")].strip()
    # Replace all apostrophe variants (straight, curly, backtick) with space
    name = name.replace("-", " ").replace("'", " ").replace("\u2019", " ").replace("\u2018", " ").replace("`", " ")
    # Collapse multiple spaces
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


def parse_videosurveillance(csv_text, lookup):
    """Parse videosurveillance CSV. Returns set of INSEE codes."""
    reader = csv.DictReader(io.StringIO(csv_text))
    result = set()
    matched = 0
    unmatched = 0

    for row in reader:
        dept = row["Numero departement"].strip()
        name = row["Ville"].strip()

        key = (dept, normalize(name))
        insee = lookup.get(key)
        if insee:
            result.add(insee)
            matched += 1
        else:
            unmatched += 1

    print(f"Videosurveillance: {matched} matched, {unmatched} unmatched", file=sys.stderr)
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

    print("Downloading videosurveillance CSV...", file=sys.stderr)
    with urllib.request.urlopen(VIDEOSURV_URL) as resp:
        csv_text = resp.read().decode("utf-8")
    vs_codes = parse_videosurveillance(csv_text, lookup)

    result = {}
    all_codes = set(police_data.keys()) | vs_codes

    for code in all_codes:
        entry = {}
        if code in police_data:
            entry["pm"] = police_data[code]["pm"]
            entry["asvp"] = police_data[code]["asvp"]
        if code in vs_codes:
            entry["vs"] = 1
        result[code] = entry

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nOutput: {output_path} ({size_kb:.0f} KB)", file=sys.stderr)
    print(f"  {len(police_data)} communes with police municipale data", file=sys.stderr)
    print(f"  {len(vs_codes)} communes with videosurveillance", file=sys.stderr)
    print(f"  {len(result)} communes total in output", file=sys.stderr)


if __name__ == "__main__":
    main()
