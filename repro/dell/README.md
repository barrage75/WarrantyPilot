# Reproduction locale Dell France

Démo autonome, données fictives uniquement. Aucun accès aux services Dell.

```sh
uv sync
uv run python -m dell_repro
```

**Local uniquement (127.0.0.1) — ne jamais publier ni déployer, ne jamais demander de vrais identifiants.**

Écoute exclusivement sur `127.0.0.1:8100`. `DELL_REPRO_PORT` modifie uniquement le port.
Identifiants de démonstration : `demo.appelia@reproduction.local` / `demo-only`.
Ne jamais utiliser d’identifiants ni de données réelles.

Les références observées sont celles de Dell France (collecte 2026-11-14).
Les photos ne sont pas reprises. Le formulaire détaillé, les pages de dossier, le mot
de passe et le message « L'adresse e-mail ou le mot de passe est incorrect. » sont
des hypothèses de démonstration, pas des écrans ou libellés Dell vérifiés.
### Provenance des éléments visuels

| Élément | Provenance et adaptations |
| --- | --- |
| Logo Dell Technologies | SVG intégré à https://www.dell.com/support/home/fr-fr, sélecteur `header svg.dellTechLogo` (premier), extrait le 2026-11-14. Couleur `#0076ce` intégrée via attribut `fill` et style `path` pour conserver son bleu hors de la page source. |
| Favicon | https://www.dell.com/cdn/assets/di/idp/dwa/favicon.ico, collecté le 2026-11-14. |
| Roboto 300/400/500 | Fontsource `@fontsource/roboto@4.5.8`, fichiers `roboto-latin-<poids>-normal.woff2` sous `https://cdn.jsdelivr.net/npm/@fontsource/roboto@4.5.8/files/`. Apache 2.0, texte complet dans `static/fonts/LICENSE`, provenance détaillée dans `static/fonts/SOURCES.txt`. |
| Icônes | SVG au trait dessinés pour la reproduction, dans `templates/icons.html` ; aucune bibliothèque d’icônes Dell copiée. |
| Bannières | Aplats et dégradés CSS originaux. Aucune photo Dell, ni de personnes ni de produits. |

Toutes les ressources sont servies localement. Les URL ci-dessus servent uniquement
à documenter la provenance ; le navigateur ne les appelle pas.

### Service Tags fictifs

| Tag | Modèle | Service | Fin de garantie |
| --- | --- | --- | --- |
| `7XK4L93` | Latitude 7440 | ProSupport Plus, Keep Your Hard Drive | 11/03/2028 |
| `4HB2QM2` | Latitude 5430 | Basic Onsite | 30/06/2024 (expiré) |
| `9QF7R12` | OptiPlex 7010 | ProSupport | 15/01/2027 |
| `2MJ8C54` | Precision 3581 | ProSupport | 20/12/2026 |
| `ZZZ0000` | Inconnu | Aucun produit correspondant | — |

Les statuts sont calculés à la date du jour. « Expire bientôt » signifie moins de
90 jours avant échéance. Les tests figent la date au 14/11/2026.

SQLite et PDF : `runtime/` (ignoré par Git), ou dossier choisi par
`DELL_REPRO_RUNTIME` pour l’isolation des tests. Redémarrer invalide les sessions signées.
`DELL_REPRO_TODAY` (YYYY-MM-DD), `DELL_REPRO_NOW` (ISO), `DELL_REPRO_SEED`
permettent des scénarios déterministes. `DELL_REPRO_FAIL=500|timeout|slow` active
une panne ; surcharge possible par `__fail` (query ou champ de formulaire).
Délais : `DELL_REPRO_TIMEOUT_SECONDS` (35), `DELL_REPRO_SLOW_SECONDS` (8).
Les endpoints `/__test__/cases`, `/__test__/reset`, `/__test__/advance/<numero>`
sont réservés aux clients loopback. Le contournement `allow_testclient=True`
est uniquement une option explicite de la fabrique Python utilisée par les tests.

### Routes

| Méthode | Chemin | Usage |
| --- | --- | --- |
| GET | `/` | Redirection vers l’accueil |
| GET | `/support/home/fr-fr?servicetag=...` | Recherche par Service Tag |
| GET/POST | `/myaccount/fr-fr/signin?next=...` | Connexion démo en deux étapes |
| POST | `/myaccount/fr-fr/signout` | Déconnexion |
| GET | `/support/home/fr-fr/product-support/servicetag/<TAG>/overview` | Produit et garantie |
| GET/POST | `/support/incidents-online/fr-fr/servicerequest?servicetag=<TAG>` | Formulaire protégé et création idempotente |
| GET | `/support/incidents-online/fr-fr/servicerequest/confirmation/<numero>` | Confirmation et récapitulatif |
| GET | `/support/status/<numero>` | État et historique |
| GET | `/__test__/cases` | Liste JSON des dossiers |
| POST | `/__test__/reset` | Efface dossiers et pièces jointes |
| POST | `/__test__/advance/<numero>` | Avance d’un état, 409 si clôturé |

Les endpoints de test refusent les clients autres que `127.0.0.1`/`::1`. Host reste
limité à `127.0.0.1`/`localhost`. Ils ne constituent pas une API de production.

### Modes de panne

`__fail` se transmet dans la query du POST ou dans le champ caché du formulaire
(la query du GET initialise ce champ). À défaut, `DELL_REPRO_FAIL` s’applique.

| Mode | Résultat |
| --- | --- |
| `500` | Erreur 500, aucun dossier créé |
| `timeout` | Attente asynchrone, puis 504, aucun dossier créé |
| `slow` | Attente asynchrone, puis succès normal |
| Autre valeur non vide | Erreur 400 |

### Vérification / CI locale

Depuis `repro/dell/`, commande complète (aucun déploiement) :

```sh
uv sync --locked && uv run playwright install --with-deps chromium && uv run ruff check . && uv run ruff format --check . && uv run mypy && DELL_REPRO_SCREENSHOTS="$HOME/dell_shots" uv run pytest -v
```

Les tests marqués `e2e` démarrent un vrai sous-processus sur un port loopback libre,
avec base temporaire et Chromium headless à 1440 px de large. Ils contrôlent aussi
l’absence de requêtes externes. `uv run pytest -m e2e -v` limite l’exécution à ces
parcours. Sans `DELL_REPRO_SCREENSHOTS`, ils n’enregistrent aucune capture.
