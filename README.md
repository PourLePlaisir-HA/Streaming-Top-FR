# Streaming Top FR 0.7.0

<p align="center">
  <img src="custom_components/streaming_top_fr/brand/logo.png" alt="Streaming Top FR" width="220">
</p>

<p align="center">
  <strong>Streaming Top FR for Home Assistant</strong><br>
  Découvrez, classez et lancez les meilleurs films et séries disponibles sur vos services de streaming en France.
</p>

Carte Home Assistant multi-services pour découvrir des films et séries disponibles en France, les classer (`Ma liste`, `Déjà vus`, `Pas intéressé`) et lancer les plateformes déjà validées vers des destinations configurables.


## Installation

### 1. Installer Streaming Top FR via HACS

1. Ouvrez **HACS** dans Home Assistant.
2. Ajoutez `https://github.com/PourLePlaisir-HA/Streaming-Top-FR` comme **dépôt personnalisé** de type **Integration**.
3. Recherchez **Streaming Top FR** puis installez l'intégration.
4. Redémarrez Home Assistant.
5. Ajoutez l'intégration depuis **Paramètres → Appareils et services → Ajouter une intégration → Streaming Top FR**.
6. L'assistant graphique s'ouvre automatiquement et vous guide à travers les services, la découverte, le Top Streaming, Famille, les classifications et, si souhaité, les destinations Android TV / Freebox.

> À partir de la v0.7, l'IHM Home Assistant devient la source de configuration principale. Un ancien `/config/streaming_top_fr.yaml` est importé automatiquement lors de la première migration, mais reste intact afin de permettre un retour vers la v0.6.5.

> La découverte et les classements fonctionnent sans ADB. **Android Debug Bridge est requis uniquement si vous souhaitez lancer Netflix, Disney+ ou Prime Video directement sur un Player Android TV / Freebox Pop depuis la carte.**

---

## Configuration native Home Assistant — v0.7

L'ajout de **Streaming Top FR** ouvre maintenant un assistant multi-écrans directement dans Home Assistant :

1. **Général** — fréquence d'actualisation ;
2. **Services** — Netflix, Disney+, Prime Video, HBO Max, Apple TV+, Paramount+, CANAL+, Crunchyroll, MUBI et ADN ;
3. **Découverte** — titres visibles, préchargement et profondeur ;
4. **Top Streaming / IMDb** — activation, seuil de votes et courts métrages ;
5. **Décennies** — choix de la décennie par défaut et sélection des décennies actives ;
6. **Famille** — âge cible et catégories ;
7. **Classification** — France prioritaire et fallback US ;
8. **Lecture** — ajout facultatif d'une ou plusieurs destinations Android TV / Freebox via sélecteurs d'entités.

Après installation, tous ces réglages restent accessibles depuis **Paramètres → Appareils et services → Streaming Top FR → Configurer**. Le menu permet également d'éditer individuellement chaque décennie et de gérer les destinations de lecture.

La lecture Android TV reste facultative : il est possible d'utiliser entièrement les fonctions de découverte et de classement sans installer ADB.

---

### 2. Préparer Android Debug Bridge (lecture depuis Home Assistant)

Streaming Top FR utilise l'action Home Assistant `androidtv.adb_command` pour les séquences de lancement Android TV. Il faut donc ajouter l'intégration officielle **Android Debug Bridge** dans Home Assistant.

Documentation officielle Home Assistant :  
https://www.home-assistant.io/integrations/androidtv/

Home Assistant recommande d'utiliser en priorité son implémentation Python ADB intégrée, sans serveur ADB externe.

#### Freebox Player Pop : activer le mode développeur

Sur le **Player Pop** :

