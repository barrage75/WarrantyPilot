# Vérifications navigateur locales

Charger Node 22 et rendre `uv` disponible dans le PATH, puis :

```sh
npx playwright test e2e/smoke.spec.ts --repeat-each=3
npx playwright test e2e/screenshots.spec.ts
```

Playwright démarre une API sur 127.0.0.1:8001 avec `WP_ENV=dev`,
`WP_DATABASE_URL` et `WP_ANCHOR_FILE` dans un nouveau dossier temporaire
`frontend/.playwright-runtime/run-*` (ignoré). Le serveur API n'est **jamais**
réutilisé : arrêter d'abord toute API de développement qui occupe ce port.
Vite écoute sur 127.0.0.1:5173 et peut être réutilisé hors CI seulement.
Un seul worker évite les resets concurrents.

Contournement provisoire : après le reset par l'interface, `helpers.ts` utilise
`uv run --project ../backend python -c …` et SQLite **en lecture seule** pour
lire Camille et les équipements Jabra/Dell de cette base de test uniquement.
Il attend un endpoint personnes/équipements et ne lit jamais la base utilisateur.
Les appels fake-case restent limités aux tests, jamais au chat.

Les captures 1440×900 FR/EN utilisent cette même API isolée ; les actions,
statuts et événements sont réels mais les dossiers et données sont fictifs.
Les écrans sans endpoint restent explicitement SIMULÉS. Les images sont
dans `frontend/screenshots/`, ignoré par Git.

`npm test` exclut `e2e/**` dans la configuration Vitest ; aucun test navigateur
n'est ajouté aux vérifications CI lint/typecheck/build.
