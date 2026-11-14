# Architecture L0

## Modules et flux

```text
UI (React) ──HTTP/SSE──> FastAPI routers
                            │
                    contracts (Pydantic)
                            │
       ┌────────────────────┴─────────────────────┐
       │ core: orchestration, policy, security, DB │
       └───────────────┬──────────────────────────┘
                       │ injected Protocols
          ingestion · rules · action · follow-up
                       │
                 SQLAlchemy / SQLite
                       │
              append-only event journal
```

Chaque dossier possède des étapes persistées et peut reprendre après un arrêt.
Les contrats de `backend/app/contracts` sont la source de vérité partagée; les
adaptateurs implémentent les Protocols sans modifier ces contrats. L0 ne branche
que des fakes.

## Frontières de confiance

- Les documents importés, faits extraits, textes de courriels ou de pages et
  sorties de modèle sont non fiables; aucun ne peut accorder une capacité
  d'action.
- Le répartiteur vérifie côté serveur la pause, la liste blanche d'adresses
  e-mail et les origines URL locales exactes avant tout adaptateur.
- Une approbation humaine est un événement du journal attribué à un identifiant
  humain fourni par l'appelant. L'API L0 n'authentifie pas cet identifiant; le
  service reste réservé à localhost. Un envoi concernant un PC exige aussi les
  sept étapes de la liste de contrôle, avec une personne identifiée pour les
  étapes sensibles.
- `.env` et les données d'exécution restent locales et sont ignorées par Git.
  L'API n'a pas d'authentification en L0 : elle doit rester liée à localhost.

## Cycle d'un dossier

`prepared → awaiting_validation → sending → sent → tracked → resolved`.
`sent` exige un résultat d'adaptateur réussi avec une preuve non vide. Un envoi
en échec ou interrompu ne peut pas être présenté comme envoyé. Les tentatives
sont limitées et chaque envoi possède une clé d'idempotence. L'orchestrateur
enregistre l'étape `execute` avant l'appel à l'adaptateur; au redémarrage, un
résultat inconnu devient donc `failed`, jamais `sent`.

Le contrat `CaseStatus` ne contient pas d'état `manual`, contrairement à la
formulation du plan sur le repli après deux échecs. L0 garde le dossier en
`failed` (nouvelle tentative bornée ou annulation); le repli manuel doit être
tranché avant d'ajouter un état ou un flux dédié.

Les lots suivants possèdent leurs adaptateurs selon `OWNERSHIP.md`.
