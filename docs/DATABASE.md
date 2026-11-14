# Base et journal

La migration initiale Alembic crée les tables `people`, `equipment`,
`documents`, `facts`, `rules`, `rights`, `incidents`, `verdicts`,
`policy_decisions`, `cases`, `actions`, `action_results`, `data_checklists`,
`purchase_requests`, `settings`, `events` et `case_steps`.

`actions.idempotency_key` est unique. `case_steps` possède une contrainte
unique `(case_id, step_name)` et garde l'ordre, l'état, le nombre de tentatives,
la sortie structurée et l'heure de mise à jour.
La base impose aussi les états autorisés des étapes et des dossiers, le
catalogue fermé des événements, `documents.untrusted = true` et une preuve non
vide pour tout résultat d'action réussi.

`POST /api/demo/reset` efface la base SQLite locale et les ancrages, réapplique
la migration Alembic jusqu'à `head`, puis insère les données fictives.

## Journal

SQLite refuse les opérations `UPDATE` et `DELETE` sur `events` avec des
triggers. Chaque événement est sérialisé en JSON canonique (clés triées,
aucun espace superflu), puis son empreinte est calculée ainsi :

```text
SHA-256(prev_hash || canonical_json)
```

Le premier `prev_hash` est composé de 64 zéros. Les clés de payload contenant
`key`, `token`, `secret` ou `password` sont masquées avant stockage. Les
ancrages HMAC-SHA256 vont dans `runtime/anchors/anchors.jsonl`, hors base et
ignoré par Git. Le contrôle peut détecter une altération; il ne prétend pas
l'empêcher si une personne contrôle entièrement la machine et la clé.

Les corrections doivent être ajoutées comme nouveaux événements, jamais par
réécriture de la ligne d'origine.