1. Ouvrez **Paramètres**.
2. Allez dans **Préférences relatives à l'appareil** (ou **Système**, selon la version Android TV).
3. Ouvrez **À propos**.
4. Descendez sur **Build Android TV / Numéro de build**.
5. Appuyez **7 fois sur OK** avec la télécommande.
6. Un message confirme que le **mode développeur** est activé.
7. Revenez au menu précédent et ouvrez **Options pour les développeurs**.
8. Dans **Débogage**, activez **Débogage USB**.
9. Si votre version du Player propose aussi **Débogage réseau / ADB réseau**, activez-le.

Free documente également l'activation du mode développeur par appuis répétés sur le numéro de build sur le Player Pop :  
https://dev.freebox.fr/bugs/task/40578

#### Ajouter le Player Pop dans Home Assistant

1. Relevez l'**adresse IP locale** du Player Pop et, de préférence, réservez-la dans votre DHCP afin qu'elle ne change pas.
2. Dans Home Assistant : **Paramètres → Appareils et services → Ajouter une intégration**.
3. Recherchez **Android Debug Bridge**.
4. Ajoutez l'adresse IP du Player Pop.
5. Lors de la première connexion, une demande d'autorisation ADB apparaît sur le téléviseur : cochez **Toujours autoriser depuis cet appareil** puis validez.

L'intégration Android Debug Bridge crée notamment l'entité `media_player` utilisée comme `adb_player` par Streaming Top FR.

> **Sécurité :** ADB donne un contrôle avancé sur le Player. Ne publiez jamais le port ADB sur Internet et n'effectuez aucune redirection de port vers le Player. Gardez ADB uniquement sur votre réseau local.

#### Entités de destination

Exemple :

```yaml
players:
  salon:
    name: Salon
    type: android_tv
    media_player: media_player.android_tv_salon
    remote: remote.android_tv_salon
    adb_player: media_player.android_tv_salon_adb
```

- `media_player` : destination Home Assistant logique ;
- `remote` : entité `remote` capable d'allumer le Player et d'envoyer les commandes de navigation ;
- `adb_player` : entité `media_player` fournie par **Android Debug Bridge**, cible de `androidtv.adb_command`.

Les exemples du dépôt sont volontairement génériques : remplacez ces entités par celles de votre installation.

---

### 3. Charger les cartes Lovelace

Les **deux cartes sont incluses dans l'intégration** dans le fichier :

```text
custom_components/streaming_top_fr/www/streaming-top-fr-card.js
```

L'intégration expose ce fichier à l'adresse :

```text
/streaming_top_fr/streaming-top-fr-card.js
```

Il faut l'enregistrer **une seule fois** comme ressource Lovelace :

1. Ouvrez **Paramètres → Tableaux de bord**.
2. Ouvrez le menu **⋮ → Ressources**.
3. Ajoutez :
   - URL : `/streaming_top_fr/streaming-top-fr-card.js`
   - Type : **Module JavaScript**
4. Rechargez les ressources ou faites un rechargement forcé du navigateur.

La même ressource fournit les deux cartes suivantes.

#### Carte de découverte

```yaml
type: custom:streaming-top-fr-card
title: Streaming
```

#### Carte Top Streaming

```yaml
type: custom:streaming-top-fr-catalog-card
title: Top Streaming
default_category: movies
```

> La **décennie par défaut** se règle désormais dans **Paramètres → Appareils et services → Streaming Top FR → Configurer → Décennies**. Si vous ajoutez explicitement `default_decade:` dans le YAML de la carte, cette valeur locale prend priorité sur le réglage global de l'intégration.

---

### 4. Le moteur de lancement est-il inclus ?

**Oui.** Aucun script Home Assistant séparé n'est nécessaire pour les plateformes déjà validées.

Le moteur est embarqué dans :

```text
custom_components/streaming_top_fr/playback.py
```

La carte appelle directement le backend Streaming Top FR, qui exécute les séquences de lancement.

Séquences actuellement intégrées :

