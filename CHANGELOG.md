# Changelog

## 0.7.0-beta.3
- Corrige les libellés manquants du menu **Configurer** pour **Synthèse** et **Décennie par défaut**.
- Réorganise les réglages des décennies : **Décennies** sert à modifier les paramètres détaillés d'une décennie ; **Décennie par défaut** devient une section séparée.
- La décennie par défaut sélectionnée est automatiquement conservée comme active.
- Version de développement : `0.7.0-beta.3`.

## 0.7.0-beta.2
- Ajoute une page **Synthèse** en tête du menu **Configurer**.
- La synthèse est en lecture seule et affiche les valeurs réellement actives : fréquence d'actualisation, services, découverte, Top/IMDb, décennies et volumes, Famille, classifications et destinations de lecture.
- Les décennies affichent également leurs catégories actives (🎬 Films · ✨ Animation · 📺 Séries).
- Ajoute un réglage **Décennie par défaut** dans l'IHM ; la carte Top Streaming l'utilise automatiquement, sauf surcharge locale explicite via `default_decade:` dans le YAML Lovelace.
- Version de développement : `0.7.0-beta.2`.

## 0.7.0-beta.1
- Ajoute un **assistant de configuration natif Home Assistant** affiché dès l'ajout de l'intégration.
- L'assistant configure successivement : fréquence d'actualisation, services de streaming, découverte, Top Streaming / IMDb, décennies, Famille, classifications et destinations Android TV / Freebox.
- Ajoute un **Options Flow** accessible via **Paramètres → Appareils et services → Streaming Top FR → Configurer**.
- Le menu Configurer permet de modifier séparément : Général, Services, Découverte, Top Streaming, chaque décennie, Famille, Classifications et Destinations de lecture.
- Les destinations utilisent les sélecteurs d'entités Home Assistant pour `media_player`, `remote` et le `media_player` Android Debug Bridge.
- Les destinations peuvent être ajoutées, modifiées, renommées ou supprimées depuis l'IHM.
- Migre automatiquement les réglages de `/config/streaming_top_fr.yaml` vers les options natives lors du premier démarrage en v0.7, sans modifier ni supprimer le YAML.
- Conserve la compatibilité de retour vers la v0.6.5 en gardant la version majeure de ConfigEntry inchangée.
- Les nouvelles installations UI ne créent plus de destinations d'exemple fictives.
- Ajoute les traductions FR/EN complètes et `strings.json`.
- Ajoute une validation GitHub Actions : compilation Python, JSON et syntaxe JavaScript.
- Version de développement : `0.7.0-beta.1`.

## 0.6.5
- **Version stable validée via HACS** : installation depuis le dépôt public, création de l'intégration, chargement backend, cartes Lovelace et fonctionnement général testés avec succès.
- Met à jour le texte du flux de configuration pour refléter le support multi-services actuel.
- Ajoute le branding officiel Streaming Top FR (`brand/icon.png` et `brand/logo.png`) pour Home Assistant/HACS.
- Le pool du Top est désormais défini par **JustWatch `POPULAR` France**, puis classé par qualité IMDb pondérée.
- IMDb ne détermine plus la pertinence France ; il départage seulement les candidats déjà populaires localement.
- Ajoute un fallback US strictement secondaire si le pool France ne suffit pas ; tous les candidats France restent devant les candidats US.
- Le fallback US utilise uniquement le signal de popularité US : disponibilité, métadonnées localisées et offres restent vérifiées en France sur les services activés.
- Ajoute les champs d'audit `popularity_market`, `popularity_rank`, `fr_popularity_rank` et `us_popularity_rank`.
- Famille hérite du même pool France-first.
- Invalide les anciens classements via `top-catalog-v5` et `top-family-v5`.
- Frontend : `/streaming_top_fr/streaming-top-fr-card.js?v=0.6.5`.

