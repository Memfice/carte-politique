# Mode Surveillance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated surveillance visualization mode with population-normalized data, heatmap coloring, statistics sidebar, and interactive filters.

**Architecture:** Enrich the Python data pipeline to include INSEE population data and compute surveillance ratios. Add a mode toggle to the existing Leaflet map that switches between political coloring (current) and surveillance heatmap coloring. A statistics sidebar shows correlation between political affiliation and surveillance intensity.

**Tech Stack:** Python 3 + pandas (data pipeline), vanilla JS + Leaflet (frontend), single index.html file.

---

### Task 1: Enrich `process_surveillance.py` with population data

**Files:**
- Modify: `process_surveillance.py`
- Output: `surveillance.json` (regenerated)

**Step 1: Add population download and parsing**

Add a new URL constant at the top with other URLs:

```python
POPULATION_URL = "https://www.data.gouv.fr/api/1/datasets/r/630e7917-02db-4838-8856-09235719551c"
```

Add function to parse population XLSX:

```python
def parse_population(xlsx_path):
    """Parse INSEE population XLSX. Returns dict {insee_code: population}."""
    import pandas as pd

    df = pd.read_excel(xlsx_path, engine="openpyxl")
    result = {}

    # The file has columns including codgeo (INSEE code) and population columns
    # Find the most recent population column
    pop_cols = [c for c in df.columns if str(c).startswith("pop_municipale") or str(c).startswith("pmun")]
    if not pop_cols:
        # Fallback: print columns for debugging
        for col in df.columns:
            print(f"  Column: {col}", file=sys.stderr)
        raise ValueError("Cannot find population column. See column names above.")

    pop_col = pop_cols[-1]  # Most recent
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
```

Note: `openpyxl` needs to be installed (`pip install openpyxl`).

**Step 2: Integrate population into main() and compute ratio**

In `main()`, after downloading police/videosurveillance data, add population download:

```python
    print("Downloading population INSEE XLSX...", file=sys.stderr)
    tmp_pop = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    urllib.request.urlretrieve(POPULATION_URL, tmp_pop.name)
    population = parse_population(tmp_pop.name)
    os.unlink(tmp_pop.name)
```

Update the result-building loop to include population and ratio:

```python
    for code in all_codes:
        entry = {}
        if code in police_data:
            entry["pm"] = police_data[code]["pm"]
            entry["asvp"] = police_data[code]["asvp"]
        if code in vs_codes:
            entry["vs"] = 1
        if code in population:
            entry["pop"] = population[code]
            agents = (entry.get("pm", 0) + entry.get("asvp", 0))
            if agents > 0 and population[code] > 0:
                entry["r"] = round(agents / population[code] * 10000, 1)
        result[code] = entry
```

**Step 3: Run the script and verify output**

Run: `cd /home/hadrien/carte-politique && python3 process_surveillance.py`

Expected: Script completes. `surveillance.json` entries now have `pop` and `r` fields.

Verify: `python3 -c "import json; d=json.load(open('surveillance.json')); sample=list(d.items())[:3]; print(json.dumps(dict(sample), indent=2))"`

Expected shape: `{"CODE": {"pm": 5, "asvp": 0, "vs": 1, "pop": 12000, "r": 4.2}}`

Note: The population XLSX column names may differ. If the script fails with "Cannot find population column", read the printed column names and adjust the column detection logic.

**Step 4: Commit**

```bash
git add process_surveillance.py surveillance.json
git commit -m "feat: add population data and surveillance ratio to surveillance.json"
```

---

### Task 2: Add mode toggle UI and surveillance CSS

**Files:**
- Modify: `index.html` (CSS section + HTML section)

**Step 1: Add CSS for new UI elements**

Add before the closing `</style>` tag (after `.filter-btn.active` rule, ~line 71):

