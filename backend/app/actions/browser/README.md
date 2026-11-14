# Lot L4b — adaptateur navigateur (`browser_portal`)

`BrowserPortalAdapter` implémente `ActionAdapter` pour `Channel.BROWSER_PORTAL` et dépose la
demande de réparation sur la **reproduction locale Dell** (`repro/dell`). Badge : `reproduction`.

- Liste blanche codée en dur : `127.0.0.1:8100` et `localhost:8100` uniquement (origines de test
  loopback acceptées seulement si `test_mode`). Toute navigation hors liste (redirection, clic,
  popup) arrête l'action : `failure`, `error="url_not_allowed"`. Chromium est en plus lancé avec
  `--host-resolver-rules` qui empêche de résoudre tout nom autre que le loopback.
- Moteurs (`BrowserDriver`) : `ScriptedPlaywrightDriver` (sélecteurs, CI), `HCompanyDriver`
  (boucle Holo via l'API Models H Company), `BrowserUseDriver` (Browser Use 1.0 via CDP).
  Réglage `WP_BROWSER_ENGINE` = `scripted|hcompany|browser_use` ; repli scripté si
  `WP_BROWSER_FALLBACK_TO_SCRIPTED=true` (défaut) après un échec propre au moteur IA, journalisé.
- Le numéro de dossier est toujours lu sur la page de confirmation, jamais sur la réponse d'un agent.
- Idempotence : registre SQLite local (rejoue la preuve) + `requestToken` dérivé de `case_id`
  (la reproduction déduplique une resoumission après timeout).
- Données : `payload["portal_claim"]` (voir `claim.py`) ; identifiants = compte de démo de la
  reproduction (`*@reproduction.local`), refus sinon.
- Preuve JSON : `case_number`, `url`, `screenshot_path` (PNG), `captured_at`, `engine`.
- Progression : `on_step(text, screenshot_path)` (sync ou async).

Playwright n'est pas une dépendance du backend : sans lui, l'action échoue en
`browser_unavailable` et les tests d'intégration sont sautés. Localement :
`uv run --project backend --with playwright==1.65.1 pytest backend/tests/unit/actions/browser`.
