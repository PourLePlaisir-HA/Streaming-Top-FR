# 🍿 Streaming Top FR

<p align="center">
  <img src="https://raw.githubusercontent.com/PourLePlaisir-HA/Streaming-Top-FR/main/custom_components/streaming_top_fr/brand/logo.png" alt="Streaming Top FR" width="220">
</p>

<p align="center">
  <strong>Découvrez quoi regarder. Retrouvez où le regarder. Lancez-le directement depuis Home Assistant.</strong>
</p>

<p align="center">
  Streaming Top FR transforme Home Assistant en véritable hub de découverte et de lecture pour vos services de streaming <strong>et votre vidéothèque locale</strong>.
</p>

---

## 🆕 Nouveautés 1.0.9

La version 1.0.9 simplifie la configuration de **Streaming Local** sans modifier son fonctionnement de scan ou de lecture.

### ⚙️ Configuration Streaming Local simplifiée

Le champ **Chemin dans Home Assistant** n'est plus affiché dans l'écran de configuration ni dans la synthèse.

Le chemin de scan déjà enregistré reste conservé en interne afin de ne pas casser les installations existantes. La configuration utilisateur reste centrée sur :

- activation de Streaming Local ;
- URI SMB utilisée par VLC ;
- mode d'authentification SMB ;
- utilisateur et mot de passe SMB ;
- extensions vidéo ;
- dossiers Films, Séries, Animation et Documentaires ;
- scan éventuel des dossiers cachés.

Cette évolution est volontairement limitée à la couche de configuration. Le scanner, le matching des métadonnées et la lecture VLC restent inchangés.

---

## 🆕 Nouveautés 1.0.8

La série `1.0.8` introduit un **filtre transversal de genres** sur les trois cartes, sans modifier les moteurs historiques de classement, de matching ou de lecture.

### 🏷️ Filtre par genre

Le sélecteur **Genre** apparaît avec `Tous` puis uniquement les genres réellement présents dans la sélection courante.

Genres normalisés :

- Action
- Aventure
- Animation
- Comédie
- Crime / Policier
- Documentaire
- Drame
- Famille
- Fantastique
- Histoire
- Horreur
- Musique
- Mystère
- Romance
- Science-fiction
- Sport
- Thriller
- Guerre
- Western

Le filtre est volontairement **mono-sélection** dans cette version.

Il se combine avec :

- la plateforme ;
- Films / Séries / Animation / Famille ;
- les décennies ;
- Ma liste / Déjà vus / Pas intéressé ;
- Tous / Pas encore vus / Vus sur Streaming Local ;
- la recherche instantanée ;
- `Voir N de plus` et `scroll_infini`.

Le genre actif est conservé après un refresh.

### ⚙️ Option Lovelace

Le filtre est actif par défaut. Il peut être désactivé indépendamment sur une carte :

```yaml
type: custom:streaming-top-fr-card
genre_filter: false
```

La même option est disponible sur les trois cartes.

### 🔍 Debug des genres

Lorsque le mode Debug est activé, les détails techniques exposent également :

- `genres_raw` : valeurs brutes fournies par la source ;
- `genres` : identifiants canoniques utilisés par le filtre ;
- `genre_labels` : libellés français ;
- `genre_source` : JustWatch ou IMDb ;
- `genre_filter` : filtre actuellement sélectionné ;
- `genre_match` : résultat du filtrage pour le titre.

### 🛡️ Sans régression moteur

Les genres sont ajoutés dans une couche d'extension dédiée.

Les gardes CI continuent de vérifier que :

- le moteur historique Streaming / Top reste inchangé ;
- le moteur Streaming Local reste inchangé ;
- le parser Local reste inchangé.

Les anciens caches dépourvus de genres sont rafraîchis automatiquement et les genres sont ensuite conservés dans un cache dédié.

---

## 🆕 Nouveautés 1.0.7

La version `1.0.7` consolide l'expérience utilisateur des trois cartes sans modifier les moteurs de données ou de classement.

### 🔎 Recherche plus robuste

La recherche affiche désormais un message explicite lorsqu'aucun résultat n'est trouvé, avec un bouton permettant d'effacer immédiatement la requête.

