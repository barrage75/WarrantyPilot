# Revue du backend WarrantyPilot

Périmètre : `backend/`, `data/appelia/`, `repro/dell/`, `Makefile`, `.github/workflows/`.
Hors périmètre : `frontend/`, `docs/demo/`.

Aucune forme du contrat HTTP (`backend/app/contracts/openapi.json`) n'a changé : `make openapi` ne produit aucun diff.

État après corrections : `make lint typecheck test` vert (523 tests passés, 4 ignorés), `make p0` 10/10.

## Critique

Aucun défaut critique trouvé : pas de contournement d'authentification, pas d'accès possible à un vrai fabricant. Les listes d'autorisation (e-mail et URL, `app/core/security.py`) sont vérifiées avant chaque action, et la chaîne HMAC du journal est saine.

## Important

| # | Constat | Statut |
|---|---------|--------|
| I1 | `routers/scan.py` : le résultat de `asyncio.create_task(_run_scan(...))` n'était conservé nulle part. La boucle asyncio ne garde qu'une référence faible, donc le ramasse-miettes peut détruire un scan en cours. | **Corrigé** : `scan.py:199` et `main.py:316` (`app.state.scan_tasks`, retrait automatique à la fin). Test : `test_scan_task_is_retained_until_done` |
| I2 | Toutes les transactions SQLite commencent par `BEGIN IMMEDIATE`, y compris les simples lectures (`core/db.py`). Le scan lisait `purchase_requests` en SQL synchrone dans la boucle asyncio. Si un autre fil tenait déjà le verrou d'écriture, tout le serveur pouvait rester bloqué jusqu'à 30 s. | **Corrigé** : `scan.py:151`, la lecture passe par `asyncio.to_thread`. Tests : `test_scan_purchase_read_runs_off_loop`, `test_scan_database_error_is_reported` |
| I3 | Flux SSE `GET /cases/{id}/stream` : la requête lancée toutes les 0,5 s tournait dans la boucle asyncio et prenait donc le verrou d'écriture, une fois par client connecté. | **Corrigé** : `cases.py:308` (`asyncio.to_thread`), le flux renvoyé reste identique. Tests : `test_sse_poll_runs_off_loop_without_changing_events`, `test_sse_database_error_propagates` |
| I4 | Journal : la ligne d'ancrage était ajoutée à `anchors.jsonl` **avant** le commit SQL (dans `auto_anchor` comme dans `POST /journal/anchor`). En cas d'échec du commit (base occupée, rollback), il restait une ligne orpheline, et `verify()` répondait ensuite `anchors_ok=false` pour toujours. | **Corrigé** : `core/journal.py:196`, la ligne n'est écrite qu'après un commit réussi (événement `after_commit` lié à la transaction d'origine). Tests : `test_anchor_rollback_does_not_write_file`, `test_anchor_commit_writes_file` |
| I5 | Plusieurs routes `async def` font du SQL synchrone dans la boucle avant ou après `await orchestrator.run(...)` : `cases.validate_case`, `cases.complete_checklist_step`, `chat.send_message` (`report_failure`), `purchase_guard.decide` et `resolve_case`, `demo.create_fake_case`, `intake.poll` et `upload`. C'est le même risque de blocage que I2 et I3 (verrou d'écriture attendu dans la boucle). | **Reporté** : il faut restructurer chaque route (passer la partie SQL dans `to_thread`, ou en faire des routes synchrones). C'est trop large pour cette PR, alors qu'un autre lot modifie les routeurs en parallèle. Piste : un utilitaire `run_db(fn)` commun. |
| I6 | Segfault serveur observé une fois en e2e pendant le scan. Après relecture, tous les appels pdfplumber et pypdf (scan, intake, `reset_demo`) passent par l'unique fil `PDF_EXECUTOR` (`ingestion/pdf_executor.py`). Le seul autre chemin, `IntakeService._extract_content`, est lui aussi appelé via `run_pdf_task`. | **Non reproduit** : la cause la plus probable (parsing PDF concurrent) est déjà corrigée par #39. À surveiller ; si le problème revient, activer `faulthandler` côté uvicorn. |
| I7 | `POST /agent/resume` n'exige qu'une session `operator`. N'importe quel opérateur peut donc relancer l'agent après une pause d'urgence décidée par un administrateur. | **Reporté** : passer à `require_admin` change le comportement visible (403 pour un opérateur). C'est une décision produit et frontend. |