- **Netflix** : réveil du Player, redémarrage propre de l'application, sélection du profil par défaut puis lancement direct du contenu ;
- **Disney+** : résolution de la fiche France, réveil/redémarrage de l'application, ouverture du contenu puis validation du profil ;
- **Prime Video** : réveil, redémarrage propre de l'application et ouverture de Prime Video ;
- **HBO Max / Apple TV+ / Paramount+ / CANAL+ / Crunchyroll / MUBI / ADN** : disponibilité et catalogue pris en charge, mais lancement automatisé non activé tant que la séquence n'a pas été validée.

## Nouveau 0.6.5 — classement ancré sur la popularité France

Le Top Streaming n'est plus construit à partir d'un tri IMDb mondial. **JustWatch France `POPULAR` définit désormais le pool de candidats réellement populaires en France et disponibles sur les services activés**, puis la note IMDb et le volume de votes servent uniquement à classer la qualité à l'intérieur de ce pool via la pondération bayésienne existante.

Le comportement est hiérarchique : tous les candidats France restent prioritaires. Si le pool France ne suffit pas à remplir `top_count` après les filtres, un complément **US `POPULAR`** peut être utilisé, mais ses métadonnées et offres sont toujours relues en **France** et le titre n'est accepté que s'il est réellement disponible sur un service activé en France.

Aucun pays ou genre n'est blacklisté : un film international réellement populaire en France reste éligible. Les caches Top/Famille passent en génération `v5`; toutes les fonctions 0.6.4/0.6.3 sont conservées.

## Nouveau 0.6.4 — statuts globaux appliqués à tous les flows

`Déjà vu` et `Pas intéressé` sont désormais des exclusions globales de découverte. Dès qu'une œuvre reçoit l'un de ces statuts, elle disparaît des carrousels multi-services **et** du Top Streaming, dans toutes les branches : **Films, Animation, Séries et Famille**. Le statut `Ma liste` ne masque pas l'œuvre.

Les œuvres restent conservées dans leurs bibliothèques globales (`Déjà vus`, `Pas intéressé`) avec leurs métadonnées et disponibilités. En retirant le statut depuis le bucket correspondant, l'œuvre redevient éligible à la découverte au prochain rafraîchissement.

Le Top Streaming ne se contente pas de masquer la vignette : il conserve un pool classé de réserve et fait remonter le candidat suivant pour maintenir `top_count` lorsque c'est possible. La branche Famille applique la même logique après son filtre de classification d'âge. Les deux cartes se synchronisent aussi dans le navigateur : restaurer une œuvre depuis `Déjà vus` ou `Pas intéressé` recharge l'autre carte sans attendre un rechargement manuel du dashboard.

## Nouveau 0.6.3 — affiches IMDb canoniques

IMDb devient la **source de référence des affiches** dès qu'un `imdb_id` est connu. JustWatch reste la source de disponibilité France, des offres et de la découverte, mais son poster n'est utilisé qu'en fallback si IMDb est temporairement indisponible ou ne fournit aucune image exploitable.

La résolution utilise l'identifiant IMDb canonique fourni par JustWatch quand il est disponible ; sinon l'intégration conserve le fallback de résolution IMDb par titre/année/type. Les posters IMDb sont récupérés par lots via GraphQL puis mis en cache **90 jours par IMDb ID**, ce qui évite une requête HTTP par vignette.

La règle est commune aux carrousels de découverte multi-services, au Top Streaming par décennie, à la branche Famille, aux enrichissements Netflix et aux bibliothèques globales. Les anciennes entrées `Ma liste`, `Déjà vus` et `Pas intéressé` sont auto-réparées lors des rafraîchissements quand leur poster IMDb peut être résolu.

Un poster IMDb marqué `poster_source: imdb` a priorité lors des fusions multi-provider / bibliothèque afin qu'une ancienne image JustWatch stockée ne puisse plus l'écraser.

## Nouveau 0.6.2 — seuil IMDb et courts métrages configurables

La carte **Top Streaming** peut maintenant filtrer les candidats avant le classement :

```yaml
top_catalog:
  enabled: true
  min_imdb_votes: 20000
  exclude_short_films: true
```

