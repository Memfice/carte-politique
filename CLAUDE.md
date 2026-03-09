# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Interactive map visualizing French municipal mayors' political affiliations, local surveillance data, crime statistics, and socio-economic indicators across ~35,000 communes. Four modes: **prospection** (composite score for video-enforcement potential, default), **politique** (political family colors), **surveillance** (heatmap of police agents per capita), and **securite** (crime rate heatmap by category).

## Architecture

**Single-file frontend** — all HTML, CSS, and JavaScript live in `index.html` (~2700 lines). No build system, no package manager, no framework beyond Leaflet.

### Frontend Stack
- **Leaflet.js** (v1.9.4) for map rendering, loaded from CDN with SRI hash
- **topojson-client** (v3.1.0) for converting TopoJSON → GeoJSON, loaded from CDN with SRI hash
- **CartoDB Dark No Labels** basemap
- Vanilla JavaScript (ES5-compatible), inline CSS

### Data Pipeline
Python scripts generate JSON data files from external sources (data.gouv.fr, INSEE, ONISR, DGFiP):

```
process_maires.py       → maires.json        (mayors + political family, ~3.8 MB)
process_surveillance.py → surveillance.json  (police counts + ratio, ~183 KB)
process_prospection.py  → prospection.json   (prospection signals + scoring data, ~1.3 MB)
process_delinquance.py  → delinquance.json   (crime stats by commune, ~1.2 MB)
process_enrichment.py   → enrichment.json    (QPV, DGFiP finances, revenus, ~3.2 MB)
process_insights.py     → insights.json      (peer groups, benchmarks, narrative flags, ~5 MB)
```

Python dependencies: `pandas`, `openpyxl`, `odf`, `pyarrow` (for parquet)

### Key Data Files
- `communes-topo.json` — TopoJSON commune boundaries (13 MB, object key: `a_com2022`)
- `maires.json` — keyed by INSEE code, fields: `n` (name), `nu` (nuance), `f` (famille), `cl` (color), `lb` (label), `m` (maire)
- `surveillance.json` — keyed by INSEE code, fields: `pm` (police municipale), `asvp` (ASVP agents), `pop` (population), `r` (ratio per 10k, capped at 50), `r_raw` (uncapped ratio, only if capped)
- `prospection.json` — keyed by INSEE code, fields: `stat_payant`, `videoverb`, `pm`, `asvp`, `pop`, `pm_trend` (array), `pm_trend_years` (array), `accidents` (count 2023-2024), `accidents_years`
- `delinquance.json` — keyed by INSEE code, fields: `total` (total crimes), `cats` (object with 15 short keys), `pop` (population), `r` (ratio per 10k), `year`
- `enrichment.json` — keyed by INSEE code, fields: `qpv` (QPV count), `dgf_hab` (DGF per capita), `dette_hab`, `cafn_hab`, `perso_hab`, `rev_med` (median income), `tx_pauv` (poverty rate)
- `insights.json` — keyed by INSEE code, fields: `peers` (top 5 peer codes), `peer_names` (display names), `bench` (benchmarks: `crime_r`, `pm_r`, `accidents_r`, `rev_med`, `tx_pauv` each with `val`/`med`/`pct`), `flags` (narrative booleans + numeric: `crime_above_peers`, `no_pm_peers_have`, `no_vv_peers_have`, `pm_growing`, `high_accident_rate`, `budget_capacity`, `high_poverty`, `peers_pm_pct`, `peers_vv_pct`, `peers_stat_payant_pct`)

### Crime Categories (delinquance.json `cats` keys)
`cambr` (cambriolages), `destr` (destructions), `escro` (escroqueries), `traf_stup` (trafic stupefiants), `usage_stup`, `usage_stup_afd`, `viol_phys` (violences physiques), `viol_intraf` (violences intrafamiliales), `viol_sex` (violences sexuelles), `vols_armes`, `vols_acc_veh`, `vols_ds_veh`, `vols_veh`, `vols_sv` (vols sans violence), `vols_viol`

### Prospection Scoring
Composite score from 6 weighted signals (no_videoverb moved to filter-only):
- `stat_payant` (30%) — commune has paid parking (GART 2019)
- `pm_count` (20%) — police agents per 10k pop, capped at 1
- `pm_growth` (10%) — growth rate weighted by sqrt(volume) to avoid small-number noise
- `accidents` (15%) — road accidents per 10k pop (ONISR 2023-2024)
- `pop_sweet` (25%) — gaussian on log(pop) centered at 30k
- `budget_capacity` (0% default) — DGF per capita normalized (DGFiP 2022), user-activatable

