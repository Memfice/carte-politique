# Methodologie et sources de donnees

Ce document decrit l'ensemble des donnees utilisees par la carte, leurs sources, les calculs appliques, et les limites connues. L'objectif est de permettre a chaque utilisateur de comprendre ce qu'il voit, de challenger les choix faits, et de proposer des ameliorations.

---

## Vue d'ensemble

La carte couvre **34 844 communes** de France metropolitaine et d'outre-mer. Elle propose quatre modes de visualisation :

| Mode | Ce qu'il montre | Donnees utilisees |
|------|----------------|-------------------|
| **Politique** | Couleur politique du maire (municipales 2020) | `maires.json` |
| **Surveillance** | Densite de police municipale (agents / 10k hab.) | `surveillance.json` |
| **Securite** | Taux de delinquance enregistree / 10k hab. | `delinquance.json` |
| **Prospection** | Score composite de potentiel pour la videoverbalisation | `prospection.json` |

Les **fiches communes** (clic sur une commune) affichent toutes les donnees disponibles quel que soit le mode actif : politique, surveillance, delinquance, finances, revenus, QPV. Chaque donnee est accompagnee d'un **badge de fraicheur** colore indiquant l'annee de la source.

---

## 1. Donnees politiques — `maires.json`

### Source

- **Nuances politiques** : fichier `nuances-communes.csv` du Ministere de l'Interieur, attribue apres les elections municipales de 2020
- **Noms des maires** : Repertoire National des Elus (RNE), fichier `elus-maires.csv` (data.gouv.fr)

### Contenu par commune

| Champ | Description | Exemple |
|-------|-------------|---------|
| `n` | Nom de la commune | "Carcassonne" |
| `nu` | Code nuance politique | "LSOC" |
| `f` | Famille politique | "Gauche" |
| `cl` | Couleur hexadecimale | "#E2001A" |
| `lb` | Label lisible de la nuance | "Socialiste" |
| `m` | Nom du maire (si disponible) | "Gerard Larrat" |

### Familles politiques

Les nuances sont regroupees en 6 familles :

| Famille | Couleur | Communes | % du total |
|---------|---------|----------|------------|
| Non classe | #CCCCCC | 32 151 | 92,3% |
| Droite | #0056A6 | 1 075 | 3,1% |
| Gauche | #E2001A | 820 | 2,4% |
| Centre | #FFB300 | 407 | 1,2% |
| Courants politiques divers | #9E9E9E | 380 | 1,1% |
| Extreme droite | #0D1B4A | 11 | 0,03% |

### Limite importante

**92,3% des communes sont "Non classe".** Ce n'est pas un bug : le Ministere n'attribue des nuances politiques qu'aux communes de plus de 1 000 habitants (scrutin de liste). Les ~32 000 communes a scrutin majoritaire n'ont pas de nuance officielle. La carte est donc essentiellement grise en mode politique — seules 2 693 communes ont une couleur.

### Jointure entre les fichiers

Le RNE et le fichier de nuances sont joints par **code INSEE de la commune** (5 caracteres, ex: "11069" pour Carcassonne). Le matching est direct, sans ambiguite.

---

## 2. Donnees de surveillance — `surveillance.json`

### Sources