`min_imdb_votes` est le nombre minimal de votes IMDb requis pour entrer dans le pool de classement. `0` désactive ce filtre. La pondération bayésienne note + volume de votes reste ensuite appliquée normalement aux candidats conservés.

`exclude_short_films: true` exclut des branches **Films** et **Animation** les œuvres dont la durée JustWatch est connue et strictement inférieure à **40 minutes**. Le réglage ne s'applique pas aux séries ; une durée inconnue n'est pas exclue arbitrairement.

Ces deux règles s'appliquent également aux sous-branches **Famille**, qui repartent du même pool Top Streaming filtré. Les clés de cache incluent ces réglages afin qu'un changement de configuration produise immédiatement un nouveau classement au prochain rafraîchissement.

## Nouveau 0.6.1 — branche Famille

La carte Top Streaming dispose maintenant d'une quatrième branche **Famille**. Elle conserve la décennie sélectionnée puis propose trois sous-catégories : **Films**, **Animation** et **Séries**.

```yaml
family:
  enabled: true
  target_age: 11
  allow_unrated: false
  movies: true
  animation: true
  series: true
```

`target_age: 11` correspond au besoin « enfants de moins de 12 ans ». La classification **France** est utilisée en priorité. Pour 11 ans, `TP` et `-10` sont acceptés ; `-12`, `-16` et `-18` sont exclus. Lorsqu'aucune classification française n'est disponible, les classifications US peuvent être utilisées si `classification.us_fallback: true`. Elles restent affichées telles quelles : aucune conversion US → FR n'est effectuée.

Les œuvres sans classification exploitable sont exclues avec `allow_unrated: false`. La branche Famille est calculée **à la demande** lorsque l'utilisateur la sélectionne afin de ne pas déclencher des centaines de requêtes de classification pendant un rafraîchissement normal. Les résultats sont mis en cache techniquement pendant 12 h.

`top_count` reste celui de la décennie et représente un **maximum par sous-catégorie Famille**. Si seulement 9 séries adaptées sont trouvées pour un Top 20, la carte affiche 9 séries, sans remplir avec des contenus hors critères.

## Nouveau 0.6.0 — carte Top Streaming par décennie

La 0.6.0 ajoute une deuxième carte Lovelace sans remplacer la carte de découverte existante :

```yaml
type: custom:streaming-top-fr-catalog-card
title: Top Streaming
default_decade: "1990"
default_category: movies
```

Elle construit, pour chaque décennie activée, trois branches indépendantes : **Films**, **Animation** et **Séries**. `top_count` s'applique à chacune des catégories activées. Les œuvres sont limitées aux services activés dans `services:` et aux offres de streaming France hors location/achat seuls.

Le classement utilise la **note IMDb et le volume de votes IMDb exposés par JustWatch**. Une pondération bayésienne est recalculée pour chaque décennie/catégorie : le volume de votes sert de niveau de confiance afin qu'un titre noté très haut avec très peu de votes ne passe pas artificiellement devant un classique massivement évalué. Le seuil de confiance est relatif au pool de la décennie/catégorie, ce qui évite de pénaliser les œuvres anciennes avec les volumes de votes modernes.

Les statuts restent globaux par œuvre et partagés entre les deux cartes. Depuis la **0.6.4**, `Déjà vu` et `Pas intéressé` excluent aussi l'œuvre du classement Top Streaming et de Famille ; le candidat suivant remonte lorsque le pool de réserve le permet. `Ma liste` reste visible dans la découverte.

La popup réutilise les disponibilités multi-services et les destinations configurées dans `players:`. Elle n'ajoute pas de ligne redondante « Disponible sur » : les blocs `Voir sur …` indiquent directement les services disponibles et permettent le lancement lorsqu'il est pris en charge. Les classifications d'âge sont enrichies à l'ouverture de la popup afin d'éviter des centaines de requêtes au chargement du classement.

Le cache du classement est technique (12 h) et sa clé tient compte des services activés, de la décennie, de la catégorie et de `top_count`.