## 0.6.4
- Uniformise les statuts globaux sur **toutes les zones de découverte** : carrousels multi-services, Top Streaming Films, Animation, Séries et branche Famille.
- Une œuvre marquée `Déjà vu` ou `Pas intéressé` disparaît désormais immédiatement de tous les flows de découverte, quelle que soit la catégorie depuis laquelle le statut a été posé. `Ma liste` reste visible dans la découverte.
- Les œuvres continuent d'être enregistrées dans les buckets globaux `Déjà vus` et `Pas intéressé`; les retirer de ces buckets les rend à nouveau éligibles aux listes de découverte lors du rafraîchissement.
- Le Top Streaming conserve maintenant un **pool classé de réserve** : lorsqu'un titre est exclu par statut, le titre suivant remonte afin de préserver `top_count` tant que le pool contient assez de candidats.
- La branche Famille conserve elle aussi un pool éligible de réserve et applique les mêmes exclusions globales avant de recalculer les rangs visibles.
- Ajoute un garde-fou frontend qui masque `Déjà vu` / `Pas intéressé` même si une réponse de cache ancienne était encore affichée pendant le rafraîchissement.
- Synchronise les deux cartes ouvertes sur le même dashboard : un changement de statut ou une restauration depuis un bucket déclenche le rechargement de l'autre carte, y compris l'invalidation du cache Famille frontend.
- Invalide les caches Top/Famille précédents via les générations `top-catalog-v4` / `top-family-v4`, sans toucher aux autres caches persistants.
- Frontend : `/streaming_top_fr/streaming-top-fr-card.js?v=0.6.4`.

