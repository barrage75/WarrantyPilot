# Runbook de démo

Tout tourne en local sur `127.0.0.1`. L'API locale n'a pas d'authentification (`docs/SECURITY.md`) : jamais sur un réseau partagé, jamais exposée. Données fictives uniquement.

## J-1

1. Mettre à jour : `git fetch && git checkout integration && git pull`.
2. Installer : `make setup` (dépendances, migrations, OpenAPI). Si l'erreur `sqlite3.OperationalError: unable to open database file` apparaît : `mkdir -p runtime/anchors` puis relancer `make setup` (observé sur une machine neuve).
3. Reproduction Dell, une fois :
   ```sh
   cd repro/dell
   uv sync --locked
   uv run playwright install --with-deps chromium
   uv run pytest -v
   cd ../..
   ```
4. Vérifications du dépôt : `make lint typecheck test` et `make frontend-build`.
5. **`make p0` n'existe pas** dans le `Makefile` (cibles : `setup dev smtp test lint typecheck openapi reset preflight frontend-build`). Équivalent P0 : `make test` + les tests E2E du parcours principal (`frontend/e2e/README.md`, `frontend/e2e/smoke.spec.ts`), qui demandent d'arrêter `make dev` car ils lancent leur propre API isolée.
6. Répéter le script complet deux fois, chronométrer.
7. Enregistrer la **vidéo de secours** (3 min, script complet, écran 1440×900) et la copier sur la machine de démo **et** une clé USB. Copier aussi un jeu de captures Dell (`runtime/browser/screenshots/<action_id>/*.png`) dans un dossier hors `runtime/` (le reset efface `runtime/`).
8. Désactiver mises à jour, notifications, veille.

## H-30

Quatre terminaux, depuis la racine du dépôt.

| Terminal | Commande | Attendu |
|---|---|---|
| 1 | `make smtp` | serveur SMTP local sur `127.0.0.1:2525`, Maildir `runtime/mail` |
| 2 | `cd repro/dell && uv run python -m dell_repro` | portail fictif sur `http://127.0.0.1:8100` |
| 3 | `make dev` | API `127.0.0.1:8001`, front `127.0.0.1:5173` |
| 4 | commandes ci-dessous | — |

Dans le terminal 4 :

```sh
make reset          # attendu : {"status":"reset"}
make preflight      # attendu : "ok": true, 5 contrôles verts
curl -s http://127.0.0.1:8001/api/settings | grep auto_send_threshold_eur   # attendu : "300.00"
# Dossier Dell (Dell Latitude 7440, Service Tag fictif 7XK4L93)
curl -s -X POST http://127.0.0.1:8001/api/dev/fake-case \
  -H 'Content-Type: application/json' \
  -d '{"equipment_id":"11ab0f7a-5eec-5a06-a08e-d35346207174"}'
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8100/   # attendu : 200
```

Le reset peut aussi se faire dans l'interface : page **Démo** → **« Réinitialiser la démo »** → **« Confirmer la remise à zéro »**. Il efface le dossier Dell : relancer la commande `fake-case` après.

## Contrôle avant démo (H-5)

- [ ] Page **Démo** : préflight tout vert ; en-tête « Journal · Intègre ».
- [ ] Page **Décisions** : une seule carte, Dell Latitude 7440 · 7XK4L93, « Préparé ».
- [ ] Page **Garde-fou achat** : casque Jabra Evolve2 65, 120 €, état recommandation.
- [ ] Aucun dossier Jabra existant (sinon `make reset` + `fake-case`).
- [ ] Les 5 onglets du script ouverts, zoom 100 %, vidéo de secours en pause.
- [ ] Wi-Fi coupé (rien n'en dépend, voir ci-dessous).

## Réseau coupé

Le parcours n'a besoin d'aucun réseau externe : SMTP local, portail Dell local, moteur de navigateur `scripted` par défaut (`backend/app/actions/browser/settings.py`), règles et Factur-X locaux. Ne pas activer les moteurs H Company / Browser Use ni un LLM externe pour la démo. Recommandation : couper le Wi-Fi avant de monter sur scène.

## Le navigateur plante

1. Rouvrir Chrome, rouvrir les onglets (adresses dans `SCRIPT_3MIN.md`). L'état est en base SQLite : rien n'est perdu.
2. Re-sélectionner l'opérateur (Paul ou Karim) dans **« Vous agissez en tant que »**.
3. Si une action Dell est restée bloquée : `make preflight` (contrôle `no_stuck_sending`). Si rouge : bouton **« Prendre la main »** sur le dossier, ou `make reset` + `fake-case` et reprendre à l'étape en cours.

## Plan B Dell (boutons inutilisables)

```sh
CASE=$(curl -s http://127.0.0.1:8001/api/cases | python3 -c "import json,sys;print([c['id'] for c in json.load(sys.stdin) if c['verdict'] and c['verdict']['channel']=='browser_portal'][0])")
K=97225c38-d686-5d99-a6cf-53e18aa92e8d   # Karim Benali (fictif)
for s in repair_type backup_verified disk_encryption disk_handling accounts_and_mdm shipping_label return_inspection; do
  curl -s -X POST http://127.0.0.1:8001/api/cases/$CASE/checklist/$s -H 'Content-Type: application/json' -d "{\"person_id\":\"$K\"}" >/dev/null
done
curl -s -X POST http://127.0.0.1:8001/api/cases/$CASE/validate -H 'Content-Type: application/json' -d "{\"person_id\":\"$K\"}"
```

Commandes vérifiées le 14/11/2026 : statut final `resolved`, numéro de dossier et 4 captures.

## Bascule vidéo de secours

Critère : deux échecs de suite, ou plus de 20 s perdues. Dire : « Pour respecter le temps, je vous montre l'enregistrement de ce même parcours, fait hier sur cette machine. » Lancer la vidéo au segment en cours, commenter avec les mêmes phrases. Ne jamais présenter la vidéo comme du direct.

## Après la démo

`Ctrl+C` dans les 4 terminaux. `make reset` si la machine est réutilisée.