### Performance Patterns
- **Pre-allocated style constants** — 6 shared `STYLE_*` objects reused across 35k features per restyle (Leaflet copies properties, never mutates source)
- **`dashArray: null`** on all non-dashed styles — prevents Leaflet `setStyle` merge leak when switching from dashed modes (surveillance/securite) to non-dashed (politique/prospection)
- **Score caching** — `prospScoreCache` avoids recomputing 35k scores; invalidated on weight/filter change
- **Debounced sliders** — all range inputs use 50ms `setTimeout` to avoid 60Hz restyles during drag
- **Search normalization** — `nameNorm` pre-computed at index build time (NFD + diacritics strip + lowercase) instead of per keystroke
- **Memory management** — `topoData = null` after TopoJSON→GeoJSON conversion, `communesGeo = null` after layer creation

### State Management
Global JS variables: `currentMode` ('prospection'|'politique'|'surveillance'|'securite', default: `'prospection'`), `activeFilter` (selected political family), `survFilters` (ratio slider + checkbox), `prospWeights` (signal weights for scoring), `prospFilters` (prospection mode filters including `qpvOnly`), `secuFilter` (selected crime category or null), `secuFilters` (ratioMin slider + dataOnly checkbox), `delinq` (delinquance data object), `enrich` (enrichment data object), `insights` (peer groups + benchmarks + narrative flags).

### Deep Linking
URL parameters: `?mode=X&commune=XXXXX&filter=Y`. State encoded via `history.pushState` (commune changes) and `history.replaceState` (mode/filter changes). Restored on page load after data and layers are initialized. Default mode (prospection) omitted from URL for clean links.

### Core Flow
1. Fetch 7 JSON data files on load (maires, surveillance, prospection, delinquance, enrichment, insights)
2. Convert TopoJSON → GeoJSON via `topojson.feature()`, then free source objects
3. Style communes via `getStylePolitique()`, `getStyleSurveillance()`, `getStyleSecurite()`, or `getStyleProspection()` based on mode; all return `dashArray: null` (or `'2 4'` for dashed) to prevent style leaks
4. Hover shows info panel (`#info`), click zooms + opens detail panel (`#detail-panel.open`)
5. Search bar with autocomplete indexes commune names from all data sources, uses `layerByCode` lookup to zoom to selected commune
6. Detail panel shows all available data for a commune regardless of active mode (delinquance breakdown, finances, QPV badge, freshness badges)
7. **Argumentaire section** in detail panel: auto-generated sales narrative from peer-group benchmarks, comparison table, clickable peer commune links
8. **Deep linking** via URL parameters: `?mode=X&commune=XXXXX&filter=Y` — state restored on page load
9. Methodology drawer (`#methodo-drawer`) documents sources, freshness, and known biases

### Mode Colors
| Mode | Color | Palette |
|------|-------|---------|
| Prospection | `#4ecdc4` | Blue → red (5 levels) |
| Politique | `#4a90d9` | Political family colors |
| Surveillance | `#e8913a` | Yellow → red (6 levels) |
| Securite | `#c0392b` | Violet → magenta (6 levels, `SECU_COLORS`) |

### UI Layout
- **`#top-bar`** — search box, mode tab buttons (`.mode-btn[data-mode]`), methodology button
- **`#cmd-panel > #cmd-content`** — left sidebar, dynamically rebuilt on mode switch (`renderCmdPolitique`, `renderCmdSurveillance`, `renderCmdSecurite`, `renderCmdProspection`)
- **`#map`** — Leaflet container
- **`#bottom-bar > #bottom-stats`** — contextual stats per mode
- **`#detail-panel`** — slide-in right panel (`.open` class), commune-level deep dive
- **`#info`** — floating tooltip on hover
- **`#methodo-overlay` + `#methodo-drawer`** — methodology slide-in drawer

## Commands

### Regenerate data files
```bash
python3 process_maires.py           # requires nuances-communes.csv + elus-maires.csv in /tmp
python3 process_surveillance.py     # downloads from data.gouv.fr APIs
python3 process_prospection.py      # builds prospection scoring data
python3 process_delinquance.py      # downloads parquet from data.gouv.fr (~14 MB)
python3 process_enrichment.py       # downloads QPV CSV, DGFiP JSON, Filosofi 2021 CSV
python3 process_insights.py        # computes peer groups + benchmarks from other JSONs (~2 min)
```

### Development
Open `index.html` directly in a browser — no dev server needed.

## Conventions

- **Commits:** `type: message` format (feat, fix, style, docs, chore)
- **JS naming:** camelCase variables, kebab-case DOM IDs and CSS classes
- **Data keys:** short abbreviations to minimize JSON size (see data files section above)
- **Language:** UI text is in French
- **Style returns:** every `getStyle*()` function and `STYLE_*` constant must include `dashArray` (either `null` or a dash pattern) to prevent Leaflet merge leaks
- **CDN scripts:** must have `integrity` (SRI) and `crossorigin="anonymous"` attributes
- **Slider handlers:** must debounce expensive operations (restyle, list rebuild) at 50ms minimum
- **Leaflet gotcha:** `setStyle()` merges properties (doesn't replace); use `resetStyle()` or explicit nulls to clear stale properties