```css
#mode-toggle {
  position: absolute; top: 70px; left: 10px; z-index: 1000;
  display: flex; border-radius: 8px; overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.mode-btn {
  padding: 8px 16px; border: none; cursor: pointer;
  font-size: 13px; font-weight: 600;
  background: rgba(255,255,255,0.95); color: #333;
  transition: all 0.2s;
}
.mode-btn:first-child { border-right: 1px solid #ddd; }
.mode-btn.active { background: #333; color: white; }

#stats-panel {
  position: absolute; top: 10px; right: 10px; z-index: 1000;
  background: rgba(255,255,255,0.95); padding: 16px;
  border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  font-size: 13px; width: 320px; max-height: calc(100vh - 30px);
  overflow-y: auto; display: none;
}
#stats-panel h3 { font-size: 14px; margin-bottom: 10px; }
#stats-panel table {
  width: 100%; border-collapse: collapse; font-size: 12px;
}
#stats-panel th, #stats-panel td {
  padding: 5px 6px; text-align: left; border-bottom: 1px solid #eee;
}
#stats-panel th { font-weight: 600; color: #666; font-size: 11px; }
#stats-panel tr.clickable { cursor: pointer; }
#stats-panel tr.clickable:hover { background: #f5f5f5; }
#stats-panel .stats-note {
  margin-top: 12px; font-size: 10px; color: #999; line-height: 1.4;
}
#stats-panel .stats-summary {
  margin: 10px 0; padding: 8px; background: #f8f8f8;
  border-radius: 4px; font-size: 12px; line-height: 1.5;
}

#surv-filters {
  position: absolute; top: 80px; left: 50%; transform: translateX(-50%);
  z-index: 1000; display: none; background: rgba(255,255,255,0.95);
  padding: 10px 16px; border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  font-size: 12px; gap: 12px; align-items: center;
}
#surv-filters label { display: flex; align-items: center; gap: 4px; cursor: pointer; }
#surv-filters input[type="range"] { width: 100px; }
#surv-filters .slider-value { min-width: 30px; font-weight: 600; }

.surv-mode #info { top: auto; bottom: 30px; }
```

**Step 2: Add mode toggle HTML**

Add right after `<div id="title-bar">...</div>` (~line 86):

```html
<div id="mode-toggle">
  <button class="mode-btn active" data-mode="politique">Vue politique</button>
  <button class="mode-btn" data-mode="surveillance">Vue surveillance</button>
</div>
```

**Step 3: Add stats panel HTML**

Add right after the `<div id="info">...</div>` block (~line 129):

```html
<div id="stats-panel">
  <h3>Surveillance par famille politique</h3>
  <div id="stats-table"></div>
  <div id="stats-summary" class="stats-summary"></div>
  <div class="stats-note" id="stats-note"></div>
</div>
```

**Step 4: Add surveillance filters HTML**

Add right after `<div id="filter-bar"></div>` (line 87):

```html
<div id="surv-filters">
  <label>
    Seuil ratio :
    <input type="range" id="ratio-slider" min="0" max="50" value="0" step="1">
    <span class="slider-value" id="ratio-value">0</span> /10k hab
  </label>
  <label>
    <input type="checkbox" id="vs-only">
    Videoprotection uniquement
  </label>
  <label>
    <input type="checkbox" id="data-only">
    Avec donnees uniquement
  </label>
</div>
```

**Step 5: Add population + ratio fields to info panel**

In the `#info-surv-row` div (lines 124-128), add population and ratio rows:

```html
<div class="detail" id="info-surv-row" style="display:none; margin-top:6px; padding-top:6px; border-top:1px solid #eee;">
  <div><strong>Police mun. :</strong> <span id="info-pm"></span></div>
  <div><strong>ASVP :</strong> <span id="info-asvp"></span></div>
  <div><strong>Population :</strong> <span id="info-pop"></span></div>
  <div><strong>Ratio /10k :</strong> <span id="info-ratio"></span></div>
  <div><strong>Videoprot. :</strong> <span id="info-vs"></span></div>
</div>
```

**Step 6: Verify in browser**

Open `index.html`. Mode toggle visible top-left. New elements present but inactive. No JS errors in console.

**Step 7: Commit**

```bash
git add index.html
git commit -m "feat: add mode toggle, stats panel, and surveillance filter UI elements"
```

---

### Task 3: Implement surveillance style function and mode switching

**Files:**
- Modify: `index.html` (JavaScript section)

**Step 1: Add mode state and surveillance color scale**

Add right after `var activeFilter = null;` (~line 219):