## 0.6.3
- IMDb devient la source canonique des posters via `imdb_id`; le poster JustWatch est conservé uniquement en fallback.
- Ajoute une récupération GraphQL IMDb des `primaryImage`, avec requêtes batchées (jusqu'à 20 IDs par appel) et cache dédié de 90 jours par IMDb ID.
- Étend les requêtes JustWatch `POPULAR`, `SEARCH` et `DETAIL` pour récupérer `externalIds.imdbId` directement et éviter les recherches IMDb par titre lorsque l'identifiant canonique est déjà disponible.
- Applique la politique de poster IMDb aux carrousels multi-services, à Netflix officiel + enrichissement JustWatch, au Top Streaming par décennie et à la branche Famille.
- Les bibliothèques globales (`Ma liste`, `Déjà vus`, `Pas intéressé`) sont auto-réparées au rafraîchissement : les anciens posters JustWatch sont remplacés par l'affiche IMDb lorsqu'elle est disponible.
- Les fusions d'œuvres backend/frontend donnent priorité à `poster_source: imdb`, empêchant un ancien poster stocké d'écraser l'affiche canonique.
- Invalide uniquement les caches Top/Famille (`v3`) et les anciennes entrées Netflix dépourvues de `poster_source`; les caches de classification existants restent conservés.
- Conserve toutes les fonctions et réglages validés de la 0.6.2 (`min_imdb_votes`, exclusion des courts métrages, Famille, statuts globaux, multi-services, players, Disney+ France).
- Frontend : `/streaming_top_fr/streaming-top-fr-card.js?v=0.6.3`.

## 0.6.2
- Ajoute `top_catalog.min_imdb_votes` (défaut `20000`) pour imposer un seuil minimal de votes IMDb avant la pondération bayésienne. `0` désactive le seuil.
- Ajoute `top_catalog.exclude_short_films` (défaut `true`). Quand actif, les Films/Animations dont la durée JustWatch connue est strictement inférieure à 40 minutes sont exclus ; les Séries ne sont pas concernées.
- Le filtre s'applique aux branches Top Streaming normales et aux sous-branches Famille.
- Les clés de cache Top/Famille incluent le seuil de votes et le réglage courts métrages, évitant de réutiliser un ancien classement après modification de la configuration.
- Les configurations existantes qui possèdent déjà `top_catalog:` reçoivent automatiquement les deux nouvelles clés sans remplacer les autres valeurs utilisateur.
- La ligne de source de la carte rappelle le seuil IMDb actif et l'exclusion des courts métrages.
- Frontend : `/streaming_top_fr/streaming-top-fr-card.js?v=0.6.2`.

## 0.6.1
- Ajoute une quatrième branche **Famille** à la carte `custom:streaming-top-fr-catalog-card`.
- La branche Famille est chargée **à la demande** : aucune vérification massive des classifications d'âge n'est faite pendant le rafraîchissement normal du catalogue.
- Ajoute `family:` dans `/config/streaming_top_fr.yaml` avec `enabled`, `target_age`, `allow_unrated`, `movies`, `animation`, `series`.
- Valeur par défaut `target_age: 11` : filtre destiné aux enfants de moins de 12 ans.
- Le filtre âge donne la priorité à la classification française : `TP` et `-10` sont admis pour 11 ans ; `-12`, `-16`, `-18` sont exclus.
- Si aucune classification FR n'existe et si `classification.us_fallback` est actif, le filtre peut utiliser la classification US sans jamais la convertir en classification française.
- Pour le filtrage US, les seuils conservateurs sont : G=0, PG=10, PG-13=13, R=17, NC-17=18 ; TV-Y=0, TV-Y7=7, TV-G=0, TV-PG=10, TV-14=14, TV-MA=17. Ces seuils servent uniquement au filtre Famille.
- `allow_unrated: false` exclut par défaut les titres sans classification exploitable.
- Dans Famille, un second sélecteur propose **Films / Animation / Séries** en respectant les catégories activées pour la décennie et dans `family:`.
- `top_count` reste un maximum par sous-catégorie Famille : aucune œuvre n'est ajoutée artificiellement si le nombre de titres éligibles est inférieur.
- Le classement IMDb pondéré reste identique ; le filtre Famille s'applique ensuite sur un pool profond jusqu'à 100 candidats et le rang Famille est recalculé sur les résultats admissibles.
- Les statuts globaux, disponibilités multi-services, popup et lancements de la 0.6.0/0.5.2 sont conservés.
- Frontend : `/streaming_top_fr/streaming-top-fr-card.js?v=0.6.1`.

## 0.6.0
- Ajoute une deuxième carte Lovelace `custom:streaming-top-fr-catalog-card` pour les classements historiques disponibles en streaming France.
- Ajoute `top_catalog:` dans `/config/streaming_top_fr.yaml`, avec activation par décennie, `top_count` et switches indépendants `movies`, `animation`, `series`.
- `top_count` s'applique séparément à chaque catégorie activée.
- Valeurs initiales reprises de la conception validée : 1920=3, 1930=5, 1940=5, 1950=15, 1960=5, 1970=12, 1980=20, 1990/2000/2010/2020=65.
- Les décennies 1920–1960 sont désactivées par défaut pour limiter les requêtes ; elles restent activables individuellement.
- Sépare les branches Films (hors animation), Animation (longs métrages) et Séries. Les séries animées restent dans Séries.
- Filtre les résultats aux services activés dans `services:` et aux offres France de streaming (FLATRATE / FLATRATE_AND_BUY / ADS / FREE), sans location/achat seuls.
- Classe les candidats avec une pondération bayésienne note IMDb + nombre de votes IMDb, recalculée par décennie/catégorie.
- Les données IMDb utilisées pour le classement sont `imdbScore` et `imdbVotes` fournies par JustWatch France ; fallback de tri JustWatch `POPULAR` si l'enum `IMDB_SCORE` n'est pas accepté, puis re-classement local identique.
- Conserve les `media_key` JustWatch : les statuts sont partagés avec la carte Streaming Top FR 0.5.2.
- Les œuvres classées Vu / Pas intéressé restent visibles dans le classement historique ; leur statut est seulement reflété par les boutons.
- Réutilise la popup, les disponibilités multi-services, les players configurables/illimités et les lancements Netflix / Disney+ / Prime validés.
- Ajoute un enrichissement lazy des classifications d'âge à l'ouverture de la popup pour éviter des centaines de requêtes initiales.
- Ajoute un cache technique de 12 h pour les branches de classement.
- Frontend : la ressource existante `streaming-top-fr-card.js?v=0.6.0` expose désormais les deux custom cards.

## 0.5.2
- Corrige le lancement Disney+ quand l'UUID fourni par l'offre JustWatch correspond à une entité générique ou étrangère alors que le titre est disponible en France.
- JustWatch France reste la source de disponibilité ; la lecture Disney+ passe désormais par une résolution spécifique de la fiche publique Disney+ France au moment du lancement.
- Le résolveur utilise le titre français, le titre original, l'année et le type de contenu pour sélectionner une correspondance.
- Les candidats sont validés sur `/fr-fr/browse/entity-...`; les redirections hors de la locale France et les pages d'indisponibilité géographique sont rejetées.
- L'URL Disney+ France résolue est transmise telle quelle à la séquence Android TV au lieu de reconstruire systématiquement une URL générique à partir de l'UUID JustWatch.
- Ajoute un cache technique court de 24 h pour éviter les résolutions réseau répétitives ; ce cache est jetable et n'est pas considéré comme une donnée durable.
- En cas d'absence de correspondance sûre, le lancement s'arrête avec `disney_fr_unresolved` plutôt que d'ouvrir potentiellement une mauvaise entité régionale.
- Cas de non-régression : Zootopie 2, UUID générique `8f08a8df-8b2f-49e1-9130-1e842b90f185` vs UUID France `0818ff05-d4fd-4419-92ed-4f907f09bacb`.
- Frontend : `streaming-top-fr-card.js?v=0.5.2`.

## 0.5.1
- Rend `Ma liste`, `Déjà vus` et `Pas intéressé` globaux par œuvre (`media_key`) et non plus dépendants du provider actif.
- Corrige le bug HBO Max où un titre quittait `À découvrir` mais n'apparaissait pas immédiatement dans la rubrique correspondante.
- Les compteurs des trois bibliothèques sont désormais globaux par type Films / Séries.
- `Déjà vu` et `Pas intéressé` continuent d'exclure globalement l'œuvre des carrousels de tous les services activés.
- Ajoute une table `providers` par œuvre afin de fusionner les disponibilités multi-services et de conserver les IDs/URLs de lecture propres à chaque plateforme.
- JustWatch expose maintenant, pour une œuvre, les autres services activables connus à partir de ses offres France.
- Passe le cache métadonnées au schéma 9 afin que les titres Netflix déjà mis en cache récupèrent aussi leur table multi-provider.
- Migre sans perte les éléments stockés en 0.5.0 : leur provider historique est converti vers le nouveau format multi-provider.
- Ajoute la section `players:` dans `/config/streaming_top_fr.yaml`. Le nombre de destinations n'est pas limité en dur.
- Les boutons de destination des popups sont générés dynamiquement à partir de `players:`.
- Ajoute un service de lancement interne via WebSocket : Netflix / Disney+ / Prime utilisent directement les entités `remote` et `adb_player` de la destination choisie.
- Supprime le mapping frontend codé en dur `Salon / Étage`; une troisième destination ou davantage peut être ajoutée sans modifier la carte.
- Conserve HBO Max et les autres nouveaux services en consultation uniquement tant que leur séquence de lancement n'est pas validée.
- Frontend : `streaming-top-fr-card.js?v=0.5.1`.

## 0.5.0
- Ajoute la section `services:` dans `/config/streaming_top_fr.yaml`.
- Permet d'activer/désactiver individuellement Netflix, Disney+, Prime Video, HBO Max, Apple TV+, Paramount+, CANAL+, Crunchyroll, MUBI et ADN.
- Génère dynamiquement les onglets de plateformes selon la configuration.
- Ajoute les carrousels Films / Séries pour chaque service activé via JustWatch France.
- Conserve Netflix comme cas spécial : Top 10 officiel France + continuité JustWatch.
- Les nouveaux services n'affichent pas de boutons Freebox tant que leur lancement n'a pas été validé ; Netflix / Disney+ / Prime restent inchangés.
- Ajoute des wordmarks CSS légers pour les nouveaux services, sans dépendance d'image externe.
- Avec plus de quatre services actifs, le sélecteur devient horizontalement scrollable pour rester utilisable sur mobile.
- Optimise les classifications d'âge : les titres visibles sont enrichis en priorité, la réserve l'est lorsqu'elle remonte.
- Les configurations 0.4.x existantes sont migrées automatiquement en ajoutant la section `services:` avec les trois plateformes historiques activées.
- Aucun changement au mécanisme de fenêtre glissante, aux statuts ni aux scripts de lecture validés.

## 0.4.1
- Corrige les compteurs et les rubriques `Ma liste`, `Déjà vus` et `Pas intéressé` pour les **films**.
- Cause : l’interface utilise le bucket `movies` alors que les éléments stockés utilisent `media_type: movie`; le filtre comparait donc `movie` à `movies` et rejetait tous les films stockés.
- Normalise désormais `movies` → `movie` pour les compteurs et l’affichage des listes.
- Les statuts déjà enregistrés dans le stockage Home Assistant sont conservés : ils doivent réapparaître après mise à jour.
- Aucun changement au mécanisme de fenêtre glissante/prefetch ni à la lecture Netflix / Disney+ / Prime.

## 0.4.0
- Ajoute `/config/streaming_top_fr.yaml`, créé automatiquement au premier démarrage.
- Ajoute les switches de classification : affichage global, France, fallback US, classifications US TV.
- Conserve le rendu validé : France en rond gris clair / texte noir ; US en rectangle anthracite / texte blanc ; aucune conversion.
- Ajoute `visible_count`, `prefetch_count` et `max_depth` pour piloter la découverte.
- Implémente une fenêtre glissante toujours pleine : les titres `Déjà vus` / `Pas intéressé` sont remplacés 1 pour 1 jusqu'à `max_depth`.
- La source approfondit sa requête seulement du nombre nécessaire pour reconstituer `prefetch_count`.
- Netflix conserve uniquement les rangs officiels #1 à #10 ; les continuations JustWatch n'affichent aucun faux rang.
- Les images restent chargées en lazy-loading : seuls les posters réellement affichés sont téléchargés par le navigateur.
- `visible_count` est un entier configurable avec un pas de 1.
- Cache metadata porté au schéma 8 pour stocker séparément les classifications FR et US.

## 0.3.4
- Corrige la récupération IMDb des classifications : lecture de la liste complète des certificats du guide parental, avec priorité France puis fallback US.
- Une classification US n'est jamais convertie en classification française.
- Ajoute un fallback HTML IMDb puis un fallback certificat US principal si nécessaire.
- Force le rendu demandé : France (TP/-10/-12/-16/-18) = rond gris clair, texte noir ; US (G/PG/PG-13/R/NC-17/TV-*) = rectangle gris très foncé, texte blanc.
- Incrémente le cache metadata pour purger les classifications erronées/manquantes des versions précédentes.
- Aucun changement dans la lecture Netflix / Disney+ / Prime ni dans les popups et boutons déjà validés.

## 0.3.3
- Classification d’âge dans la popup uniquement, directement à côté du titre.
- Priorité IMDb France ; fallback classification française JustWatch ; sinon IMDb US sans conversion.
- Nouveau rendu : France = badge rond gris clair / texte noir ; US = rectangle gris très foncé / texte blanc.
- Résolution IMDb renforcée via l’identifiant JustWatch quand disponible, sinon recherche IMDb par titre/année/type.
- Cache métadonnées incrémenté pour forcer le rafraîchissement des classifications.

## 0.3.2
- Déplace le badge d’âge dans la popup, directement à côté du titre.
- Retire le badge d’âge de la ligne de métadonnées des tuiles.
- Ajoute un fallback de récupération sur la page publique JustWatch France lorsque le détail REST ne renvoie pas `age_certification`.
- Bump du cache metadata en schéma 5 pour retenter immédiatement les classifications manquantes.
- Aucun changement dans la logique de lecture Netflix / Disney+ / Prime ni dans les ajustements mobile validés.

## 0.3.1
- Retire le badge de plateforme superposé aux posters.
- Centre les boutons-logo Netflix / Disney+ / Prime.
- Centre les boutons Films / Séries.
- Ajoute la classification d’âge France via le détail JustWatch avec cache local.
- Badges : TP vert, -10 jaune, -12 orange, -16 rouge, -18 rouge foncé.
- Aucun changement dans la logique de lecture validée ni dans le centrage vertical des boutons `Voir sur …`.

## 0.3.0
- Corrige l’affichage des logos Disney+ et Prime sur mobile en supprimant les SVG basés sur `<text>` au profit de wordmarks HTML/CSS robustes.
- Supprime le bouton `Détails` des popups.
- Centre les boutons d’état en bas des popups.
- Conserve le décalage vertical de -3 px du bloc `Voir sur … / Salon-Étage` validé en 0.2.9.
- Aucun changement dans la logique de lecture Netflix, Disney+ ou Prime Video.

## 0.2.9
- Ajuste le centrage vertical des boutons de lecture : le bloc `Voir sur …` + `Salon/Étage` est remonté de 3 px.
- Aucun changement fonctionnel sur Netflix, Disney+ ou Prime Video.

## 0.2.8
- Remplace les icônes MDI de plateformes par des logos SVG embarqués directement dans la carte, sans dépendance externe.
- Corrige l'affichage manquant des logos Disney+ et Prime.
- Les boutons de lecture utilisent désormais un texte blanc forcé sur les fonds teintés, avec contenu centré.
- `Salon` et `Étage` sont affichés plus gros et en gras dans les boutons de lancement.
- Remplace le bouton `Fermer` par un bouton `×` en haut à droite de la popup.
- Réduit encore la popup sur mobile : maximum 360 px et marges renforcées.
- Conserve les couleurs semi-transparentes par plateforme et toute la logique de lecture validée.

## 0.2.7
- Sélecteur Netflix / Disney+ / Prime remplacé par des icônes/logo.
- Ajoute `mdi:filmstrip` devant Films et `mdi:television-play` devant Séries.
- Boutons de lecture de la popup contextualisés : `Voir sur Netflix`, `Voir sur Disney+`, `Lancer Prime`.
- Conserve deux destinations distinctes Salon / Étage, affichées sous le libellé de lecture.
- Styles de lecture semi-transparents teintés par plateforme : rouge sombre Netflix, bleu nuit Disney+, bleu clair/cyan Prime.
- Popup mobile réduite à `calc(100vw - 24px)` avec maximum 420 px et marges renforcées ; passage des boutons de lecture sur une colonne sous 370 px.
- Aucun changement dans la logique de lancement Netflix / Disney+ / Prime.

## 0.2.6
- Corrige la fenêtre de détail tronquée sur mobile.
- Le conteneur modal utilise désormais `box-sizing: border-box`, une largeur réellement limitée au viewport et un centrage robuste.
- Sur écran étroit, la popup utilise toute la largeur disponible avec marges de 10 px et une hauteur maximale basée sur `100dvh`.
- Empêche les boutons `▶ Salon` / `▶ Étage` et les textes longs de provoquer un débordement horizontal.
- Aucun changement dans la logique de lancement Netflix / Disney+ / Prime.

## 0.2.5
- Ajoute `▶ Salon` et `▶ Étage` dans la fiche de chaque tuile.
- Appelle par défaut `script.tv_streaming_freebox_pop` via `script.turn_on` avec `freebox`, `app` et `content_id`.
- Extrait automatiquement l'ID natif Netflix depuis l'offre Netflix JustWatch.
- Extrait automatiquement l'UUID `entity-...` Disney+ depuis l'offre Disney+ JustWatch.
- Prime Video appelle le script sans ID de contenu (ouverture de l'application uniquement).
- Fallback d'extraction des IDs côté carte pour les éléments déjà stockés en `Ma liste` / `Déjà vus`.
- Normalise `N/A` dans les sous-titres Netflix : il n'est plus affiché.
- Notes : IMDb prioritaire, TMDB en fallback ; suppression du score JustWatch de l'affichage.
- Invalide une fois le cache de métadonnées Netflix afin d'ajouter les IDs de lecture.