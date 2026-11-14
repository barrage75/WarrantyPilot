# API

Toutes les routes sont sous `/api`. Les réponses utilisent les contrats
Pydantic; `backend/app/contracts/openapi.json` est la référence générée.

| Méthode | Route | But |
|---|---|---|
| GET | `/health` | Santé du processus |
| GET | `/cases` | Liste des dossiers |
| GET | `/cases/{id}` | Détail d'un dossier |
| GET | `/cases/{id}/events` | Événements vérifiables du dossier |
| GET | `/cases/{id}/stream` | Événements SSE; `after` reprend après un numéro de séquence |
| GET | `/cases/{id}/checklist` | Lire la liste des sept étapes pour les données du PC |
| POST | `/cases/{id}/checklist/{step_name}` | Compléter une étape avec `person_id` |
| POST | `/cases/{id}/validate` | Valider avec `person_id` |
| POST | `/cases/{id}/reject` | Rejeter avec `person_id` et un motif |
| POST | `/cases/{id}/manual-takeover` | Transférer un dossier en échec à une personne (`person_id`) |
| POST | `/cases/{id}/manual-proof` | Saisir une preuve humaine (`person_id`, `proof`) et marquer l'envoi comme prouvé |
| GET | `/journal/verify` | Vérifier chaîne et ancrages |
| POST | `/journal/anchor` | Ancrer l'empreinte courante |
| GET | `/agent/status` | État pause/reprise |
| POST | `/agent/pause` | Mettre l'agent en pause |
| POST | `/agent/resume` | Reprendre l'agent |
| GET / PUT | `/settings` | Lire ou modifier les réglages |
| POST | `/demo/reset` | Réinitialiser la base de démonstration |
| GET | `/demo/preflight` | Contrôles de préparation de la démo |
| POST | `/dev/fake-case` | Créer et lancer un cas fictif (uniquement si `WP_ENV=dev`) |

Les routes de validation et rejet renvoient 409 si le dossier n'est pas en
attente de validation; les identifiants inconnus renvoient 404. L'API L0 est
locale et sans authentification : ne pas la publier sur un réseau.
La prise en main manuelle est possible depuis `failed`; la preuve humaine
produit un `ActionResult` réussi et un événement `action_succeeded` attribué à
`human:<id>`.

Les types détaillés de requête et de réponse sont dans
`backend/app/contracts/openapi.json`, généré avec `make openapi`.