```javascript
  var currentMode = 'politique';

  // Surveillance heatmap: yellow → orange → red → dark red
  var SURV_COLORS = [
    { threshold: 0,  color: '#FFFFB2' },
    { threshold: 5,  color: '#FED976' },
    { threshold: 10, color: '#FEB24C' },
    { threshold: 20, color: '#FD8D3C' },
    { threshold: 30, color: '#FC4E2A' },
    { threshold: 50, color: '#E31A1C' },
    { threshold: 100, color: '#B10026' }
  ];

  function getSurvColor(ratio) {
    if (ratio === undefined || ratio === null) return '#444';
    for (var i = SURV_COLORS.length - 1; i >= 0; i--) {
      if (ratio >= SURV_COLORS[i].threshold) return SURV_COLORS[i].color;
    }
    return SURV_COLORS[0].color;
  }

  var survFilters = { ratioMin: 0, vsOnly: false, dataOnly: false };
```

**Step 2: Rename existing getStyle to getStylePolitique**

Rename `function getStyle(feature)` to `function getStylePolitique(feature)` — keep the exact same body.

**Step 3: Add getStyleSurveillance function**

Add right after `getStylePolitique`:

```javascript
  function getStyleSurveillance(feature) {
    var code = feature.properties.codgeo;
    var s = surv[code];
    var m = maires[code];

    if (!s) {
      if (survFilters.dataOnly) return { fillOpacity: 0, weight: 0, opacity: 0 };
      return { fillColor: '#444', fillOpacity: 0.15, weight: 0.2, color: '#222', opacity: 0.3 };
    }

    var ratio = s.r || 0;
    var hasVS = !!s.vs;

    if (survFilters.vsOnly && !hasVS)
      return { fillColor: '#444', fillOpacity: 0.15, weight: 0.2, color: '#222', opacity: 0.3 };
    if (ratio < survFilters.ratioMin)
      return { fillColor: '#444', fillOpacity: 0.15, weight: 0.2, color: '#222', opacity: 0.3 };
    if (activeFilter && m && m.f !== activeFilter)
      return { fillColor: '#333', fillOpacity: 0.15, weight: 0.2, color: '#111', opacity: 0.3 };

    return {
      fillColor: getSurvColor(ratio),
      fillOpacity: 0.85,
      weight: hasVS ? 2 : 0.3,
      color: hasVS ? '#ffffff' : '#333',
      opacity: hasVS ? 0.9 : 0.4
    };
  }
```

**Step 4: Add delegating getStyle**

```javascript
  function getStyle(feature) {
    if (currentMode === 'surveillance') return getStyleSurveillance(feature);
    return getStylePolitique(feature);
  }
```

**Step 5: Implement switchMode()**

Add after filter button setup, and wire up mode toggle button clicks:

```javascript
  // Mode toggle click handlers
  var modeButtons = document.querySelectorAll('.mode-btn');
  for (var i = 0; i < modeButtons.length; i++) {
    modeButtons[i].addEventListener('click', (function(btn) {
      return function() { switchMode(btn.getAttribute('data-mode')); };
    })(modeButtons[i]));
  }

  function switchMode(mode) {
    currentMode = mode;
    var btns = document.querySelectorAll('.mode-btn');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].getAttribute('data-mode') === mode);
    }

    document.getElementById('filter-bar').style.display = mode === 'politique' ? 'flex' : 'none';
    document.getElementById('surv-filters').style.display = mode === 'surveillance' ? 'flex' : 'none';
    document.getElementById('stats-panel').style.display = mode === 'surveillance' ? 'block' : 'none';
    document.getElementById('info').style.display = 'none';
    document.body.classList.toggle('surv-mode', mode === 'surveillance');

    document.querySelector('#title-bar p').textContent =
      mode === 'surveillance'
        ? 'Effectifs police municipale et videoprotection'
        : 'Nuance politique du maire \u2014 Municipales 2020';

    renderLegend(mode);
    geoLayer.setStyle(getStyle);
    if (mode === 'surveillance') renderStats();
  }
```

**Step 6: Implement renderLegend()**

Uses safe DOM methods (no innerHTML):