Exemple de configuration :

```yaml
top_catalog:
  enabled: true
  decades:
    "1990":
      enabled: true
      top_count: 65
      movies: true
      animation: true
      series: true

    "2000":
      enabled: true
      top_count: 65
      movies: true
      animation: true
      series: true
```

Les décennies 1920 à 1960 sont désactivées par défaut dans le modèle fourni afin de ne pas générer de requêtes inutiles ; elles peuvent être activées individuellement.

**Base stable :** la 0.6.0 est construite à partir de la **0.5.2 validée**. Tant que la nouvelle carte n'a pas été testée sur l'installation réelle, la 0.5.2 reste la version stable de référence.


## Correctif 0.5.2 — résolution Disney+ France

La disponibilité d'un titre reste déterminée avec **JustWatch France**, mais l'URL Disney+ fournie par JustWatch n'est plus utilisée aveuglément pour la lecture. Certains titres disposent d'un UUID Disney différent selon la région.

Au moment du lancement d'un titre Disney+, l'intégration :

- recherche la fiche sur les surfaces publiques Disney+ France ;
- compare le titre français, le titre original, l'année et le type (film/série) ;
- valide le candidat sur une URL `/fr-fr/browse/entity-...` ;
- rejette les redirections hors de `/fr-fr/` et les pages indiquant une indisponibilité géographique ;
- transmet ensuite l'URL France exacte à la Freebox/Android TV ;
- conserve seulement un **cache technique de 24 h**, puis résout à nouveau la fiche.

Le lien générique JustWatch reste uniquement un candidat de départ : il n'est utilisé que s'il passe la validation France. Si aucune correspondance suffisamment sûre n'est trouvée, le lancement est refusé plutôt que d'envoyer une mauvaise fiche régionale.

Cas de non-régression utilisé pour la validation : **Zootopie 2**. L'UUID générique `8f08a8df-8b2f-49e1-9130-1e842b90f185` provoquait le message d'indisponibilité géographique, tandis que l'entité France `0818ff05-d4fd-4419-92ed-4f907f09bacb` ouvre correctement le titre.

La **0.5.2 est validée comme base stable de référence** pour les évolutions suivantes.

## Nouveautés 0.5.1 — statuts globaux par œuvre

Les statuts ne sont plus rattachés au service depuis lequel l'action a été effectuée. Ils sont stockés globalement par `media_key`.

Conséquences :

- un film marqué **Déjà vu** depuis HBO Max est également exclu des propositions Netflix, Disney+, Prime, etc. lorsque la même œuvre est reconnue ;
- un film marqué **Pas intéressé** disparaît de la découverte de tous les services activés ;
- `Ma liste`, `Déjà vus` et `Pas intéressé` sont des bibliothèques globales, sans doublon par plateforme ;
- les anciens statuts 0.5.0 sont conservés et migrés en mémoire vers le nouveau format.

Chaque œuvre conserve maintenant une table `providers` contenant les disponibilités et les identifiants de lecture propres à chaque service. Une même fiche peut donc connaître Netflix + Disney+ + HBO Max sans dupliquer l'œuvre.

## Destinations de lecture configurables et non limitées

La section `players:` de `/config/streaming_top_fr.yaml` définit les destinations affichées dans les popups. Le nombre de destinations n'est pas limité en dur.

```yaml
players:
  salon:
    name: Salon
    type: android_tv
    media_player: media_player.android_tv_salon
    remote: remote.android_tv_salon
    adb_player: media_player.android_tv_salon_adb

  etage:
    name: Étage
    type: android_tv
    media_player: media_player.android_tv_etage
    remote: remote.android_tv_etage
    adb_player: media_player.android_tv_etage_adb
```

Pour ajouter une destination :

```yaml
  chambre:
    name: Chambre
    type: android_tv
    media_player: media_player.android_tv_chambre
    remote: remote.android_tv_chambre
    adb_player: media_player.android_tv_chambre
```