Le champ de recherche conserve également correctement le focus pendant la saisie continue : les frappes restent dans la searchbox et ne déclenchent plus les raccourcis clavier globaux de Home Assistant.

### 🔄 État conservé après refresh

Un rafraîchissement conserve désormais les principaux choix de navigation :

- recherche en cours ;
- plateforme et type de média sur Streaming ;
- bucket sélectionné : À découvrir / Ma liste / Déjà vus / Pas intéressé ;
- décennie et catégorie sur Top Streaming ;
- sous-catégorie Famille lorsqu'elle est utilisée ;
- catégorie et filtre Tous / Pas encore vus / Vus sur Streaming Local.

### ✨ Chargement plus fluide

Le premier chargement utilise un skeleton responsive afin de limiter les changements brusques de hauteur.

Lorsqu'un refresh est lancé avec des contenus déjà affichés, les posters restent visibles pendant la récupération des nouvelles données au lieu d'être remplacés par une carte vide ou un simple message de chargement.

### 📱 Responsive renforcé

La mise en page est explicitement couverte par les tests sur trois profils :

- smartphone ~390 px ;
- tablette ~820 px ;
- desktop large ~1600 px.

Les comportements `columns: full`, `Voir N de plus`, `scroll_infini` et `searchbox` restent compatibles.

## ✨ Pourquoi Streaming Top FR ?

Quand plusieurs plateformes de streaming et une vidéothèque locale cohabitent, trouver un film devient vite plus compliqué que le regarder.

**Streaming Top FR centralise tout dans Home Assistant :**

- découverte multi-services disponible en France ;
- classement des meilleurs films, séries et animations par décennie ;
- vue Famille basée sur les classifications d'âge ;
- suivi global des contenus vus, à voir ou ignorés ;
- vidéothèque locale enrichie avec affiches et métadonnées ;
- lancement direct sur Android TV / Freebox Pop ;
- lecture des fichiers locaux avec VLC via SMB.

L'intégration est pensée pour fonctionner comme un **catalogue unifié**, tout en laissant chaque service et chaque fichier à sa place.

---

# 🚀 Fonctionnalités

## 🎬 1. Streaming multi-services

La carte principale permet de parcourir les contenus disponibles sur les services activés.

Services actuellement pris en charge pour la découverte :

- Netflix
- Disney+
- Prime Video
- HBO Max
- Apple TV+
- Paramount+
- CANAL+
- Crunchyroll
- MUBI
- ADN

Les disponibilités sont vérifiées pour la **France**.

Netflix utilise son classement officiel lorsque disponible ; les autres catalogues et disponibilités s'appuient sur JustWatch France.

### Lancement direct validé

Depuis la popup d'un contenu, Streaming Top FR peut lancer directement :

- **Netflix**
- **Disney+**
- **Prime Video**

sur une destination Android TV compatible configurée dans Home Assistant.

Les autres services restent visibles pour la découverte et la disponibilité, même lorsque leur lancement automatisé n'est pas encore activé.

---

## 🏆 2. Top Streaming par décennie

La deuxième carte propose un catalogue historique par décennie.

Catégories disponibles :

- 🎬 Films
- ✨ Animation
- 📺 Séries
- 👨‍👩‍👧 Famille

Les décennies peuvent être activées individuellement et leur profondeur configurée.

Le classement combine :

1. un pool de contenus réellement populaires et disponibles en France ;
2. les notes IMDb ;
3. le volume de votes IMDb ;
4. une pondération destinée à éviter qu'un titre très peu évalué ne domine artificiellement le classement.

Des filtres permettent notamment de définir :

- un minimum de votes IMDb ;
- l'exclusion des courts métrages ;
- les décennies actives ;
- le nombre de titres par catégorie.

---

## 👨‍👩‍👧 3. Mode Famille

Le mode Famille permet de filtrer facilement les contenus selon un âge cible.

Il fonctionne sur :

- Films
- Animation
- Séries

La classification française est prioritaire lorsqu'elle est disponible.

Un fallback US peut être activé, sans conversion artificielle des classifications américaines vers les classifications françaises.

Exemple : pour une cible de moins de 12 ans, l'intégration peut autoriser les classifications compatibles et exclure automatiquement les contenus `-12`, `-16`, `-18` selon la configuration choisie.

---

## ✅ 4. Statuts globaux et bibliothèques personnelles