```javascript
  function renderLegend(mode) {
    var legendItemsEl = document.getElementById('legend-items');
    var legendSurvEl = document.getElementById('legend-surv');
    var legendTitle = document.querySelector('#legend h3');

    if (mode === 'politique') {
      // Rebuild political legend items (they were cleared when switching to surveillance)
      legendItemsEl.textContent = '';
      FAMILLES.forEach(function(f) {
        var item = document.createElement('div');
        item.className = 'legend-item';

        var swatch = document.createElement('div');
        swatch.className = 'legend-swatch';
        swatch.style.background = f.color;
        if (f.key === 'Non class\u00e9') swatch.style.opacity = '0.4';

        var label = document.createElement('span');
        label.className = 'legend-label';
        label.textContent = f.label;

        var countEl = document.createElement('span');
        countEl.className = 'legend-count';
        countEl.textContent = (familleCounts[f.key] || 0).toLocaleString('fr');

        item.appendChild(swatch);
        item.appendChild(label);
        item.appendChild(countEl);

        item.addEventListener('click', (function(famille) {
          return function() { activeFilter = famille; updateFilter(); };
        })(f.key));

        legendItemsEl.appendChild(item);
      });

      legendSurvEl.style.display = 'block';
      legendTitle.textContent = 'Famille politique';
      return;
    }

    // Surveillance mode legend
    legendSurvEl.style.display = 'none';
    legendTitle.textContent = 'Intensite surveillance';
    legendItemsEl.textContent = '';

    SURV_COLORS.forEach(function(sc) {
      var item = document.createElement('div');
      item.className = 'legend-item';
      item.style.cursor = 'default';

      var swatch = document.createElement('div');
      swatch.className = 'legend-swatch';
      swatch.style.background = sc.color;

      var label = document.createElement('span');
      label.className = 'legend-label';
      label.textContent = sc.threshold === 0 ? '< 5 agents/10k hab' :
                           sc.threshold === 100 ? '100+ agents/10k hab' :
                           sc.threshold + '+ agents/10k hab';

      item.appendChild(swatch);
      item.appendChild(label);
      legendItemsEl.appendChild(item);
    });

    // Video surveillance indicator
    var vsItem = document.createElement('div');
    vsItem.className = 'legend-item';
    vsItem.style.cssText = 'margin-top:8px;padding-top:8px;border-top:1px solid #ddd;cursor:default;';

    var vsBox = document.createElement('div');
    vsBox.style.cssText = 'width:16px;height:16px;border:3px solid white;border-radius:3px;background:#666;margin-right:8px;box-shadow:0 0 2px rgba(0,0,0,0.5);';
    var vsLabel = document.createElement('span');
    vsLabel.className = 'legend-label';
    vsLabel.textContent = 'Videoprotection';
    vsItem.appendChild(vsBox);
    vsItem.appendChild(vsLabel);
    legendItemsEl.appendChild(vsItem);

    // Data note
    var noteDiv = document.createElement('div');
    noteDiv.style.cssText = 'margin-top:8px;font-size:10px;color:#999;line-height:1.4;';
    noteDiv.textContent = 'Police mun. : donnees 2024 | Videoprot. : donnees 2012 | Pop. : INSEE';
    legendItemsEl.appendChild(noteDiv);
  }
```

**Step 7: Implement updateSurvFilters()**

Wire up filter controls with event listeners (add after mode toggle setup):

```javascript
  document.getElementById('ratio-slider').addEventListener('input', updateSurvFilters);
  document.getElementById('vs-only').addEventListener('change', updateSurvFilters);
  document.getElementById('data-only').addEventListener('change', updateSurvFilters);

  function updateSurvFilters() {
    survFilters.ratioMin = parseInt(document.getElementById('ratio-slider').value);
    survFilters.vsOnly = document.getElementById('vs-only').checked;
    survFilters.dataOnly = document.getElementById('data-only').checked;
    document.getElementById('ratio-value').textContent = survFilters.ratioMin;

    geoLayer.setStyle(getStyle);
    if (currentMode === 'surveillance') renderStats();
  }
```

**Step 8: Update showInfo() for population and ratio**

Update the `showInfo` function to populate the new info fields:

