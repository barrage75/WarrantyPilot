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
que des fakes. Le répartiteur sélectionne l'adaptateur par `Verdict.channel`,
puis par `Case.channel` si le verdict ne précise aucun canal.

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
résultat inconnu devient `failed` ou `manual_takeover` si les deux essais sont
épuisés, jamais `sent`. Un dossier `failed` peut être repris par un humain;
seule une preuve saisie par une personne permet alors la transition vers
`sent`.

Les lots suivants possèdent leurs adaptateurs selon `OWNERSHIP.md`.