Les statuts sont associés à l'œuvre elle-même, et non à une plateforme particulière.

Vous pouvez utiliser :

- **Ma liste**
- **Déjà vu**
- **Pas intéressé**

Un film marqué vu depuis un service reste considéré comme vu ailleurs lorsque la même œuvre est reconnue.

Les statuts **Vu** et **Pas intéressé** peuvent retirer automatiquement les titres des zones de découverte, tout en restant réversibles.

La logique est partagée entre :

- Streaming
- Top Streaming
- Famille
- Streaming Local

---

# 🏠 Streaming Local

Streaming Top FR ne se limite pas aux plateformes en ligne.

La troisième carte, **Streaming Local**, transforme une vidéothèque accessible depuis Home Assistant en catalogue visuel enrichi.

## 📁 Catégories locales

La bibliothèque peut être organisée en :

- Films
- Séries
- Animation
- Documentaires
- Famille

Les dossiers associés à chaque catégorie sont configurables.

---

## 🖼️ Métadonnées et affiches

Les fichiers locaux sont analysés puis enrichis avec les métadonnées disponibles :

- titre
- année
- synopsis
- affiche
- note
- classification d'âge
- informations IMDb / JustWatch lorsque disponibles

Les noms de fichiers sont nettoyés afin d'améliorer l'identification automatique.

Pour les séries, Streaming Local sait également reconnaître les saisons et épisodes et les regrouper dans une présentation adaptée.

---

## 👁️ Suivi Vu / Pas encore vu

Streaming Local dispose de ses propres vues :

- **Tous**
- **Pas encore vus**
- **Vus**

Les statuts sont réversibles.

Pour les séries, le suivi peut s'appliquer épisode par épisode afin de retrouver rapidement la progression de lecture.

---

## ▶️ Lecture VLC directe via SMB

Un fichier local peut être lancé directement depuis Home Assistant sur une destination Android TV utilisant **VLC**.

Le flux est simple :

```text
Streaming Local
      ↓
Home Assistant
      ↓
Android Debug Bridge
      ↓
VLC
      ↓
SMB / NAS
```

### Authentification SMB

Le mode recommandé et utilisé par défaut est :

**Streaming Top FR — identifiants configurés**

Vous renseignez dans la configuration :

- l'URI SMB de base ;
- l'utilisateur SMB ;
- le mot de passe SMB.

Exemple public :

```text
smb://192.168.0.200/videos
```

Les identifiants :

- restent côté Home Assistant ;
- ne sont pas envoyés à la carte Lovelace ;
- ne sont pas stockés dans les objets de la vidéothèque ;
- sont injectés uniquement au moment du lancement VLC ;
- sont encodés correctement si le login ou le mot de passe contient des caractères spéciaux.

Le mode **VLC — identifiants mémorisés** reste disponible comme alternative.

---

# 🧩 Les 3 cartes Lovelace

Une seule ressource JavaScript fournit les trois cartes.

## 1. Streaming

```yaml
type: custom:streaming-top-fr-card
title: Streaming
```

Découverte des contenus disponibles sur les services activés, gestion des statuts et lancement direct.

## 2. Top Streaming

```yaml
type: custom:streaming-top-fr-catalog-card
title: Top Streaming
default_category: movies
```

Classements par décennie avec Films, Animation, Séries et Famille.

## 3. Streaming Local

```yaml
type: custom:streaming-local-card
title: Streaming Local
```

Catalogue de la vidéothèque locale, suivi Vu / Pas encore vu et lecture VLC.

---

## 📐 Affichage responsive des cartes

À partir de la série **1.0.5**, les trois cartes utilisent une grille verticale responsive avec chargement progressif des affiches.

Le nombre de colonnes s'adapte automatiquement à la largeur réelle de chaque carte. Le comportement ne dépend donc pas directement de l'appareil : une carte étroite sur un grand écran peut utiliser le même mode qu'une tablette, tandis qu'une carte occupant une grande section exploite davantage de colonnes.

Le nombre de lignes visibles est configurable dans :

**Paramètres → Appareils et services → Streaming Top FR → Configurer → Affichage des cartes**

Valeurs par défaut :