```javascript
  function showInfo(feature) {
    var code = feature.properties.codgeo;
    var m = maires[code];
    if (!m) return;
    document.getElementById('info-name').textContent = m.n + ' (' + code + ')';
    document.getElementById('info-maire').textContent = m.m || '\u2014';
    document.getElementById('info-nuance').textContent = m.lb + ' (' + m.nu + ')';
    document.getElementById('info-famille').textContent = m.f;
    infoPanel.style.display = 'block';

    var s = surv[code];
    var survRow = document.getElementById('info-surv-row');
    if (s) {
      survRow.style.display = 'block';
      document.getElementById('info-pm').textContent = (s.pm || 0) + ' agents';
      document.getElementById('info-asvp').textContent = (s.asvp || 0) + ' agents';
      document.getElementById('info-pop').textContent = s.pop ? s.pop.toLocaleString('fr') + ' hab.' : 'N/A';
      document.getElementById('info-ratio').textContent = s.r ? s.r + ' agents/10k hab' : 'N/A';
      document.getElementById('info-vs').textContent = s.vs ? 'Oui (2012)' : 'Non repertoriee';
    } else {
      survRow.style.display = 'none';
    }
  }
```

**Step 9: Verify in browser**

Open `index.html`, click "Vue surveillance":
- Map shows yellow→red heatmap
- Communes without data are grey/transparent
- Legend shows heatmap scale
- Filter bar switches to slider + checkboxes
- Slider/checkboxes filter the map
- Hover shows population + ratio
- Click "Vue politique" returns to normal

**Step 10: Commit**

```bash
git add index.html
git commit -m "feat: implement surveillance mode with heatmap, mode toggle, filters, and legend"
```

---

### Task 4: Build statistics sidebar

**Files:**
- Modify: `index.html` (JavaScript section)

**Step 1: Implement computeStats()**

Add in the JavaScript section:

```javascript
  function computeStats() {
    var stats = {};
    FAMILLES.forEach(function(f) {
      if (f.key === 'Non class\u00e9') return;
      stats[f.key] = { label: f.label, color: f.color, count: 0, totalRatio: 0, ratioCount: 0, vsCount: 0 };
    });

    for (var code in surv) {
      var s = surv[code];
      var m = maires[code];
      if (!m || m.f === 'Non class\u00e9' || !stats[m.f]) continue;
      if (survFilters.vsOnly && !s.vs) continue;
      if (s.r !== undefined && s.r < survFilters.ratioMin) continue;
      if (activeFilter && m.f !== activeFilter) continue;

      var fam = stats[m.f];
      fam.count++;
      if (s.r !== undefined) { fam.totalRatio += s.r; fam.ratioCount++; }
      if (s.vs) fam.vsCount++;
    }
    return stats;
  }
```

**Step 2: Implement renderStats()**

Uses safe DOM construction (no innerHTML):

