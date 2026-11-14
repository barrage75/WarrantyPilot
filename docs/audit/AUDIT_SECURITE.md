# Audit sécurité et fiabilité — WarrantyPilot

- **Périmètre** : dépôt `barrage75/gare`, branche `integration`, commit `9368065` (« feat: faits partagés, Paul couvert, envoi auto de démo, captures servies (#31) »).
- **Méthode** : lecture du code, modélisation STRIDE, exécution de la suite existante, scripts de preuve (PoC) lancés **hors dépôt** sur une copie jetable, audit des dépendances, scan des secrets sur tout l'historique.
- **Aucun fichier de code n'a été modifié.** Ce document est le seul fichier ajouté au dépôt ; les scripts de preuve de l'audit sont conservés hors dépôt.
- **Légende** : **[V]** constat vérifié (code lu + PoC ou test qui passe) ; **[H]** hypothèse (déduite du code, non démontrée de bout en bout).

## 0. Synthèse

| # | Gravité | Constat | Statut |
|---|---|---|---|
| C1 | Critique | `PUT /api/settings` sans acteur humain ni journal : allowlist e-mail, origines navigateur et seuil d'envoi automatique modifiables par n'importe quel appelant | [V] |
| C2 | Critique | Aucune authentification : « l'acteur humain » est un `person_id` choisi par l'appelant et listé publiquement par `GET /api/people` (validation, checklist 7 étapes, preuve manuelle) | [V] |
| H1 | Haute | `POST /api/demo/reset` efface base, journal et ancres sans contrôle (ni rôle, ni `demo_mode`, ni `WP_ENV`), accessible en requête « simple » cross-site (CSRF), et `verify` répond ensuite `ok=true` | [V] |
| H2 | Haute | Pas de `TrustedHostMiddleware` ni de contrôle `Origin` sur l'API : rebinding DNS → lecture et écriture de l'API depuis une page web | [V] (Host accepté) / [H] (chaîne navigateur complète) |
| H3 | Haute | `POST /api/purchase-requests/{id}/decision` (`suspend`) crée un dossier et lance l'orchestrateur sous l'acteur fictif `human:purchase-guard`, sans `person_id` | [V] |
| H4 | Haute | Journal : seule l'ancre est signée en HMAC ; la queue non ancrée peut être tronquée et une chaîne sans ancre réécrite sans détection. Clé HMAC par défaut connue | [V] |
| M1 | Moyenne | `manual-proof` accepte n'importe quelle chaîne non vide comme preuve d'envoi (`"x"` → `sent`) | [V] |
| M2 | Moyenne | Allowlist navigateur par défaut du contrat = `localhost:*` et `127.0.0.1:*` (tous ports), en contradiction avec la règle « 127.0.0.1:8100 uniquement » ; seule la liste figée de l'adaptateur sauve la règle | [V] |
| M3 | Moyenne | Injection de prompt dans une facture PDF → date d'achat inventée → verdict `covered` → envoi automatique sous le seuil (300 € après reset) | [H] |
| M4 | Moyenne | Masquage des secrets par **nom de clé** seulement : valeurs libres (`error`, `proof`, `text`) non masquées ; `idempotency_key` est masqué à tort (perte d'auditabilité) | [V] |
| M5 | Moyenne | Les deux étapes « non humaines » et les cinq étapes humaines de la checklist sont validables par un seul et même identifiant en 7 appels, sans ordre ni séparation des rôles | [V] |
| B1 | Basse | Concurrence : deux `run()` simultanés → un seul envoi (sur un essai), mais un appel renvoie `failed` alors que le dossier est `resolved` | [V] |
| B2 | Basse | `cors_origins` déclaré mais jamais utilisé ; `/docs`, `/redoc`, `/openapi.json` exposés | [V] |
| B3 | Basse | Ressources non bornées : `POST /api/scan` et `POST /api/chat/conversations` empilent tâches et états en mémoire (`app.state`) sans limite | [V] (code) / [H] (impact) |
| B4 | Basse | Dépendance : `pytest 8.4.2` (dev) — `PYSEC-2026-1845`, corrigé en 9.0.3 | [V] |
| B5 | Basse | Qualité : `mypy --strict app` → 12 erreurs hors périmètre CI (`app/api`, `app/testing`) ; `ruff` I001 dans `data/appelia/tests/test_dataset.py` | [V] |

**Aucun constat** pour : traversée de chemin (captures), SSRF côté serveur, secrets dans l'historique Git, double envoi e-mail, upload (aucun endpoint d'upload), bind réseau (tout est sur 127.0.0.1). Détails au §3.

## 1. Modèle de menaces (STRIDE)

Hypothèse de déploiement : poste de démo, API sur `127.0.0.1:8001` (Makefile:12), Vite sur `127.0.0.1:5173` (frontend/vite.config.ts:8), SMTP local `127.0.0.1:2525` (backend/app/actions/email/local_smtp_server.py:14), reproduction Dell `127.0.0.1:8100` (repro/dell/dell_repro/__main__.py:7). Attaquants considérés : (A) page web visitée par l'opérateur pendant la démo ; (B) autre processus/utilisateur local ; (C) contenu non fiable (PDF, e-mail, page du portail, sortie LLM).

| Composant | S (usurpation) | T (altération) | R (répudiation) | I (fuite) | D (déni) | E (élévation) |
|---|---|---|---|---|---|---|
| API FastAPI | C2 : `person_id` libre ; H2 : Host non contrôlé | C1 : réglages ; H1 : reset | C1 : changement de réglages non journalisé ; H3 : acteur fictif | Toutes les lectures sans auth (personnes, dossiers, journal) — acceptable seulement en local strict | B3 | C1/C2 : tout appelant = administrateur + valideur |
| Ingestion (Factur-X / PDF+LLM) | — | M3 : faits LLM injectés | — | Envoi du document au fournisseur LLM (Mistral) si configuré | Charge CPU/I/O via `POST /api/scan` répété (extraction Factur-X, pas LLM dans cette route) | M3 : fait → verdict → action |
| Adaptateur e-mail | — | — | Preuve = `message_id` + SHA-256 du contenu (bon) | — | — | Bloqué par double contrôle allowlist + domaine `.example` (bon) |
| Adaptateur navigateur | — | Page du portail = donnée non fiable (prompt injection vers l'agent computer-use) | Capture + n° de dossier + URL (bon) | — | — | Bloqué par allowlist figée + garde Playwright `route("**/*")` (bon) |
| Journal | — | H4 | H4, M4 | M4 (secret dans une valeur libre) | — | — |
| Reset | — | H1 | H1 : efface l'historique | — | H1 | — |
| Frontend | L'identité opérateur est une valeur `localStorage` choisie dans une liste (frontend/src/operator.tsx:5-8) | — | — | Pas de `dangerouslySetInnerHTML`/`innerHTML`/`eval` trouvé dans `frontend/src` | — | — |

## 2. Vérification des règles non négociables

| Règle | Où c'est appliqué (fichier:ligne) | Test existant | Verdict |
|---|---|---|---|
| Aucun envoi hors allowlist e-mail | Orchestrateur `backend/app/core/orchestrator.py:780-784` → `backend/app/core/security.py:10-14` (égalité exacte, casse ignorée) ; adaptateur `backend/app/actions/email/adapter.py:88-97` (destinataire **et** `cc`, + domaine `.example` obligatoire l.92) | `tests/unit/test_security_flags.py::test_email_allowlist_is_exact`, `tests/integration/test_orchestrator.py::test_email_outside_allowlist_is_refused_before_adapter` | **Respectée dans le code, mais contournable par C1** (l'allowlist est modifiable sans contrôle). La garde `.example` limite l'impact réel à des domaines réservés non routables. |
| Aucune navigation hors 127.0.0.1:8100 / localhost:8100 | Liste figée `backend/app/actions/browser/allowlist.py:15`, origines de test uniquement en `test_mode` et en loopback (`backend/app/actions/browser/allowlist.py:33-41`) ; garde Playwright `backend/app/actions/browser/drivers/_session.py:59-88` ; `allowed_domains` browser-use `backend/app/actions/browser/drivers/browser_use.py:61` | `tests/unit/actions/browser/test_browser_allowlist.py` (11 fonctions de test, cas paramétrés supplémentaires), `test_browser_repro_integration.py::test_redirect_outside_allowlist_stops_the_action` | **Respectée par l'adaptateur.** Écart : la valeur par défaut du contrat `backend/app/contracts/models.py:418-420` autorise tous les ports loopback (M2) et `test_security_flags.py::test_url_allowlist_defaults_to_localhost_only` entérine ce défaut. |
| Aucun double envoi | Clé d'idempotence stable `case:{id}:{canal}:{cible}` `backend/app/core/orchestrator.py:573` ; reprise d'un succès antérieur `backend/app/core/orchestrator.py:142-210` ; état « running/unknown_outcome » bloquant `backend/app/core/orchestrator.py:512-521`, `392-394` ; e-mail : verrou + ledger + `find_sent` `backend/app/actions/email/adapter.py:107-136` ; navigateur : store SQLite d'idempotence (`backend/app/actions/browser/store.py`) | `test_orchestrator.py::test_failure_can_retry_once_with_a_stable_idempotency_key`, `test_browser_adapter.py::test_idempotency_survives_a_new_adapter_instance` | **Aucun double envoi observé sur cet essai [V]** — PoC 08 : 2 `run()` concurrents → 1 message livré, 1 `ActionResult` succès. Voir B1. |
| `sent` exige une preuve | `backend/app/core/status.py:48-62` ; `ActionResult` refuse un succès sans preuve `backend/app/contracts/models.py:299-302` ; prise en main manuelle exige un acteur `human:` `backend/app/core/status.py:55-60` | `tests/unit/test_status.py::test_sent_requires_successful_result_with_proof`, `::test_manual_takeover_requires_human_proof_to_reach_sent` | **Respectée formellement**, mais la preuve manuelle n'est pas qualifiée (M1) et l'acteur humain n'est pas authentifié (C2). |
| Documents/e-mails/pages/sorties LLM = données non fiables | Prompt d'extraction `backend/app/ingestion/pdf_llm.py:16-22` + délimiteurs neutralisés (`backend/app/ingestion/pdf_llm.py:87-88`) ; contrôles `ingestion/controls/suspicious.py`, `duplicates.py`, `plausibility.py` ; signal suspect bloquant l'auto-envoi `backend/app/core/orchestrator.py:311-315` + `core/policy.py` ; consigne au pilote `backend/app/actions/browser/drivers/hcompany.py:91-95` ; succès navigateur jamais pris sur parole du LLM (`backend/app/actions/browser/drivers/browser_use.py:1-5`) | `tests/unit/ingestion/test_extractors.py::test_generated_hidden_and_duplicate`, `test_controls.py` | **Partiellement** : aucune sortie LLM ne choisit le destinataire, l'URL ou le canal (bon). Mais une date d'achat extraite par LLM suffit à fonder `covered` puis l'auto-envoi (M3). |
| Journal append-only chaîné SHA-256 + HMAC | Chaîne `backend/app/core/journal.py:94-105` ; triggers SQLite `events_no_update`/`events_no_delete` (backend/migrations/versions/0006_chat_disclosure_event.py:26,35) ; HMAC sur ancres seulement `backend/app/core/journal.py:132-161` ; vérification `backend/app/core/journal.py:164-232` | `tests/unit/test_journal.py` (7 tests : altération, ancre supprimée, concurrence) | **Partiellement** (H4, H1) : HMAC uniquement sur l'ancre, queue non ancrée non protégée, reset qui supprime triggers + journal. |
| Secrets jamais journalisés | `redact_secrets` `backend/app/core/journal.py:20-38` ; `SecretStr` pour les secrets déclarés dans AppSettings et BrowserSettings (`backend/app/core/settings.py:19,26-28`, `backend/app/actions/browser/settings.py:39,44-64`) | `test_journal.py::test_hash_chain_is_valid_and_secrets_are_redacted` | **Partiellement** (M4) : masquage par nom de clé uniquement. |
| Procédure de protection des données PC bloquante (7 étapes validées par un humain) | `DataChecklist.complete()` `backend/app/contracts/models.py:339-352` ; blocage politique `core/policy.py` (`data_checklist_incomplete`) via `backend/app/core/orchestrator.py:299-325`, `346-356` ; re-contrôle juste avant l'action `backend/app/core/orchestrator.py:396-409` | `tests/contract/test_protocols.py::test_data_checklist_requires_all_seven_steps_and_human_signoff`, `test_policy.py::test_pause_and_incomplete_data_checklist_are_blocking` | **Respectée mécaniquement**, mais « un humain » = n'importe quel `person_id` existant fourni par l'appelant (C2, M5). |
| Aucun `covered` sans preuve d'achat et règle connue | Garde `backend/app/rules/engine.py:68-69` ; absence de règle → à vérifier l.229-236 ; preuve d'achat datée obligatoire l.238-242 ; politique : seul `COVERED` peut s'auto-envoyer `backend/app/core/policy.py:27` | `tests/unit/rules/test_engine_cases.py`, `test_appelia_traps.py`, contrat `tests/contract/rules/test_rules_engine_contract.py` | **Respectée** ; la qualité de la « preuve » dépend de l'ingestion (M3). |

## 3. Constats détaillés (par gravité)

### C1 — Critique — Réglages de sécurité modifiables sans acteur humain ni trace [V]

- **Preuve** : `backend/app/api/routers/settings.py:16-27` accepte un `Settings` complet (allowlist e-mail, origines navigateur, seuil, drapeaux) sans `person_id`, sans contrôle et sans `append_event`. `write_settings` (`backend/app/core/settings_store.py:31-50`) n'écrit rien au journal.
- **PoC** `test_01_settings_no_identity_and_no_audit` : `PUT /api/settings` avec `email_allowlist=["attacker@evil.example"]`, `browser_allowed_origins=["http://evil.example:80"]`, `auto_send_threshold_eur=100000` → **200** ; nombre d'événements avant/après : **1/1**.
- **Scénario** : un processus local (ou une page web via H2) passe le seuil à 100 000 € et ajoute une adresse à l'allowlist → tous les dossiers « couverts » partent sans validation humaine, sans aucune trace de qui a changé la règle. L'adaptateur e-mail limite encore aux domaines `.example` et l'adaptateur navigateur garde sa liste figée ; la règle « validation humaine au-dessus d'un seuil » est en revanche entièrement contournée.
- **Correction** : (1) exiger un `person_id` d'un rôle autorisé (ex. `responsable informatique`) + jeton de session opérateur (voir C2) ; (2) journaliser `SETTINGS_CHANGED` avec l'avant/après (champs sensibles en clair, ils ne sont pas secrets) ; (3) refuser côté serveur toute entrée d'allowlist hors `*.example` et toute origine navigateur hors `PRODUCTION_ORIGINS` ; (4) borner `auto_send_threshold_eur` (ex. ≤ 500).
- **Test qui le prouverait** : `PUT /api/settings` sans identité → 401/403 ; avec identité valide → 200 **et** un événement `settings_changed` signé par `human:<id>` ; origine `http://evil.example:80` → 422.

### C2 — Critique — L'« acteur humain » n'est pas authentifié [V]

- **Preuve** : `backend/app/api/dependencies.py:14-17` (`_require_person`) vérifie seulement que l'UUID existe dans `people` ; `GET /api/people` (`backend/app/api/routers/cases.py:170`) publie ces UUID. Utilisé par `validate` (backend/app/api/routers/cases.py:410-429), `reject` (432-465), `manual-takeover` (468-498), `manual-proof` (501-584), `checklist/{step}` (600-660), `confirm-cancellation` (backend/app/api/routers/purchase_guard.py:246-293). Aucun `Depends` d'authentification sur les 34 routes (inventaire : aucune dépendance de sécurité dans `backend/app/api`). Côté interface, l'identité est une valeur choisie et stockée localement (frontend/src/operator.tsx:5-8).
- **PoC** `test_04_impersonate_all_seven_checklist_steps` : un id lu sur `/api/people`, 7 `POST /api/cases/{id}/checklist/{step}` → `DataChecklist.complete() == True`, les 7 étapes signées par ce même id.
- **Scénario** : n'importe quel appelant (script, extension, page via H2) valide un dossier au-dessus du seuil ou signe la procédure de protection des données d'un PC à la place du responsable → le PC part en réparation sans sauvegarde/chiffrement vérifiés. Le journal attribue l'action à un humain qui n'a rien fait (répudiation).
- **Correction** : pour le MVP local, jeton opérateur par session (en-tête `Authorization: Bearer`, généré au démarrage, affiché dans la console, gardé en mémoire par le frontend), lié à une personne ; `person_id` déduit du jeton et non du corps ; contrôle de rôle par endpoint (valideur ≠ demandeur, checklist réservée au rôle informatique). À plus long terme : vraie authentification (OIDC).
- **Test** : `POST /cases/{id}/validate` avec `person_id` valide mais sans jeton → 401 ; jeton de Paul pour valider son propre dossier → 403.

### H1 — Haute — Reset destructif sans garde, exploitable en CSRF, et indétectable [V]

- **Preuve** : `backend/app/api/routers/demo.py:35-41` appelle `reset_demo` sans aucune condition ; `backend/app/core/reset.py:58-82` supprime le Maildir, le ledger d'envoi, le fichier SQLite (ou `DROP TRIGGER events_no_update/events_no_delete` puis `drop_all`), puis le fichier d'ancres. `create_fake_case` (backend/app/api/routers/demo.py:62-63) vérifie `environment != "dev"`, pas `demo_reset`.
- **PoC** `test_02a` : `POST /api/demo/reset` sans corps, `Content-Type: text/plain`, `Origin: http://evil.example` → **200** ; les anciens événements et le fichier d'ancres disparaissent ; `GET /api/journal/verify` → `ok=true`. `test_02b` : idem avec `environment=production`, `demo_mode=False`.
- **Scénario** : une page web visitée pendant la démo envoie `fetch("http://127.0.0.1:8001/api/demo/reset",{method:"POST",mode:"no-cors"})` (requête « simple » : pas de pré-vol CORS) → toutes les preuves, dossiers et le journal « append-only » sont effacés, et la vérification d'intégrité reste verte. [H] pour la partie navigateur : Chrome déploie progressivement des restrictions « Private Network Access » qui peuvent bloquer cet appel ; non testé dans un navigateur réel.
- **Correction** : (1) n'exposer `demo/reset` que si `demo_mode and environment == "dev"`, sinon 404 ; (2) exiger un acteur humain authentifié + corps JSON `{"confirm":"RESET"}` (force le pré-vol CORS) ; (3) archiver avant reset l'ancien journal et le fichier d'ancres (`runtime/archive/<horodatage>/`) et journaliser `DEMO_RESET` avec le hash de la dernière ancre précédente ; (4) vérifier `Origin` (voir H2).
- **Test** : reset avec `Content-Type: text/plain` → 415/422 ; reset avec `demo_mode=False` → 404 ; après reset, un fichier d'archive contient l'ancien journal et `verify` sur l'archive renvoie `ok=true`.

### H2 — Haute — Ni contrôle d'hôte ni contrôle d'origine sur l'API [V]/[H]

- **Preuve** : `backend/app/api/main.py:189-204` crée l'application sans aucun middleware ; `cors_origins` (`backend/app/core/settings.py:30`) n'est référencé nulle part ailleurs. À comparer avec la reproduction Dell qui, elle, pose `TrustedHostMiddleware` (`repro/dell/dell_repro/app.py:116`).
- **PoC** `test_03` : `GET /api/cases` avec `Host: attacker.example` → **200** ; pas d'en-tête `Access-Control-Allow-Origin`.
- **Scénario** (rebinding DNS, [H]) : `attacker.example` résout d'abord vers son serveur puis vers `127.0.0.1` ; la page, désormais « même origine », lit `/api/people`, puis appelle `PUT /api/settings` (C1) et `POST /cases/{id}/validate` (C2) avec du JSON. L'absence de CORS bloque la lecture cross-origin classique mais pas ce scénario ni les POST simples (H1).
- **Correction** : `TrustedHostMiddleware(allowed_hosts=["127.0.0.1","localhost"])` ; middleware qui refuse toute méthode non sûre dont l'en-tête `Origin` n'est pas dans `cors_origins` ; `CORSMiddleware` explicite avec `cors_origins` ; jeton de C2.
- **Test** : `Host: attacker.example` → 400 ; `POST` avec `Origin: http://evil.example` → 403 ; avec `Origin: http://localhost:5173` → 200.

### H3 — Haute — Décision d'achat qui déclenche l'orchestrateur sans humain identifié [V]

- **Preuve** : `backend/app/api/routers/purchase_guard.py:186-243` : pas de `_require_person` ; acteur codé en dur `human:purchase-guard` (l.213, 229, 239) — un « humain » qui n'est pas une personne ; `choice=suspend` crée un dossier (`_ensure_linked_case`, l.124-173) puis `await orchestrator.run(case_id)` (l.234). `resolve-case` (l.296-327) relance aussi l'orchestrateur sans acteur.
- **PoC** `test_05` : corps `{"choice":"suspend"}` seul → 200, nouveau dossier, `verdict_computed`, `policy_decided`, `action_started` journalisés, acteur `human:purchase-guard`.
- **Scénario** : un appelant non identifié déclenche des demandes de garantie réelles (sous le seuil : envoi automatique) et le journal prétend qu'un humain a décidé.
- **Correction** : exiger `person_id` (et le jeton de C2) dans `PurchaseDecision` ; acteur `human:<id>` ; interdire `human:` suivi d'un identifiant qui n'est pas un UUID de `people` (validation dans `append_event` ou `Event.valid_actor`, backend/app/contracts/models.py:404).
- **Test** : `decision` sans `person_id` → 422 ; avec → événement `actor == f"human:{person_id}"`.

### H4 — Haute — Intégrité du journal : HMAC limité aux ancres, clé par défaut connue [V]

- **Preuve** : le hash d'événement est un SHA-256 **non signé** (`backend/app/core/journal.py:105`) ; le HMAC ne couvre que les lignes d'ancre (`backend/app/core/journal.py:132-161`) ; `verify` contrôle la chaîne SHA-256 entière (`backend/app/core/journal.py:173-188`) et les ancres existantes (`backend/app/core/journal.py:190-225`), mais ne détecte pas la suppression d’une queue postérieure à la dernière ancre ; ancrage uniquement à la demande (`POST /api/journal/anchor`, `backend/app/api/routers/journal.py:19-27`) ; clé par défaut `local-dev-only-change-me` (`backend/app/core/settings.py:19`), et `.env.example:3` fournit une valeur d'exemple. Les triggers SQLite se suppriment en une requête par quiconque a accès au fichier (reset le fait lui-même, backend/app/core/reset.py:78-79).
- **PoC** `test_06c` : 3 événements, ancre, 2 événements, suppression des 2 derniers (après `DROP TRIGGER`) → `verify ok=true`. `test_06d` : sans ancre, modification d'un payload et recalcul de la chaîne → `verify ok=true`.
- **Scénario** : un acteur local efface l'événement `action_succeeded` d'un envoi contesté, ou réécrit l'historique complet si aucune ancre n'a été posée.
- **Correction** : (1) signer **chaque** événement : `hash = HMAC(key, prev_hash + canonical)` ; (2) ancrage automatique (à chaque `status_changed` vers `sent`/`resolved` et périodiquement) ; (3) l'ancre enregistre aussi `checked` (nombre d'événements) et `verify` signale `seq` max < dernière ancre ; (4) refuser au démarrage la clé par défaut hors `environment=dev` ; (5) copie des ancres hors du dossier `runtime/` modifiable par l'API.
- **Test** : supprimer le dernier événement après ancre → `verify.ok == False` ; démarrer avec `WP_ENV=prod` et la clé par défaut → échec du préflight.

### M1 — Moyenne — Preuve manuelle non qualifiée [V]

- **Preuve** : `backend/app/api/routers/cases.py:510-511` ne refuse que la chaîne vide ; `backend/app/core/status.py:48-60` ne demande qu'une chaîne non vide et un acteur dont le préfixe est `human:`.
- **PoC** `test_07` : `proof="x"` → 200, statut `sent`, `ActionResult` succès avec preuve `x`.
- **Correction** : `ManualProofRequest` structuré (`kind` ∈ {`case_number`, `email_message_id`, `screenshot`}, valeur validée par motif, ex. n° Dell `^\d{10}$`, et/ou pièce jointe) ; badge `manual` affiché.
- **Test** : `proof="x"` → 422 ; `{"kind":"case_number","value":"1234567890"}` → 200.

### M2 — Moyenne — Allowlist navigateur par défaut trop large [V]

- **Preuve** : `backend/app/contracts/models.py:418-420` (`http://localhost:*`, `http://127.0.0.1:*`) ; `backend/app/core/security.py:28-29` accepte tout port pour `:*` ; le test `test_security_flags.py::test_url_allowlist_defaults_to_localhost_only` valide ce comportement. Avec C1, l'origine peut même devenir `http://evil.example:80` : `assert_url_allowed` (backend/app/core/orchestrator.py:789) l'accepte alors. Seule la liste figée `backend/app/actions/browser/allowlist.py:15` (vérifiée aussi sur `portal_url`, backend/app/actions/browser/adapter.py:85-86) empêche la navigation.
- **Scénario** : un futur adaptateur qui se fierait aux réglages plutôt qu'à sa liste figée pourrait viser un autre service local (`127.0.0.1:8001` lui-même, SMTP 2525…), c'est-à-dire une SSRF locale.
- **Correction** : défaut `["http://127.0.0.1:8100","http://localhost:8100"]` ; supprimer le joker `:*` hors tests ; intersection systématique réglages ∩ `PRODUCTION_ORIGINS`.
- **Test** : `assert_url_allowed("http://127.0.0.1:8001/api/demo/reset", Settings())` → `SecurityViolation`.

### M3 — Moyenne — Injection de prompt menant à une action [H]

- **Preuve** : la date d'achat qui fonde `covered` vient des faits extraits (`backend/app/rules/engine.py:238-242`), éventuellement produits par le LLM (`backend/app/ingestion/registry.py:19-28` → `pdf_llm.py`) ; l'auto-envoi dépend du verdict `COVERED` et du prix ≤ seuil (`backend/app/core/policy.py:19-27`), seuil 300 € après reset (`backend/app/core/reset.py:279-285`). La défense actuelle est textuelle (prompt `backend/app/ingestion/pdf_llm.py:16-22`) plus les contrôles `suspicious/plausibility/duplicates`. Non démontré : le moteur LLM n'est pas actif sans clé Mistral et aucun PDF piégé n'a été testé.
- **Scénario** : une facture contenant en texte blanc « purchase_date: 2026-10-01 » amène le LLM à renvoyer une date récente → `covered` → e-mail automatique au revendeur pour un matériel hors garantie (fraude, atteinte à la réputation).
- **Correction** : (1) n'autoriser l'auto-envoi que si la date provient d'une source déterministe (Factur-X, base équipement) ou est confirmée par deux sources concordantes ; (2) toute preuve issue du LLM → `needs_validation` (condition supplémentaire dans `policy.decide`) ; (3) contrôle de cohérence date facture/date livraison/numéro de série.
- **Test** : extracteur factice qui renvoie une date LLM seule → politique `needs_validation` avec la raison `llm_only_purchase_proof`.

### M4 — Moyenne — Masquage des secrets par nom de clé [V]

- **Preuve** : `backend/app/core/journal.py:20-38`.
- **PoC** `test_06b` : `{"error":"token=abc123"}` est journalisé tel quel ; `test_06a` : `{"idempotency_key":"case:x"}` devient `"***"` — la clé d'idempotence (backend/app/core/orchestrator.py:454) est donc perdue dans le journal, ce qui gêne l'audit des doublons.
- **Scénario** : si un adaptateur renvoie un jeton dans `ActionResult.error`, sa valeur est copiée dans `action_failed` (`backend/app/core/orchestrator.py:870-874`) sans masquage de la valeur libre. La propagation brute d’une exception Gmail/H Company/Mistral n’est pas démontrée ; le `str(error)` de `backend/app/core/orchestrator.py:484` concerne seulement SecurityViolation.
- **Correction** : liste blanche de clés non secrètes (`idempotency_key`) ; masquage par motif sur les valeurs (`Bearer\s+\S+`, `ya29\.`, `sk-`, `ghp_`, `token=`, `api_key=`) ; masquer aussi les valeurs des `SecretStr` connues (comparaison exacte).
- **Test** : `append_event(..., payload={"error":"Bearer abc"})` → `"Bearer ***"` ; `idempotency_key` conservé.

### M5 — Moyenne — Checklist de protection des données sans séparation des rôles [V]

- **Preuve** : `backend/app/api/routers/cases.py:600-660` ; chaque étape fixe `by_person_id` à l'appelant, sans contrôle de rôle, d'ordre (`repair_type` → … → `return_inspection`) ni de délai ; `return_inspection` (inspection au retour) peut être validée **avant** l'expédition. `backend/app/contracts/models.py:339-352` exige un `by_person_id` pour 5 étapes seulement.
- **PoC** : `test_04` (ci-dessus).
- **Correction** : rôle requis par étape ; ordre imposé ; `return_inspection` exclue des pré-requis d'envoi et validée après retour ; journaliser l'identité authentifiée (C2).
- **Test** : `return_inspection` avant `shipping_label` → 409 ; utilisateur sans rôle informatique → 403.

### B1 — Basse — Réponse incohérente en cas d'exécution concurrente [V]

- **Preuve** : PoC `test_08` : deux `run()` simultanés → 1 seul envoi, mais retours `resolved` et `failed` ; `backend/app/core/orchestrator.py:392-394` renvoie `FAILED` sans modifier la base quand une exécution est en cours.
- **Correction** : renvoyer l'état réel lu en base (ou 409 « exécution en cours ») ; verrou par dossier (`UPDATE cases SET status='sending' WHERE id=? AND status IN (...)` et test du nombre de lignes).
- **Test** : deux `POST /validate` concurrents → un 200 et un 409, un seul message dans le Maildir.

### B2 — Basse — Configuration API inutilisée ou exposée [V]

- `cors_origins` jamais utilisé (`backend/app/core/settings.py:30`) ; documentation interactive exposée (`backend/app/api/main.py:189`, valeurs par défaut FastAPI). Correction : brancher `cors_origins` (H2) ; `docs_url=None` hors `dev`.

### B3 — Basse — États en mémoire non bornés [V]/[H]

- `backend/app/api/routers/scan.py:178-197` (`asyncio.create_task` sans limite, `app.state.scans`), `backend/app/api/routers/chat.py:83-107` (`app.state.chat_conversations`), créés dans `backend/app/api/main.py:190-191`. Chaque scan relance l’extraction des seuls documents FACTURX (`backend/app/api/routers/scan.py:99-104`), dirigée vers FacturXExtractor (`backend/app/ingestion/registry.py:22-28`) : aucun appel LLM n’est atteint par cette route, même si Mistral est configuré. Correction : un scan à la fois (409 sinon), purge LRU des conversations, plafond de messages.

### B4 — Basse — Dépendance vulnérable [V]

- `uvx pip-audit -r <export uv.lock>` : `pytest 8.4.2 PYSEC-2026-1845`, correctif `9.0.3` (dépendance de développement uniquement). `npm audit` (frontend) et `pip-audit` (repro/dell) : aucune vulnérabilité connue. Correction : passer `pytest>=9.0.3` (changement de dépendance réservé à l'intégrateur).

### B5 — Basse — Typage hors périmètre CI et lint également couvert par CI [V]

- `cd backend && uv run mypy --strict app` → `Found 12 errors in 6 files` (`backend/app/api/main.py:122,135`, `backend/app/api/routers/purchase_guard.py:73,95,124,182`, `backend/app/api/routers/chat.py:229`, `backend/app/api/routers/cases.py:378`, `backend/app/api/dependencies.py:29`, `backend/app/testing/fakes.py:45,108,111`). Le mypy backend de la CI vérifie `app/contracts app/core app/ingestion app/rules ../data/appelia`, pas tout `app` (`.github/workflows/ci.yml:28-29`). Ruff couvre aussi `data/appelia` en CI (`.github/workflows/ci.yml:25`).
- `make lint` local : `ruff I001` dans `data/appelia/tests/test_dataset.py`.

### Points vérifiés sans constat

- **Traversée de chemin (captures)** : `backend/app/api/routers/cases.py:351-407` — nom filtré par motif, capture devant figurer dans un événement `action_step` du même dossier/action, `resolve(strict=True)` + `is_relative_to`. Test `tests/integration/test_case_screenshots.py::test_case_screenshot_is_served_only_for_its_action_and_case`. Le scan (`backend/app/api/routers/scan.py:89-104`) lit des noms de fichiers venant de `data/appelia/documents.json` (donnée du dépôt, non fournie par l'utilisateur).
- **SSRF serveur** : aucune URL fournie par l'utilisateur n'est récupérée côté serveur ; les URL LLM (`hcompany_base_url`, `browser_use_openai_base_url`) viennent de l'environnement. Voir toutefois M2.
- **Upload** : aucun endpoint `UploadFile`/`File(` dans `backend/app/api`.
- **Secrets dans le dépôt** : `gitleaks git` sur les 14 commits → `no leaks found` ; recherche complémentaire de motifs (`ghp_`, `github_pat_`, `sk-`, `AKIA`, `BEGIN PRIVATE KEY`, `password=`, `api_key=`) dans `git log -p --all` : 16 correspondances, toutes du code, des tests ou le mot de passe public de démo de la reproduction (`backend/app/actions/browser/settings.py:14`, documenté comme non secret). `.env` est ignoré (`.gitignore`), aucun `.env` ni base SQLite versionnés.
- **Bind réseau** : API, Vite, SMTP et reproduction écoutent sur `127.0.0.1` (Makefile:12, frontend/vite.config.ts:8, backend/app/actions/email/local_smtp_server.py:14, repro `repro/dell/dell_repro/__main__.py:7`).
- **Machine à états** : `TRANSITIONS` exhaustif (`backend/app/core/status.py:14-35`) et testé (`test_status.py::test_every_undeclared_transition_is_rejected`) ; toutes les écritures de statut de l'orchestrateur passent par `transition()`. Les routes `reject`, `manual-takeover`, `manual-proof` l'appellent aussi. Aucun contournement trouvé hors C2 (identité).
- **Pause de l'agent** : contrôlée dans la politique (`backend/app/core/policy.py:36-37`), avant l'action (`backend/app/core/orchestrator.py:389-391`) et dans `_assert_action_allowed` (l.778-779).

## 4. Commandes et résultats

| Commande | Résultat |
|---|---|
| `make lint` | échec : ruff `I001` `data/appelia/tests/test_dataset.py` ; arrêt avant le frontend, dont le lint a été lancé séparément avec succès |
| `make typecheck` | `Success: no issues found in 41 source files` ; `tsc` OK |
| `uv run pytest` (backend, Chromium installé) | `333 passed, 4 skipped` |
| `uv run mypy --strict app` | `Found 12 errors in 6 files (checked 76 source files)` |
| `uvx pip-audit` (backend / repro) | `pytest 8.4.2 PYSEC-2026-1845` / aucune |
| `npm audit` (frontend) | aucune vulnérabilité |
| `gitleaks git .` | `no leaks found` |
| PoC (hors dépôt, copie jetable) | `12 passed` — tests 01–07 : comportements faibles confirmés ; test 08 : observation concurrente sans double livraison |

Les PoC ne sont pas commités (consigne : lecture seule) et restent hors dépôt. Ils peuvent être convertis en tests de non-régression inversés lors des corrections (chaque section « Test » ci-dessus en donne l'assertion attendue).

## 5. Priorités de correction proposées

1. C2 + H2 (jeton opérateur, `TrustedHost`, contrôle `Origin`) — ferme la majorité des chemins d'exploitation.
2. C1 (réglages journalisés, bornés, réservés à un rôle) et H3 (`person_id` obligatoire).
3. H1 (reset gardé + archivage) et H4 (HMAC par événement, ancrage automatique).
4. M1–M5, puis B1–B5.