```text
Espace étroit  (< 700 px)     : 2 lignes
Espace moyen   (700–1199 px)  : 2 lignes
Grand espace   (≥ 1200 px)    : 3 lignes
Posters ajoutés par lot       : 8
Scroll infini par défaut      : Non
```

Chaque nombre de lignes peut être réglé de **1 à 6**. Le nombre de posters ajoutés par lot peut être réglé de **1 à 50**.

Les titres sont affichés dans l'ordre naturel, de gauche à droite puis de haut en bas.

Par défaut, la carte n'active pas de scroll vertical interne au premier affichage : elle montre uniquement le nombre de lignes configuré, puis propose un bouton **Voir N de plus ↓**. Chaque clic rend jusqu'à `N` posters supplémentaires, sans jamais dépasser le nombre de titres réellement disponibles dans le pool courant.

Le **scroll infini** reste disponible en option. Lorsqu'il est activé, les lots suivants sont rendus automatiquement à l'approche du bas de la grille.

Les deux paramètres peuvent être surchargés indépendamment dans chaque carte Lovelace :

```yaml
type: custom:streaming-top-fr-card
scroll_infini: false
posters_par_lot: 8
```

`scroll_infini` et `posters_par_lot` suivent la priorité suivante :

1. valeur définie dans la carte Lovelace ;
2. sinon, valeur de la configuration globale de l'intégration ;
3. sinon, valeurs par défaut : `false` et `8`.

Exemple avec un comportement différent pour Streaming Local :

```yaml
type: custom:streaming-local-card
scroll_infini: true
posters_par_lot: 20
```

À partir de la série **1.0.6**, les trois cartes disposent aussi d'une recherche instantanée dans les titres. La zone est activée par défaut et peut être masquée carte par carte avec :

```yaml
type: custom:streaming-local-card
searchbox: false
```

La recherche est insensible à la casse et aux accents et cherche le texte saisi **n'importe où dans le titre affiché**. Par exemple, `Pit` peut retrouver **Les Chroniques de Riddick : Pitch Black**.

À partir de `1.0.6-beta.2`, les trois cartes demandent par défaut toute la largeur disponible dans une vue Home Assistant **Sections** via `columns: full`. Une section qui s'étend sur plusieurs colonnes du dashboard peut donc réellement donner davantage de largeur à la carte, et le responsive recalcule automatiquement le nombre de colonnes de posters.

Exemple de carte :

```yaml
type: custom:streaming-top-fr-card
grid_options:
  columns: full
```

La largeur maximale reste déterminée par la section Home Assistant qui contient la carte. Pour obtenir une carte plus large que la largeur standard d'une section, il faut donc également élargir cette section dans le dashboard.

Le dimensionnement se fait carte par carte. Deux cartes placées côte à côte sur un écran large peuvent donc automatiquement utiliser un mode plus compact qu'une carte seule occupant toute la largeur.

La position de scroll est conservée par vue lors des rerenders et rafraîchissements afin d'éviter de revenir systématiquement en haut de la carte.


---

# 📦 Installation avec HACS

## 1. Ajouter le dépôt

Dans **HACS** :

1. ouvrez les dépôts personnalisés ;
2. ajoutez :

```text
https://github.com/PourLePlaisir-HA/Streaming-Top-FR
```

3. choisissez le type **Integration** ;
4. recherchez **Streaming Top FR** ;
5. installez la dernière version stable ;
6. redémarrez Home Assistant.

## 2. Ajouter l'intégration

Dans Home Assistant :

**Paramètres → Appareils et services → Ajouter une intégration → Streaming Top FR**

La configuration se fait ensuite entièrement depuis l'interface Home Assistant.

### Ressource Lovelace automatique

À partir de la version 1.0.4, Streaming Top FR enregistre automatiquement la ressource JavaScript nécessaire aux trois cartes :

```text
/streaming_top_fr/streaming-top-fr-card.js?v=<version>
```

Il n'est donc plus nécessaire d'ajouter manuellement cette ressource dans **Paramètres → Tableaux de bord → Ressources**.

Lors d'une mise à jour, l'URL est automatiquement actualisée avec la version installée afin de limiter les problèmes de cache. Si une ancienne ressource Streaming Top FR avait été ajoutée manuellement, elle est réutilisée et mise à jour au lieu de créer un doublon.

---

# ⚙️ Configuration

