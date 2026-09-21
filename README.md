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
Chemin Home Assistant : /medias/videos
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