| Donnee | Source | Annee | Format | URL |
|--------|--------|-------|--------|-----|
| Effectifs police municipale | Ministere de l'Interieur | 2024 | ODS | [data.gouv.fr](https://www.data.gouv.fr/api/1/datasets/r/081e94fe-b257-4ae7-bc31-bf1f2eb6c968) |
| Population legale | INSEE | 2021 | XLSX | [data.gouv.fr](https://www.data.gouv.fr/api/1/datasets/r/be303501-5c46-48a1-87b4-3d198423ff49) |

### Contenu par commune

| Champ | Description | Exemple |
|-------|-------------|---------|
| `pm` | Nombre d'agents de police municipale | 30 |
| `asvp` | Nombre d'agents de surveillance de voie publique | 20 |
| `pop` | Population (INSEE 2021) | 46 080 |
| `r` | Ratio agents / 10 000 habitants (plafonne a 50) | 10.9 |
| `r_raw` | Ratio brut avant plafonnement (uniquement si > 50) | 544.5 |

### Calcul du ratio

```
ratio = (pm + asvp) / population * 10 000
```

Le ratio est **plafonne a 50 agents pour 10 000 habitants**. Au-dela, la valeur brute est conservee dans `r_raw` pour transparence. Ce plafonnement concerne 51 communes, principalement des petites communes touristiques (Saint-Tropez, Les Baux-de-Provence, etc.) ou le nombre d'agents est disproportionne par rapport a la population permanente.

**Pourquoi plafonner ?** Sans plafonnement, quelques communes extremes (Lirac : 544, Riboux : 392) ecrasent l'echelle de couleur et rendent toutes les autres communes visuellement identiques. Le plafond a 50 preserve la lisibilite de la heatmap.

### Couverture

- **4 164 communes** sur 34 844 ont des donnees (12%)
- Les 30 680 communes restantes n'ont ni police municipale ni ASVP dans les donnees du Ministere
- La carte distingue visuellement "pas de donnees" (bordure pointillee) de "donnees = 0 agents" (fond sombre)

### Jointure

Le fichier du Ministere ne contient pas de code INSEE mais un **nom de commune + numero de departement**. La jointure se fait par matching normalise des noms :
- Suppression des accents (NFD + strip diacritiques)
- Majuscules
- Remplacement tirets, apostrophes par des espaces
- Expansion "ST" → "SAINT", "STE" → "SAINTE"
- Suppression du texte entre parentheses

Resultat : 4 167 communes matchees sur ~4 576 lignes (91%). Les 409 non matchees sont principalement des EPCI (intercommunalites) et des communes recemment fusionnees dont le nom a change.

### Limites

- **Population permanente vs. population reelle** : les communes touristiques ont un ratio surevalue car leurs agents servent une population saisonniere bien superieure
- **Effectifs ≠ ETP** : le fichier compte les agents, pas les equivalents temps plein
- **Pas de police nationale/gendarmerie** : seule la police municipale est comptee, pas les forces etatiques

---

## 3. Donnees de prospection — `prospection.json`

Le mode prospection calcule un **score de 0 a 100** estimant le potentiel d'une commune pour la videoverbalisation. Ce score est la moyenne ponderee de 6 signaux, chacun normalise entre 0 et 1.

### Sources de donnees

| Donnee | Source | Annee | Communes | URL |
|--------|--------|-------|----------|-----|
| Effectifs PM multi-annees | Min. Interieur | 2019, 2021, 2024 | 4 964 | data.gouv.fr (ODS/XLSX) |
| Stationnement payant | GART / Cerema | 2019 | 226 | [data.gouv.fr](https://static.data.gouv.fr/resources/enquete-sur-la-reforme-du-stationnement-payant-sur-voirie/20200207-161331/stt-voirie-payant-opendata-v2.csv) |
| Videoverbalisation | video-verbalisation.fr | 2025 | 586 | [video-verbalisation.fr/villes.php](https://video-verbalisation.fr/villes.php) |
| Accidents routiers | ONISR (BAAC) | 2023-2024 | 16 064 | [data.gouv.fr](https://static.data.gouv.fr/resources/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024/20251021-115900/caract-2024.csv) |
| Population | INSEE | 2021 | 4 145 | via surveillance.json |
| PM courant | Min. Interieur | 2024 | 4 164 | via surveillance.json |
| DGF par habitant | DGFiP | 2022 | ~35 000 | via enrichment.json |

### Contenu par commune

| Champ | Description | Exemple |
|-------|-------------|---------|
| `pm_trend` | Tableau des effectifs totaux (PM+ASVP) par annee | [7, 12, 15] |
| `pm_trend_years` | Annees correspondantes | [2019, 2021, 2024] |
| `stat_payant` | Commune avec stationnement payant | true |
| `stat_payant_year` | Annee de la donnee | 2019 |
| `videoverb` | Commune equipee en videoverbalisation | true |
| `videoverb_year` | Annee de la donnee | 2025 |
| `accidents` | Nombre d'accidents corporels (2 ans cumules) | 266 |
| `accidents_years` | Periode | "2023-2024" |
| `pop` | Population (INSEE) | 46 080 |
| `pm` | Agents PM actuels | 10 |
| `asvp` | Agents ASVP actuels | 2 |

---

## 4. Donnees de delinquance — `delinquance.json`

### Source

- **Dataset** : Bases statistiques communales de la delinquance enregistree par la police et la gendarmerie nationales
- **Editeur** : Service statistique ministeriel de la securite interieure (SSMSI), Ministere de l'Interieur
- **Format** : fichier Parquet (~14 MB)
- **Annee des donnees** : 2024 (derniere annee disponible dans le fichier)
- **URL** : [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/bases-statistiques-communale-departementale-et-regionale-de-la-delinquance-enregistree-par-la-police-et-la-gendarmerie-nationales/)

### Categories de delits

Le dataset contient 15 categories, chacune associee a une unite de comptage privilegiee pour eviter les doublons (un meme fait peut etre compte en "infractions" et en "victimes") :

| Categorie | Cle courte | Unite retenue |
|-----------|-----------|---------------|
| Cambriolages de logement | `cambr` | Infraction |
| Destructions et degradations volontaires | `destr` | Infraction |
| Escroqueries et fraudes aux moyens de paiement | `escro` | Infraction |
| Trafic de stupefiants | `traf_stup` | Infraction |
| Usage de stupefiants | `usage_stup` | Mis en cause |
| Usage de stupefiants (AFD) | `usage_stup_afd` | Mis en cause |
| Violences physiques hors cadre familial | `viol_phys` | Victime |
| Violences physiques intrafamiliales | `viol_intraf` | Victime |
| Violences sexuelles | `viol_sex` | Victime |
| Vols avec armes | `vols_armes` | Victime |
| Vols d'accessoires sur vehicules | `vols_acc_veh` | Infraction |
| Vols dans les vehicules | `vols_ds_veh` | Infraction |
| Vols de vehicule | `vols_veh` | Vehicule |
| Vols sans violence contre des personnes | `vols_sv` | Victime |
| Vols violents sans arme | `vols_viol` | Victime |

### Contenu par commune

| Champ | Description | Exemple |
|-------|-------------|---------|
| `total` | Nombre total de faits toutes categories | 259 403 |
| `cats` | Objet avec une cle par categorie | `{"cambr": 12889, "vols_sv": 91234, ...}` |
| `pop` | Population de la commune | 2 114 461 |
| `r` | Ratio total / 10 000 habitants | 1227.2 |
| `year` | Annee des donnees | "2024" |

### Calcul du ratio

```
ratio = total / population * 10 000
```

Le ratio n'est **pas plafonne** (contrairement au mode surveillance) car la distribution est plus homogene.

En mode securite, le ratio peut etre calcule **par categorie** (filtrage par pills) :

```
ratio_categorie = cats[categorie] / population * 10 000
```

### Couverture et seuil de diffusion

- **~9 400 communes** sur 34 844 ont des donnees (27%)
- Le SSMSI applique un **seuil de diffusion** : les communes en dessous d'un certain seuil de population (environ 2 000 habitants) voient leurs donnees masquees (`nombre = NaN` dans le fichier source). Ce masquage vise a proteger l'anonymat des victimes dans les petites communes
- Seules les lignes avec un nombre diffuse sont retenues dans `delinquance.json`
- Les communes sans donnees apparaissent en gris transparent en mode securite

### Jointure

Le fichier parquet contient directement un **code INSEE a 5 chiffres** (colonne `CODGEO_2025`, geographie 2025). La jointure est directe, sans ambiguite.

### Limites

- **Seuil de diffusion** : les petites communes n'ont pas de donnees, ce qui biaise les analyses geographiques (les zones rurales sont absentes)
- **Faits enregistres ≠ faits commis** : seuls les faits portes a la connaissance de la police/gendarmerie sont comptabilises. Le "chiffre noir" (faits non declares) varie fortement selon les categories (ex: violences intrafamiliales sous-declarees)
- **Population permanente** : comme pour la surveillance, le ratio est rapporte a la population legale, pas a la population reelle (tourisme, navetteurs)
- **Paris, Lyon, Marseille** : ces communes utilisent un code commune global (75056, 69123, 13055) qui agrege tous les arrondissements

---

## 5. Donnees d'enrichissement — `enrichment.json`

Donnees socio-economiques et de politique de la ville utilisees pour enrichir les fiches communes et le scoring prospection.

### Sources

| Donnee | Source | Annee | Format | Communes | URL |
|--------|--------|-------|--------|----------|-----|
| QPV (Quartiers Prioritaires) | ANCT | 2024 | CSV | 843 | [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/quartiers-prioritaires-de-la-politique-de-la-ville-qpv/) |
| Comptes individuels communes | DGFiP (Min. Economie) | 2022 | JSON | ~35 000 | [data.economie.gouv.fr](https://data.economie.gouv.fr/explore/dataset/comptes-individuels-des-communes-fichier-global-2022/) |
| Revenus medians | Filosofi / INSEE | 2021 | CSV (zip) | ~31 000 | [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/principaux-indicateurs-sur-la-pauvrete-en-2021-niveau-de-vie-taux-de-pauvrete-part-des-menages-imposes-et-decomposition-du-revenu-disponible) |

### Contenu par commune

| Champ | Description | Source | Exemple |
|-------|-------------|--------|---------|
| `qpv` | Nombre de Quartiers Prioritaires dans la commune | ANCT 2024 | 3 |
| `dgf_hab` | Dotation Globale de Fonctionnement par habitant (EUR) | DGFiP 2022 | 104.5 |
| `dette_hab` | Dette par habitant (EUR) | DGFiP 2022 | 666.7 |
| `cafn_hab` | Capacite d'autofinancement nette par habitant (EUR) | DGFiP 2022 | -17.3 |
| `perso_hab` | Charges de personnel par habitant (EUR) | DGFiP 2022 | 452.2 |
| `rev_med` | Revenu median par unite de consommation (EUR) | Filosofi 2021 | 29 730 |
| `tx_pauv` | Taux de pauvrete (%) | Filosofi 2021 | 16.0 |

### QPV — Quartiers Prioritaires de la Politique de la Ville

Le fichier QPV de l'ANCT liste chaque quartier prioritaire avec son code INSEE de commune. Le script compte le nombre de QPV par commune. **843 communes** sont concernees par au moins un QPV.

Dans l'interface :
- **Fiche commune** : badge "QPV" avec le nombre de quartiers
- **Mode prospection** : filtre "Communes avec QPV uniquement"

### DGFiP — Comptes individuels des communes

Les comptes individuels du Ministere de l'Economie (DGFiP) fournissent les indicateurs financiers par habitant. Le fichier source utilise un code departement (3 caracteres) + code commune (3 caracteres) qui sont concatenes pour reconstituer le code INSEE a 5 chiffres.

### Revenus — Filosofi 2021

Les revenus medians et taux de pauvrete proviennent du dispositif Filosofi de l'INSEE (millesime 2021). Le fichier source est un CSV long (une ligne par commune et par indicateur) distribue en zip via l'API INSEE/data.gouv.fr. Deux mesures sont extraites : `MED_SL` (niveau de vie median, EUR/an) et `PR_MD60` (taux de pauvrete a 60 % de la mediane, %). Le taux de pauvrete n'est disponible que pour les communes de taille suffisante (~4 350 communes) ; les petites communes sont soumises au secret statistique.

### Integration dans la fiche commune

La fiche commune affiche une section "Contexte socio-economique" avec :
- Revenu median (badge fraicheur — 2021)
- DGF, dette, CAF nette, charges de personnel par habitant (badges fraicheur jaune — 2022)
- Badge QPV (si applicable)

---

## 6. Score de prospection — formule complete

### Les 6 signaux

Chaque signal est une valeur entre 0 et 1. Le score final est la moyenne ponderee de ces signaux, ramenee sur 100.

---

#### Signal 1 : Stationnement payant (poids : 30%)

```
signal = 1 si la commune a du stationnement payant, 0 sinon
```

**Source** : enquete GART/Cerema 2019 sur la reforme du stationnement payant sur voirie. CSV avec code INSEE direct.

**Logique** : une commune avec du stationnement payant a un besoin concret de verbalisation (constat d'infractions, emission de FPS). C'est le signal le plus directement lie au marche de la videoverbalisation.

**Limite connue** : l'enquete ne couvre que **226 communes** ayant repondu. En realite, plus de 800 communes ont du stationnement payant en France. Le signal sous-estime fortement la realite. C'est la donnee la plus incomplete du jeu.

---

#### Signal 2 : Effectif police municipale (poids : 20%)

```
signal = min((pm + asvp) / population * 10 000 / 50, 1)
```

**Source** : effectifs PM par commune, Ministere de l'Interieur 2024.

**Logique** : plus une commune a d'agents de police municipale rapportes a sa population, plus elle investit dans la securite de proximite, et plus elle est susceptible d'investir dans des outils de videoverbalisation.

**Normalisation** : le ratio est divise par 50 (seuil haut observe) et plafonne a 1. Une commune avec 25 agents pour 10 000 habitants obtient un signal de 0,5.

**Limite** : ne capture pas la gendarmerie/police nationale. Une commune avec peu de PM mais une forte presence etatique apparait comme faiblement dotee.

---

#### Signal 3 : Croissance des effectifs PM (poids : 10%)

```
si effectif_2019 > 0 :
    taux_croissance = max((effectif_2024 - effectif_2019) / effectif_2019, 0)
sinon :
    taux_croissance = 1 si effectif_2024 > 0, 0 sinon

signal = min(taux_croissance * sqrt(effectif_2024) / 5, 1)
```

**Source** : croisement des fichiers PM de 2019, 2021 et 2024. On utilise le premier et le dernier point de la serie disponible pour chaque commune.

**Logique** : une commune qui augmente ses effectifs est en dynamique d'investissement securitaire. Le taux de croissance est **pondere par la racine carree de l'effectif actuel** pour eviter que les petites variations dominent.

**Exemples concrets** :

| Commune | 2019 | 2024 | Taux | Signal |
|---------|------|------|------|--------|
| Passe de 0 a 1 agent | 0 | 1 | 100% | 0,20 |
| Passe de 1 a 2 agents | 1 | 2 | 100% | 0,28 |
| Passe de 10 a 20 agents | 10 | 20 | 100% | 0,89 |
| Passe de 20 a 40 agents | 20 | 40 | 100% | 1,00 |
| Passe de 30 a 30 agents | 30 | 30 | 0% | 0,00 |

Sans la ponderation par le volume, "0 a 1 agent" et "10 a 20 agents" auraient le meme signal (1,0) alors que le second represente un investissement bien plus significatif.

---

#### Signal 4 : Accidents routiers (poids : 15%)

```
signal = min(accidents_2ans / population * 10 000 / 30, 1)
```

**Source** : base de donnees BAAC (Bulletins d'Analyse des Accidents Corporels), ONISR, fichiers `caract-2023.csv` et `caract-2024.csv` publies sur data.gouv.fr. Chaque ligne correspond a un accident corporel avec le code INSEE de la commune.

**Logique** : un taux d'accidents eleve indique un besoin de securisation routiere — argument de vente direct pour la videoverbalisation. On cumule 2 annees (2023 + 2024, soit ~109 000 accidents) pour lisser les variations annuelles.

**Normalisation** : le nombre d'accidents est rapporte a la population pour 10 000 habitants, puis divise par 30 et plafonne a 1.

**Couverture** : 16 064 communes ont au moins un accident corporel sur la periode. Les communes sans accident ne sont pas penalisees — leur signal est simplement 0.

**Limite** : seuls les accidents **corporels** (avec blesses ou tues) sont comptabilises. Les accidents materiels ne figurent pas dans la base BAAC. Le nombre reel d'incidents de circulation est donc bien superieur.

---

#### Signal 5 : Taille de la commune (poids : 25%)

```
signal = exp(-0.5 * ((ln(population) - ln(30 000)) / 1.2)^2)
```

C'est une **courbe gaussienne en echelle logarithmique**, centree sur 30 000 habitants avec un ecart-type (sigma) de 1,2.

**Source** : population legale INSEE 2021.

**Logique** : les communes entre 5 000 et 100 000 habitants sont la cible ideale :
- Trop petites (< 3 000) : pas assez de budget ni de besoins
- Trop grandes (> 200 000) : generalement deja equipees, marches plus complexes
- Le "sweet spot" est autour de 30 000 habitants

**Valeurs du signal** :

| Population | Signal |
|-----------|--------|
| 1 000 | 0,06 |
| 5 000 | 0,36 |
| 10 000 | 0,64 |
| 20 000 | 0,92 |
| 30 000 | 1,00 |
| 50 000 | 0,92 |
| 100 000 | 0,64 |
| 200 000 | 0,36 |
| 500 000 | 0,08 |

---

#### Signal 6 : Capacite budgetaire (poids par defaut : 0%)

```
signal = min(dgf_hab / 500, 1)
```

**Source** : DGF par habitant (DGFiP 2022), via `enrichment.json`.

**Logique** : une commune avec une dotation globale de fonctionnement elevee par habitant dispose de marges budgetaires plus importantes pour investir dans des equipements de videoverbalisation.

**Normalisation** : le montant DGF/hab est divise par 500 EUR et plafonne a 1. Une commune recevant 250 EUR/hab obtient un signal de 0,5.

**Poids par defaut : 0%** — ce signal est desactive par defaut pour ne pas modifier le scoring existant. L'utilisateur peut l'activer via le slider dans l'interface.

**Couverture** : ~35 000 communes (quasi-exhaustif grace aux comptes DGFiP).

---

### Calcul du score final

```
score = arrondi( (signal_1 * poids_1 + signal_2 * poids_2 + ... + signal_6 * poids_6)
                 / (poids_1 + poids_2 + ... + poids_6) * 100 )
```

Avec les poids par defaut (modifiables via les sliders dans l'interface) :

| Signal | Poids | % du total |
|--------|-------|------------|
| Stationnement payant | 30 | 30% |
| Taille commune | 25 | 25% |
| Effectif PM | 20 | 20% |
| Accidents routiers | 15 | 15% |
| Croissance PM | 10 | 10% |
| Capacite budgetaire | 0 | 0% (activable) |

L'utilisateur peut ajuster ces poids via l'interface. Le score est recalcule en temps reel.

### Distribution des scores

| Tranche | Communes |
|---------|----------|
| 0-9 | 13 197 |
| 10-19 | 1 487 |
| 20-29 | 906 |
| 30-39 | 544 |
| 40-49 | 359 |
| 50-59 | 94 |
| 60-69 | 63 |
| 70-79 | 76 |
| 80-89 | 21 |
| 90-100 | 0 |

La majorite des communes (79%) ont un score < 10. C'est normal : seules les communes avec des signaux multiples et forts obtiennent un score eleve. **239 communes depassent 50/100.**

---

## 7. Filtres de prospection

En plus du score, quatre filtres binaires sont disponibles :

| Filtre | Effet |
|--------|-------|
| **Stat. payant uniquement** | Ne montre que les 226 communes avec stationnement payant |
| **Sans videoverbalisation** | Exclut les 586 communes deja equipees en videoverbalisation |
| **Population min.** | Slider pour fixer un seuil de population minimum |
| **Communes avec QPV** | Ne montre que les 843 communes ayant au moins un Quartier Prioritaire |

Le filtre "Sans videoverbalisation" merite une explication : plutot que d'inclure ce critere dans le score (ce qui gonflait artificiellement 90% des communes puisque la majorite n'ont pas de videoverbalisation), il est traite comme un **filtre d'exclusion**. Les communes deja equipees sont simplement masquees.

Le filtre QPV permet de cibler les communes beneficiant de la politique de la ville, qui peuvent avoir des besoins specifiques en matiere de securisation et des financements dedies.

**Source videoverbalisation** : liste scrappee depuis [video-verbalisation.fr/villes.php](https://video-verbalisation.fr/villes.php) (534 villes listees, 586 codes INSEE matches apres resolution des homonymes). Le scraping extrait les noms de villes depuis les liens HTML et les matche par nom normalise.

---

## 8. Mode securite — fonctionnement

Le mode securite affiche une **heatmap** du ratio de delinquance pour 10 000 habitants. L'echelle de couleur utilise 6 niveaux (palette violet/magenta) :

| Seuil (ratio /10k) | Couleur |
|---------------------|---------|
| 0 | Violet tres fonce |
| ... | Degradation progressive |
| Maximum observe | Magenta clair |

### Filtrage par categorie

Des "pills" de categories (comme les familles politiques en mode politique) permettent de filtrer par type de delit. Par defaut, le ratio total est affiche. Un clic sur une categorie recalcule la heatmap avec le ratio de cette seule categorie.

### Croisement par famille politique

Un tableau dans la barre laterale affiche le **ratio moyen de delinquance par famille politique**, permettant de croiser les donnees de securite avec les etiquettes politiques des maires.

### Barre d'information

La barre inferieure affiche : nombre de communes avec donnees | ratio moyen | categorie active.

---

## 9. Jointure et matching des donnees

Plusieurs sources de donnees n'utilisent pas le code INSEE mais un **nom de commune + departement**. La jointure repose sur une normalisation des noms :

```python
def normalize(name):
    # 1. Suppression des accents (decomposition Unicode NFD)
    # 2. Passage en majuscules
    # 3. Suppression du texte entre parentheses
    # 4. Remplacement tirets, apostrophes → espaces
    # 5. Expansion "ST" → "SAINT", "STE" → "SAINTE"
    # 6. Reduction des espaces multiples
```

Ce matching est imparfait. Les communes non matchees sont principalement :
- Des EPCI (intercommunalites) presentes dans le fichier PM
- Des communes recemment fusionnees (noms changes)
- Des orthographes divergentes entre sources

**Taux de matching** :
- Police municipale : 91% (4 167 / ~4 576)
- Videoverbalisation : 99,3% (586 / 590 matchables)

Les sources plus recentes (delinquance, QPV, DGFiP) utilisent directement le code INSEE, ce qui elimine les problemes de matching.

---

## 10. Limites connues et pistes d'amelioration

### Donnees incompletes

| Donnee | Couverture | Probleme |
|--------|-----------|----------|
| Nuances politiques | 7,7% des communes | Seules les communes > 1 000 hab. ont une nuance officielle |
| Stationnement payant | 226 communes | L'enquete GART 2019 est loin d'etre exhaustive (~800+ communes en realite) |
| Surveillance | 12% des communes | Les communes sans PM ni ASVP sont absentes |
| Delinquance | ~27% des communes | Seuil de diffusion SSMSI masque les petites communes |
| Taux de pauvrete | ~4 350 communes | Secret statistique pour les petites communes (Filosofi 2021) |

### Donnees absentes qui seraient pertinentes

- **Police intercommunale** : depuis 2019, des communes mutualisent leur police au niveau intercommunal — non pris en compte
- **Radars et PV automatises** : pas de dataset national open data identifie a la maille communale
- **Budget "securite" detaille** : les comptes DGFiP sont integres (DGF, dette, etc.) mais sans decoupage fonctionnel "securite" exploitable

### Biais connus du scoring

1. **Biais en faveur des communes "moyennes"** : le signal `pop_sweet` (25% du poids) favorise mecaniquement les communes autour de 30 000 habitants. C'est intentionnel (ciblage commercial) mais biaise l'analyse geographique
2. **Sous-representation du stationnement payant** : avec seulement 226 communes, le signal pese peu dans le score reel malgre son poids theorique de 30%. La contribution moyenne est de 0,4 points sur 100
3. **Ratio PM plafonne** : le plafonnement a 50 agents/10k ecrase les differences entre communes tres dotees (Saint-Tropez, stations balneaires)
4. **Accidents corporels uniquement** : exclut les accidents materiels et les infractions routieres sans accident, qui seraient pourtant pertinents

### Biais connus des donnees d'enrichissement

5. **Delinquance — seuil de diffusion** : les donnees sont masquees pour les petites communes, ce qui sur-represente les communes urbaines et moyennes dans les analyses
6. **Delinquance — chiffre noir** : les faits enregistres ne representent qu'une fraction des faits reels, avec un taux de declaration tres variable selon le type de delit
7. **Taux de pauvrete partiel** : le taux de pauvrete (Filosofi 2021) n'est disponible que pour ~4 350 communes de taille suffisante en raison du secret statistique
8. **Paris/Lyon/Marseille** : certaines donnees financieres peuvent etre absentes car ces communes utilisent des codes d'arrondissements incompatibles avec le code commune global

### Peer groups et argumentaire (insights.json)

Le script `process_insights.py` calcule pour chaque commune un **groupe de pairs** (20 communes les plus similaires) et des **benchmarks comparatifs**.

**Algorithme de distance** : distance euclidienne ponderee sur 4 dimensions normalisees (z-score) :
- `log(population)` — poids 0.4
- `revenu median` — poids 0.25
- `taux de pauvrete` — poids 0.25
- `famille politique` — bonus de proximite -0.3 si meme famille

**Benchmarks** : pour chaque commune, on calcule le percentile parmi ses 20 pairs sur 5 indicateurs (criminalite, police municipale, accidents, revenu, pauvrete).

**Flags narratifs** (seuils) :
- `crime_above_peers` : percentile criminalite > 75
- `no_pm_peers_have` : commune sans PM et > 50% des pairs en ont
- `no_vv_peers_have` : commune sans VV et > 30% des pairs en ont
- `pm_growing` : effectifs PM en hausse (dernier > premier dans la tendance)
- `high_accident_rate` : percentile accidents > 50
- `budget_capacity` : DGF/hab au-dessus de la mediane des pairs
- `high_poverty` : percentile pauvrete > 60

**Couverture** : ~9 500 communes (celles ayant une population connue et au moins un indicateur socio-economique).

**Biais** : le peer matching favorise les communes bien documentees (avec revenus et pauvrete disponibles). Les petites communes rurales sans donnees Filosofi sont exclues.

### Fraicheur des donnees (au 1er mars 2026)

| Donnee | Annee | Age | Badge |
|--------|-------|-----|-------|
| Videoverbalisation | 2025 | ~1 an | 🟢 |
| PM courant | 2024 | ~2 ans | 🟢 |
| PM historique | 2019-2024 | a jour | 🟢 |
| Accidents | 2023-2024 | ~2 ans | 🟢 |
| Delinquance | 2024 | ~2 ans | 🟢 |
| QPV | 2024 | ~2 ans | 🟢 |
| Comptes communes (DGFiP) | 2022 | ~4 ans | 🟡 |
| Population INSEE | 2021 | ~5 ans | 🟡 |
| Revenus medians (Filosofi) | 2021 | ~5 ans | 🟡 |
| Nuances politiques | 2020 | ~6 ans | 🟠 |
| Stationnement payant | 2019 | ~7 ans | 🔴 |

Les municipales de 2026 rendront les nuances politiques obsoletes — leur renouvellement sera a surveiller. Le stationnement payant (GART 2019) est la donnee la plus ancienne et la plus incomplete du projet.

L'interface affiche des **badges de fraicheur** colores pour chaque source : vert (< 3 ans), jaune (3-5 ans), orange (5-7 ans), rouge (> 7 ans).

---

## 11. Reproduction

Tous les scripts de generation sont dans le depot :

```bash
# Regenerer les donnees politiques (necessite les CSV source dans /tmp)
python3 process_maires.py

# Regenerer les donnees de surveillance (telecharge tout depuis data.gouv.fr)
python3 process_surveillance.py

# Regenerer les donnees de prospection (telecharge tout depuis data.gouv.fr + scraping)
python3 process_prospection.py

# Regenerer les donnees de delinquance (telecharge le parquet depuis data.gouv.fr, ~14 MB)
python3 process_delinquance.py

# Regenerer les donnees d'enrichissement (QPV, DGFiP, Filosofi — telecharge tout)
python3 process_enrichment.py

# Regenerer les insights (peer groups, benchmarks — utilise les JSON existants, ~2 min)
python3 process_insights.py
```

Dependances Python : `pandas`, `openpyxl`, `odf`, `pyarrow`

Les URLs des sources sont en dur dans les scripts. Si une URL change (mise a jour du dataset sur data.gouv.fr), le script echouera et l'URL devra etre mise a jour manuellement.