## Mineur

| # | Constat | Statut |
|---|---------|--------|
| M1 | `schedule_auto_anchor` : si `ThreadPoolExecutor.submit` levait une exception (exécuteur arrêté), le verrou `_anchor_pending` n'était jamais libéré, et l'ancrage automatique restait désactivé jusqu'au redémarrage. Les exceptions autres que `OperationalError` disparaissaient aussi sans trace dans un `Future`. | **Corrigé** : `api/security.py:66,78`. Tests : `test_submit_failure_releases_pending_and_logs`, `test_worker_releases_pending_and_logs_errors`, `test_in_memory_and_pending_work_are_not_submitted` |
| M2 | Les sessions expirées de `auth_sessions` n'étaient jamais supprimées : la table grossissait sans fin. | **Corrigé** : `core/auth.py:71`, purge à l'ouverture d'une session, dans la même transaction. Tests : `test_open_session_purges_expired_rows_transactionally`, `test_open_session_with_no_expired_rows` |
| M3 | `make test` n'exécutait pas `data/appelia/tests`, contrairement à la CI. | **Corrigé** : `Makefile:25` |
| M4 | Le typage strict ne couvrait que `contracts`, `core`, `ingestion`, `rules` et `appelia`. Il restait 10 erreurs `mypy --strict` dans `app/api` et `app/testing`. | **Corrigé** : erreurs supprimées (annotations seulement). `app/actions`, `app/followup`, `app/intake` et `app/testing` sont ajoutés à la vérification de types dans `Makefile` et `ci.yml`. `app/api` passe en strict mais **n'est pas ajouté** à la CI, pour ne pas bloquer le lot qui ajoute les routeurs overview/reports/notifications. À ajouter une fois ce lot fusionné. |
| M5 | Sans `playwright install chromium`, 13 tests navigateur échouaient au lieu d'être ignorés. | **Corrigé** : `tests/unit/actions/browser/conftest.py:58`, ignorés avec un message explicite. La CI installe Chromium, donc ces tests y tournent toujours. |
| M6 | Avertissement pytest-asyncio sur `asyncio_default_fixture_loop_scope`. | **Corrigé** : `backend/pyproject.toml` |
| M7 | Une requête modifiante sans en-tête `Origin` ni `Referer` passe le contrôle d'origine (`api/security.py`). Le risque est faible, car le cookie est `SameSite=Strict` et `HttpOnly`, et le jeton Bearer n'est pas envoyé automatiquement par le navigateur. | **Reporté** : refuser ces requêtes casserait `curl` et `make reset`. On pourrait exiger `Sec-Fetch-Site` quand il est présent. |
| M8 | `POST /auth/login` n'a aucune limite de tentatives, avec un mot de passe de démo partagé. | **Reporté** : acceptable en démo locale, à prévoir avant toute exposition réseau. |
| M9 | `app.state.scans` et `app.state.chat_conversations` grossissent sans limite. Une conversation n'est pas rattachée à la session qui l'a créée : tout opérateur connecté peut la lire s'il connaît son identifiant. | **Reporté** : demande une politique d'expiration ou un rattachement à la session ; impact faible en démo. |
| M10 | `scan.py` modifie `sys.path` à l'exécution pour importer `data.appelia`. | **Reporté** : fonctionne, mais l'emballage (`packaging`) serait plus propre. |
| M11 | Tests les plus lents : les tests navigateur sur la reproduction Dell (`test_browser_repro_integration.py`, environ 5,8 s pour le plus long, environ 25 s au total). | **Laissés tels quels** : ils mesurent de vrais délais d'attente (timeouts) ; la suite complète prend environ 55 s. |
