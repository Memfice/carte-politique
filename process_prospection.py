#!/usr/bin/env python3
"""
Download and process prospection datasets for videoverbalisation sales potential.
Produces prospection.json indexed by INSEE code.

Data sources:
- Police municipale effectifs multi-year (Min. Interieur) -- agent counts + trend
- Stationnement payant (GART/Cerema 2019 survey) -- communes with paid parking
- Videoverbalisation (video-verbalisation.fr) -- communes already equipped
- Accidents corporels de la circulation 2022-2024 (ONISR) -- road accidents per commune
- Population from existing surveillance.json
"""
import csv
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def download_file(url, suffix):
    """Download URL to a temp file, return path."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    urllib.request.urlretrieve(url, tmp.name)
    return tmp.name


# ---------------------------------------------------------------------------
# Police municipale multi-year trend
# ---------------------------------------------------------------------------

PM_URLS = {
    2019: ("https://www.data.gouv.fr/api/1/datasets/r/dcd42332-aa52-4362-8d61-69a9f274cc73", ".ods"),
    2021: ("https://www.data.gouv.fr/api/1/datasets/r/835130b5-d34a-41c6-9bd1-df6bcaa4372b", ".xlsx"),
    2024: ("https://www.data.gouv.fr/api/1/datasets/r/081e94fe-b257-4ae7-bc31-bf1f2eb6c968", ".ods"),
}


def parse_pm_year(file_path, lookup, year):
    """Parse police municipale ODS/XLSX for a single year.

    Returns {insee_code: total_agents (pm + asvp)}.
    """
    import pandas as pd

    ext = os.path.splitext(file_path)[1].lower()
    engine = "odf" if ext == ".ods" else "openpyxl"
    df = pd.read_excel(file_path, engine=engine, header=None)

    result = {}
    matched = 0

    for i in range(10, len(df)):
        row = df.iloc[i]
        dept_raw = row.iloc[0]
        name_raw = row.iloc[3]

        if not isinstance(dept_raw, (int, float)) or pandas_isna(dept_raw):
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
            result[insee] = pm + asvp
            matched += 1

    print(f"  PM {year}: {matched} communes matched", file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# Stationnement payant (GART/Cerema 2019)
# ---------------------------------------------------------------------------

STAT_PAYANT_URL = "https://static.data.gouv.fr/resources/enquete-sur-la-reforme-du-stationnement-payant-sur-voirie/20200207-161331/stt-voirie-payant-opendata-v2.csv"
STAT_PAYANT_YEAR = 2019


def parse_stationnement_payant(csv_path):
    """Parse GART stationnement payant CSV.

    Returns set of INSEE codes with paid parking.
    """
    with open(csv_path, encoding="latin-1") as f:
        reader = csv.DictReader(f, delimiter=";")
        result = set()
        for row in reader:
            code = row.get("Code INSEE", "").strip()
            if code:
                code = code.zfill(5)
                result.add(code)
    print(f"  Stationnement payant: {len(result)} communes", file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# Videoverbalisation (video-verbalisation.fr scraping)
# ---------------------------------------------------------------------------

VIDEOVERB_URL = "https://video-verbalisation.fr/villes.php"
VIDEOVERB_YEAR = 2025


def scrape_videoverbalisation(lookup):
    """Scrape video-verbalisation.fr for commune list.

    Returns set of INSEE codes with videoverbalisation.
    """
    headers = {"User-Agent": "Mozilla/5.0 (carte-politique research bot)"}
    req = urllib.request.Request(VIDEOVERB_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  WARNING: Could not fetch video-verbalisation.fr: {e}", file=sys.stderr)
        return set()

    city_names = re.findall(r'href="/[a-z-]+/[a-z-]+/">([^<]+)</a>', html)

    # Build reverse lookup for O(1) matching by normalized name
    name_to_codes = {}
    for key, code in lookup.items():
        name_to_codes.setdefault(key[1], []).append(code)

    matched = set()
    unmatched = []
    for name in city_names:
        name = name.strip()
        if len(name) < 2:
            continue
        norm = normalize(name)
        codes = name_to_codes.get(norm)
        if codes:
            matched.update(codes)
        else:
            unmatched.append(name)

    print(f"  Videoverbalisation: {len(city_names)} cities found, {len(matched)} matched, {len(unmatched)} unmatched", file=sys.stderr)
    if unmatched[:10]:
        print("  First unmatched:", file=sys.stderr)
        for u in unmatched[:10]:
            print(f"    {u}", file=sys.stderr)
    return matched


# ---------------------------------------------------------------------------
# Accidents corporels (ONISR / BAAC)
# ---------------------------------------------------------------------------

CARACT_URLS = {
    2023: "https://static.data.gouv.fr/resources/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2023/20241028-103125/caract-2023.csv",
    2024: "https://static.data.gouv.fr/resources/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024/20251021-115900/caract-2024.csv",
}


def parse_accidents(years=(2023, 2024)):
    """Download and parse accident characteristic files.

    The caract CSV has columns: Num_Acc;jour;mois;an;hrmn;lum;dep;com;...
    where 'com' is the 5-digit INSEE code of the commune.

    Returns dict {insee_code: total_accidents} summed over requested years.
    """
    result = {}

    for year in years:
        url = CARACT_URLS.get(year)
        if not url:
            continue
        print(f"  Downloading accidents {year}...", file=sys.stderr)
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"    WARNING: Could not download {year}: {e}", file=sys.stderr)
            continue

        reader = csv.DictReader(text.splitlines(), delimiter=";")
        year_count = 0
        seen_acc = set()
        for row in reader:
            num_acc = row.get("Num_Acc", "").strip()
            if num_acc in seen_acc:
                continue
            seen_acc.add(num_acc)

            com = row.get("com", "").strip()
            if not com or len(com) < 4:
                continue
            # Ensure 5-digit code
            com = com.zfill(5)
            result[com] = result.get(com, 0) + 1
            year_count += 1

        print(f"    {year}: {year_count} accidents parsed", file=sys.stderr)

    print(f"  Accidents total: {len(result)} communes with data, {sum(result.values())} accidents", file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    base_dir = os.path.dirname(__file__)
    maires_path = os.path.join(base_dir, "maires.json")
    surv_path = os.path.join(base_dir, "surveillance.json")
    output_path = os.path.join(base_dir, "prospection.json")

    print("Building INSEE lookup from maires.json...", file=sys.stderr)
    lookup = build_insee_lookup(maires_path)
    print(f"  {len(lookup)} communes indexed", file=sys.stderr)

    # --- Police municipale multi-year ---
    pm_by_year = {}
    print("\nDownloading police municipale multi-year data...", file=sys.stderr)
    for year, (url, suffix) in sorted(PM_URLS.items()):
        print(f"  Downloading {year}...", file=sys.stderr)
        path = download_file(url, suffix)
        pm_by_year[year] = parse_pm_year(path, lookup, year)
        os.unlink(path)

    # --- Stationnement payant ---
    print("\nDownloading stationnement payant data...", file=sys.stderr)
    stat_path = download_file(STAT_PAYANT_URL, ".csv")
    stat_payant_codes = parse_stationnement_payant(stat_path)
    os.unlink(stat_path)

    # --- Videoverbalisation ---
    print("\nScraping videoverbalisation data...", file=sys.stderr)
    videoverb_codes = scrape_videoverbalisation(lookup)

    # --- Accidents routiers ---
    print("\nDownloading accident data (2023-2024)...", file=sys.stderr)
    accidents = parse_accidents()

    # --- Merge surveillance.json data ---
    print("\nLoading surveillance.json for population + PM...", file=sys.stderr)
    with open(surv_path, encoding="utf-8") as f:
        surv = json.load(f)

    # --- Build output ---
    print("\nBuilding prospection.json...", file=sys.stderr)
    result = {}
    all_codes = set()
    for year_data in pm_by_year.values():
        all_codes |= set(year_data.keys())
    all_codes |= stat_payant_codes
    all_codes |= videoverb_codes
    all_codes |= set(surv.keys())
    all_codes |= set(accidents.keys())

    for code in sorted(all_codes):
        entry = {}

        # PM trend
        years_sorted = sorted(pm_by_year.keys())
        trend = []
        trend_years = []
        for y in years_sorted:
            if code in pm_by_year[y]:
                trend.append(pm_by_year[y][code])
                trend_years.append(y)
        if trend:
            entry["pm_trend"] = trend
            entry["pm_trend_years"] = trend_years

        # Stationnement payant
        if code in stat_payant_codes:
            entry["stat_payant"] = True
            entry["stat_payant_year"] = STAT_PAYANT_YEAR

        # Videoverbalisation
        if code in videoverb_codes:
            entry["videoverb"] = True
            entry["videoverb_year"] = VIDEOVERB_YEAR

        # Accidents
        if code in accidents:
            entry["accidents"] = accidents[code]
            entry["accidents_years"] = "2023-2024"

        # Population + PM current from surveillance.json
        surv_entry = surv.get(code, {})
        if "pop" in surv_entry:
            entry["pop"] = surv_entry["pop"]
            entry["pop_year"] = 2021
        if "pm" in surv_entry:
            entry["pm"] = surv_entry["pm"]
        if "asvp" in surv_entry:
            entry["asvp"] = surv_entry["asvp"]

        if entry:
            result[code] = entry

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nOutput: {output_path} ({size_kb:.0f} KB)", file=sys.stderr)
    print(f"  {len(result)} communes total", file=sys.stderr)
    for key in ["pm_trend", "stat_payant", "videoverb", "accidents", "pop", "pm"]:
        count = sum(1 for v in result.values() if key in v)
        print(f"  {key}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
