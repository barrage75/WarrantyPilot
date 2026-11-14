# Décisions techniques

## ADR-001 — FastAPI et React

FastAPI expose les contrats Pydantic et OpenAPI; React/Vite fournit un client
local léger. L0 n'ajoute pas de bibliothèque de composants.

## ADR-002 — Contrats Pydantic et types générés

Les contrats Python sont la source de vérité. OpenAPI est généré depuis
FastAPI, puis les types TypeScript sont générés avec `openapi-typescript`.

## ADR-003 — Un agent produit, adaptateurs injectés

Un seul orchestrateur produit la décision; les intégrations sont des Protocols
injectés. Les adaptateurs d'action sont indexés par `Channel`, choisi d'abord
par le verdict puis par le dossier. L0 ne contient que des fakes afin d'éviter
tout effet externe.

## ADR-004 — Règles YAML, source vérifiable

Les règles métier arrivent dans un lot ultérieur au format YAML. Elles devront
porter source, version et date de consultation; L0 définit déjà leur contrat.

## ADR-005 — Journal à empreintes locales

Le journal est append-only en base et ancré par HMAC dans un fichier séparé.
Les ajouts SQLite utilisent `BEGIN IMMEDIATE` et un verrou local pour sérialiser
les écritures. Cette conception détecte les altérations mais n'est pas
inviolable si la machine et la clé sont toutes deux compromises.

## ADR-006 — Quatre priorités et Gmail à deux scopes

Les fonctions sont rangées P0 à P3 et les fonctionnalités non-P0 sont
désactivables. Le principe futur de Gmail est deux permissions minimales,
séparant lecture restreinte et envoi sensible; L0 ne demande aucun accès Gmail.

## ADR-007 — Limites de parallélisme

Le travail partagé reste à l'intégrateur; au maximum quatre agents de lot
travaillent simultanément, avec un dossier propriétaire par lot.

## ADR-008 — Prise en main humaine après échec

Après deux essais, un dossier passe automatiquement de `failed` à
`manual_takeover`; une personne peut aussi demander ce transfert depuis
`failed`. Le retour à `sent` exige un `ActionResult` réussi avec preuve non vide
et un événement attribué à `human:<id>`. La prise en main manuelle peut aussi
être annulée.