La popup génère automatiquement les boutons `Salon`, `Étage`, `Chambre`, etc. La clé (`salon`, `etage`, `chambre`) est l'identifiant interne ; `name` est le libellé affiché.

Pour `type: android_tv`, les séquences actuellement validées utilisent `remote` et `adb_player`. `media_player` reste la destination Home Assistant de référence et permettra d'ajouter d'autres modes de lecture plus tard.

## Lecture intégrée à Streaming Top FR

La 0.5.1 n'a plus besoin du mapping `salon/etage` codé en dur dans le frontend. La carte demande directement à l'intégration de lancer le service vers la destination choisie dans `players:`.

Séquences actuellement validées :

- **Netflix** : réveil, redémarrage propre de l'application, profil par défaut, lancement direct du contenu ;
- **Disney+** : réveil, redémarrage propre, deep link du contenu, profil par défaut, lancement ;
- **Prime Video** : réveil, redémarrage propre, ouverture de Prime et validation du profil ;
- **HBO Max / Apple TV+ / Paramount+ / CANAL+ / Crunchyroll / MUBI / ADN** : disponibilité affichée, mais lancement Home Assistant non activé tant que la séquence n'a pas été validée.

## Services configurables

```yaml
services:
  netflix: true
  disney: true
  prime: true
  hbo_max: true
  apple_tv: false
  paramount: false
  canal: false
  crunchyroll: false
  mubi: false
  adn: false
```

Chaque service activé obtient ses carrousels Films / Séries. Netflix conserve son Top 10 officiel France puis sa continuité JustWatch ; les autres utilisent la popularité du catalogue JustWatch France.

## Fenêtre de découverte glissante

```yaml
discovery:
  visible_count: 10
  prefetch_count: 20
  max_depth: 100
```

Avec `10 / 20 / 100`, 10 titres sont visibles et 10 restent en réserve. Lorsqu'un titre sort de la découverte parce qu'il devient `Déjà vu` ou `Pas intéressé`, la réserve remonte et le backend approfondit la source pour revenir à 20 titres non classés.

## Classification d'âge

```yaml
classification:
  enabled: true
  france: true
  us_fallback: true
  us_tv: true
```

France prioritaire ; US uniquement en fallback ; aucune conversion US → France. Le badge reste dans la popup à côté du titre.

## Configuration par interface Home Assistant

La version **0.6.5** utilise encore principalement `/config/streaming_top_fr.yaml` pour les réglages avancés. L'écran d'ajout de l'intégration ne propose actuellement que l'intervalle de rafraîchissement.

Une **IHM complète de paramètres est prévue pour une prochaine version majeure**. L'objectif est de pouvoir gérer depuis **Paramètres → Appareils et services → Streaming Top FR → Configurer** :

- les services de streaming activés ;
- les destinations de lecture Android TV / Freebox ;
- les entités `media_player`, `remote` et `adb_player` avec sélecteurs Home Assistant ;
- le nombre de titres visibles, la réserve et la profondeur de découverte ;
- le seuil minimal de votes IMDb et l'exclusion des courts métrages ;
- les décennies et le nombre de titres par catégorie ;
- le mode Famille et l'âge cible ;
- les règles de classification FR / US ;
- à terme, les options de filtrage géographique des votes IMDb.

La cible est de conserver une migration compatible depuis le YAML existant afin qu'une mise à jour n'oblige pas à ressaisir toute la configuration.

## Configuration Lovelace

Carte de découverte :

```yaml
type: custom:streaming-top-fr-card
title: Streaming
```

Carte de classement historique :

```yaml
type: custom:streaming-top-fr-catalog-card
title: Top Streaming
default_decade: "1990"
default_category: movies
```

## Mise à jour frontend

```text
/streaming_top_fr/streaming-top-fr-card.js
```

Après remplacement des fichiers : redémarrer Home Assistant puis effectuer un rechargement forcé du navigateur. Le bouton **↻** relit `/config/streaming_top_fr.yaml`.