```javascript
  function renderStats() {
    var stats = computeStats();
    var tableEl = document.getElementById('stats-table');
    var summaryEl = document.getElementById('stats-summary');
    var noteEl = document.getElementById('stats-note');

    // Build table with DOM methods
    tableEl.textContent = '';
    var table = document.createElement('table');
    var thead = document.createElement('thead');
    var headerRow = document.createElement('tr');
    ['Famille', 'Communes', 'Moy. ratio', '% videoprot.'].forEach(function(text) {
      var th = document.createElement('th');
      th.textContent = text;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    var tbody = document.createElement('tbody');
    var maxRatio = 0, maxFam = '', minRatio = Infinity, minFam = '';
    var totalCommunes = 0;

    FAMILLES.forEach(function(f) {
      if (f.key === 'Non class\u00e9') return;
      var s = stats[f.key];
      if (!s) return;

      var avgRatio = s.ratioCount > 0 ? (s.totalRatio / s.ratioCount) : 0;
      var vsPct = s.count > 0 ? Math.round(s.vsCount / s.count * 100) : 0;
      totalCommunes += s.count;

      if (avgRatio > maxRatio && s.ratioCount > 0) { maxRatio = avgRatio; maxFam = f.label; }
      if (avgRatio < minRatio && s.ratioCount > 0) { minRatio = avgRatio; minFam = f.label; }

      var tr = document.createElement('tr');
      tr.className = 'clickable';
      if (activeFilter === f.key) tr.style.fontWeight = '700';

      tr.addEventListener('click', (function(famille) {
        return function() {
          activeFilter = famille;
          updateFilter();
          if (currentMode === 'surveillance') renderStats();
        };
      })(f.key));

      // Family cell with color swatch
      var tdFam = document.createElement('td');
      var swatch = document.createElement('span');
      swatch.style.cssText = 'display:inline-block;width:10px;height:10px;border-radius:2px;background:' + f.color + ';margin-right:4px;vertical-align:middle;';
      tdFam.appendChild(swatch);
      tdFam.appendChild(document.createTextNode(f.label));

      var tdCount = document.createElement('td');
      tdCount.textContent = s.count;

      var tdRatio = document.createElement('td');
      tdRatio.textContent = s.ratioCount > 0 ? avgRatio.toFixed(1) : '-';

      var tdVs = document.createElement('td');
      tdVs.textContent = s.count > 0 ? vsPct + '%' : '-';

      tr.appendChild(tdFam);
      tr.appendChild(tdCount);
      tr.appendChild(tdRatio);
      tr.appendChild(tdVs);
      tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    tableEl.appendChild(table);

    // Summary
    summaryEl.textContent = '';
    if (maxRatio > 0 && minRatio < Infinity && maxFam !== minFam) {
      var diff = Math.round((maxRatio / minRatio - 1) * 100);
      var strong1 = document.createElement('strong');
      strong1.textContent = maxFam;
      var strong2 = document.createElement('strong');
      strong2.textContent = minFam;

      summaryEl.appendChild(strong1);
      summaryEl.appendChild(document.createTextNode(
        ' a le ratio le plus eleve (' + maxRatio.toFixed(1) + '/10k hab), ' +
        (diff > 0 ? diff + '% de plus que ' : 'similaire a ')
      ));
      summaryEl.appendChild(strong2);
      summaryEl.appendChild(document.createTextNode(' (' + minRatio.toFixed(1) + '/10k hab).'));
    }

    // Note
    noteEl.textContent = 'Base sur ' + totalCommunes + ' communes avec donnees surveillance et nuance politique attribuee. ' +
      'Les communes "Non classe" (92% du total) sont exclues. Sources : police mun. 2024, videoprot. 2012, pop. INSEE.';
  }
```

**Step 3: Verify in browser**

Switch to "Vue surveillance":
- Stats sidebar appears on the right with table
- 5 political families shown with counts, avg ratio, % vidéosurveillance
- Summary sentence compares highest/lowest
- Click a table row to filter map to that family
- Adjust slider/checkboxes — stats update in real time

**Step 4: Commit**

```bash
git add index.html
git commit -m "feat: add statistics sidebar with political correlation data"
```

---

### Task 5: Final polish and end-to-end verification

**Files:**
- Modify: `index.html`

**Step 1: Ensure layout consistency**

Verify and adjust if needed:
- Mode toggle doesn't overlap title bar (top: 70px)
- Info panel moves to bottom-right in surveillance mode (`.surv-mode #info` CSS)
- Stats panel scrolls properly on small viewports (max-height + overflow-y)
- Surveillance filters bar is centered and visible

**Step 2: Full manual test**

Complete walkthrough:
1. Load page — political mode works exactly as before (regression check)
2. Click "Vue surveillance" — heatmap appears, stats sidebar shows, filters switch
3. Move ratio slider — communes below threshold grey out, stats recalculate
4. Check "Videoprotection uniquement" — only camera communes colored
5. Check "Avec donnees uniquement" — no-data communes disappear
6. Click stats table row — map filters to that family
7. Hover communes — info panel shows population, ratio, political family
8. Click "Vue politique" — everything returns to normal, legend restored
9. Verify filter buttons still work in political mode

**Step 3: Fix any issues found during testing**

Address any layout, interaction, or data display bugs.

**Step 4: Commit**

```bash
git add index.html
git commit -m "feat: polish mode switching, layout, and responsive adjustments"
```

---

### Task 6 (Optional): Search for newer videosurveillance data

**Files:**
- Potentially modify: `process_surveillance.py`

**Step 1: Research newer data sources**

Search data.gouv.fr for "videoprotection" or "videosurveillance" datasets more recent than 2012. Check CNIL open data, Ministere de l'Interieur datasets.

**Step 2: If found, update the script**

Update `VIDEOSURV_URL` and adjust parsing if format changed. Update year references in the UI.

**Step 3: If not found**

Keep 2012 data — the UI already clearly labels the data vintage.

**Step 4: Commit if changes made**

```bash
git add process_surveillance.py surveillance.json index.html
git commit -m "feat: update videosurveillance data source to [year]"
```