Depuis :

**Paramètres → Appareils et services → Streaming Top FR → Configurer**

vous pouvez gérer :

- fréquence d'actualisation ;
- services de streaming actifs ;
- profondeur de découverte ;
- paramètres IMDb ;
- décennies ;
- mode Famille ;
- classifications d'âge ;
- destinations de lecture ;
- activation ou désactivation de la lecture directe ;
- Streaming Local ;
- dossiers locaux ;
- extensions vidéo ;
- URI SMB ;
- authentification SMB.

---

# 📺 Android TV / Freebox Pop

La découverte et les classements n'ont pas besoin d'ADB.

**Android Debug Bridge est uniquement nécessaire pour le lancement automatisé sur Android TV.**

Exemple générique de destinations :

```yaml
players:
  androidtv1:
    name: AndroidTV1
    type: android_tv
    media_player: media_player.androidtv1
    remote: remote.androidtv1
    adb_player: media_player.androidtv1_adb

  androidtv2:
    name: AndroidTV2
    type: android_tv
    media_player: media_player.androidtv2
    remote: remote.androidtv2
    adb_player: media_player.androidtv2_adb
```

Les destinations se configurent normalement depuis l'interface Home Assistant ; cet exemple sert uniquement à illustrer leur structure.

> **Sécurité :** ne publiez jamais ADB sur Internet. Gardez le débogage Android accessible uniquement depuis votre réseau local.

---

# 💾 Exemple Streaming Local

Configuration type :

```text
URI SMB              : smb://192.168.0.200/videos
Authentification     : Streaming Top FR — identifiants configurés
Utilisateur SMB      : media_user
Mot de passe SMB     : ********
```

Structure possible :

```text
/medias/videos
├── Films
├── Series
├── Animation
└── Documentaires
```

Les noms de dossiers sont configurables : cette structure n'est qu'un exemple.

---

# 🔐 Sécurité et confidentialité

Streaming Top FR applique plusieurs principes simples :

- les credentials SMB configurés restent côté backend Home Assistant ;
- le mot de passe SMB n'est pas exposé au navigateur ;
- aucune credential n'est ajoutée aux données de la bibliothèque ;
- les URI stockées par le scanner restent sans login ni mot de passe ;
- les commandes de lecture sont exécutées localement via Home Assistant ;
- ADB doit rester limité au réseau local.

---

# 🧠 Sources et logique de classement

Streaming Top FR utilise plusieurs sources complémentaires :

- **Netflix officiel** lorsque son Top est disponible ;
- **JustWatch France** pour les catalogues, popularités et disponibilités ;
- **IMDb** pour les notes, volumes de votes et affiches lorsqu'un identifiant canonique est disponible.

Le but n'est pas de fabriquer un classement universel, mais de proposer un catalogue cohérent avec les contenus réellement accessibles sur les services configurés en France.

---

# 🧰 Compatibilité

La version 1.0 est conçue pour :

- Home Assistant récent ;
- installation via HACS ;
- dashboards Lovelace ;
- Android TV / Freebox Pop pour les fonctions de lancement ;
- VLC Android pour Streaming Local ;
- vidéothèque locale accessible à Home Assistant et via SMB pour la lecture.

Les fonctions de catalogue restent utilisables sans Android TV, sans ADB et sans lecture directe.

---

# 🛡️ Stabilité

La branche 1.0 conserve des gardes de régression automatisés pour protéger :

- le moteur Streaming historique ;
- le moteur Streaming Local ;
- le parser des séries et épisodes ;
- les identités canoniques des contenus ;
- le registre Vu / Non vu ;
- le lancement VLC ;
- les vues Famille et Local ;
- la syntaxe Python, JSON et JavaScript.

---

# ❤️ Projet communautaire

Streaming Top FR est un projet Home Assistant indépendant distribué sous licence MIT.

Les noms et marques Netflix, Disney+, Prime Video, IMDb, JustWatch, VLC, Home Assistant et autres marques citées appartiennent à leurs propriétaires respectifs.

Les contributions, retours de tests et rapports de bugs sont les bienvenus.

---

## 🍿 Streaming Top FR 1.0

**Streaming + Top historique + Famille + bibliothèque locale + suivi de lecture + lancement direct, réunis dans Home Assistant.**
