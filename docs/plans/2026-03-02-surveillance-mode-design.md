# Design : Mode Surveillance dédié

**Date :** 2026-03-02
**Objectif :** Transformer la carte en outil d'exploration de la surveillance municipale, avec corrélation politique.

## Contexte

La carte affiche ~35 000 communes colorées par famille politique du maire (municipales 2020), avec une couche surveillance (bordures) ajoutée récemment. L'objectif est de créer un mode de visualisation dédié à la surveillance et de montrer la corrélation avec l'orientation politique.

## Limites identifiées de la version actuelle

- Lisibilité visuelle : l'épaisseur de bordure est trop subtile
- Pas de statistiques agrégées
- Données vidéosurveillance datées (2012, CNIL)
- Manque d'interactivité (pas de filtres surveillance, pas de comparaison)

---

## 1. Données & Sources

### Enrichissement de `surveillance.json`

- **Ajouter la population par commune** (source : INSEE)
- **Calculer le ratio agents/10 000 habitants** dans `process_surveillance.py`
- Afficher les deux : chiffres bruts ET ratio normalisé

### Nouveau schéma `surveillance.json`

```json
{
  "INSEE_CODE": {
    "pm": 5,        // agents police municipale
    "asvp": 0,      // agents ASVP
    "vs": 1,        // vidéosurveillance (1 = oui)
    "pop": 12000,   // population INSEE
    "r": 4.2        // ratio (pm+asvp)/10k hab
  }
}
```

### Données vidéosurveillance

- Chercher des sources plus récentes que 2012 (CNIL, Ministère de l'Intérieur)
- Si rien de trouvé, garder 2012 avec mention claire de l'ancienneté

---

## 2. Mode Surveillance (vue dédiée)

### Toggle de mode

- Bouton toggle en haut de la carte : "Vue politique" / "Vue surveillance"
- Change l'encodage visuel de la carte + la légende + le panneau info

### Encodage visuel en mode surveillance

- **Couleur de la commune** = intensité de surveillance (ratio agents/10k hab)
  - Gradient jaune clair (faible) → rouge foncé (élevé)
  - Gris semi-transparent pour communes sans données
- **Bordure blanche** = vidéosurveillance activée
- Communes sans données : grisées et semi-transparentes (visibles mais en arrière-plan)

### Légende adaptée

- Change automatiquement avec le mode
- En mode surveillance : gradient de couleur + échelle du ratio
- Indicateur vidéosurveillance (bordure blanche)

### Info panel enrichi au hover

- Effectifs bruts (PM + ASVP)
- Population
- Ratio agents/10 000 hab
- Vidéosurveillance : oui/non
- Famille politique du maire (pour la corrélation)

---

## 3. Sidebar statistiques (panneau droit)

### Contenu

1. **Tableau par famille politique :**

| Famille | Communes (avec données) | Moy. agents/10k hab | % vidéosurveillance |
|---------|------------------------|---------------------|---------------------|
| Gauche  | N                      | X.X                 | XX%                 |
| Centre  | N                      | X.X                 | XX%                 |
| Droite  | N                      | X.X                 | XX%                 |
| Ext. droite | N                  | X.X                 | XX%                 |
| Divers  | N                      | X.X                 | XX%                 |

2. **Indicateur global** : phrase de synthèse sur la corrélation
3. **Note méthodologique** : nombre de communes avec données, exclusion des "Non classé", dates des sources

### Interaction

- Cliquer sur une ligne filtre la carte sur cette famille
- Se met à jour quand les filtres changent

### Positionnement

- Sidebar fixe à droite
- Visible uniquement en mode surveillance

---

## 4. Filtres enrichis

### En mode surveillance (en plus des filtres par famille existants)

- **Slider** : seuil de ratio agents/10k hab (filtrer au-dessus/en-dessous)
- **Checkbox** : "Vidéosurveillance uniquement"
- **Checkbox** : "Avec données uniquement" (masquer les communes sans données)

### Interaction carte ↔ stats

- Les filtres affectent à la fois la carte et les statistiques
- Le tableau stats se recalcule en temps réel

---

## 5. Architecture technique

### Structure

- Tout reste dans `index.html` (pas de séparation en fichiers)
- Code JavaScript restructuré en fonctions claires :
  - `switchMode(mode)` — bascule politique/surveillance
  - `getStylePolitique(feature)` / `getStyleSurveillance(feature)`
  - `renderLegend(mode)` — légende adaptée au mode
  - `renderStats(data, filter)` — panneau statistiques
  - `updateFilter(famille, mode)` — filtre croisé

### Script Python

- `process_surveillance.py` enrichi :
  - Téléchargement données population INSEE
  - Calcul du ratio agents/10k hab
  - Recherche de données vidéosurveillance récentes

### Performances

- Rendu canvas Leaflet déjà en place
- Stats calculées une fois au chargement, recalculées aux changements de filtre
- Pas de dépendances supplémentaires côté frontend
