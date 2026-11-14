# Propriété des dossiers

Répartition reprise de la section 9.2 de `docs/PLAN_V4.md`.

| Lot | Dossiers | Dépend de | Responsable |
|---|---|---|---|
| L0 — noyau : modèles, statuts, orchestrateur, journal, contrats | `backend/app/core`, `backend/app/contracts` | — | Intégrateur uniquement |
| L1 — jeu de données Appelia | `data/appelia` | Contrats | Agent A |
| L2 — lecture des documents, contrôles et Factur-X | `backend/app/ingestion` | Contrats | Agent B |
| L3 — moteur de règles, YAML et cas de référence | `backend/app/rules` | Contrats | Agent C |
| L4a — reproduction du site Dell | `repro/dell` | — | Agent D |
| L5 — interface | `frontend` | Contrat d'API | Agent E |
| L4b — pilotage du navigateur | `backend/app/actions/browser` | L0, L4a | Agent D |
| L6 — Gmail, envoi et suivi des réponses | `backend/app/actions/email` | L0 | Agent B après L2 |
| L7 — garde-fou achat, suivi et relances | `backend/app/purchase_guard`, `backend/app/followup` | L0, L3 | Agent C après L3 |
| L8 — bonus | `backend/app/bonus` | L0 | Agent A après L1 |
| Fichiers partagés | `backend/app/contracts`, `backend/app/core`, `backend/migrations`, dépendances, CI, Makefile et configuration | — | Intégrateur uniquement |

Un agent de lot ne modifie ni les contrats ni les fichiers d'un autre lot.
L'intégrateur gère les changements partagés, les migrations et l'intégration.
Le plan limite à quatre le nombre d'agents de lot travaillant simultanément.
