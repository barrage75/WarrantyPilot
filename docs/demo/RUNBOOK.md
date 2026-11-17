# Runbook de démo

Tout tourne en local sur `127.0.0.1`. L'API exige une session (`/api/auth/login`, SEC1) et refuse un `Host` ou une `Origin` étrangers (constaté : `Host: evil.example` → 400, `Origin: http://evil.example` → 403, sans session → 401). Données fictives uniquement. Ne jamais afficher le mot de passe de démo ni le jeton GitHub.

Repères : API `http://127.0.0.1:8001/api` (`WP_API`), front `http://127.0.0.1:5173`, SMTP `127.0.0.1:2525`, portail Dell reproduit `http://127.0.0.1:8100`. Samy Benzeguir = `admin` (`WP_ADMIN_ID` du `Makefile`), Paul Martin et Claire Dubois = `operator`. En démo locale, n'importe quel mot de passe fonctionne.

## J-1

1. `git fetch && git checkout integration && git pull`.
2. `make setup` (dépendances, migrations, `make seed`, OpenAPI). Sur une machine neuve, si `sqlite3.OperationalError: unable to open database file` : `mkdir -p runtime/anchors` puis relancer.
3. Reproduction Dell, une fois : `cd repro/dell && uv sync --locked && uv run playwright install --with-deps chromium && uv run pytest -v && cd ../..`.
4. Vérifications, **tous les services de démo arrêtés** (port 8100 libre, voir § Port 8100) : `make lint typecheck test`, `make p0`, `make frontend-build`.
   - `make p0` : lance sa propre reproduction Dell sur 8100 (runtime temporaire), attend `GET /__test__/cases`, puis `pytest -m p0 backend/tests/p0/test_p0_gate.py`. Mesuré : `10 passed` en 23 s.
5. Répéter le script deux fois, chronométrer (durées de référence dans `SCRIPT_3MIN.md`).
6. Enregistrer la **vidéo de secours** (3 min, 1440×900) sur la machine **et** une clé USB. Copier les captures Dell (`runtime/browser/screenshots/<action_id>/*.png`) hors de `runtime/`.
7. Désactiver mises à jour, notifications, veille.

## H-30

Trois terminaux à la racine du dépôt.

| Terminal | Commande | Attendu |
|---|---|---|
| 1 | `cd repro/dell && uv run python -m dell_repro` | portail fictif sur `127.0.0.1:8100` (`curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8100/` → `302`) |
| 2 | `WP_FOLLOWUP_INTERVAL_S=5 make dev` | SMTP local `2525` + API `8001` + front `5173` (`make dev` lance aussi le SMTP ; ne pas lancer `make smtp` en plus). Le suivi tourne toutes les 5 s ; sans la variable, il est désactivé (`0`) et il faut appeler `/followup/tick` |
| 3 | commandes ci-dessous | — |

```sh
make reset       # connexion admin (cookie runtime/.make-session) puis {"confirm":"RESET"} ; attendu {"status":"reset"}
make preflight   # attendu "ok": true
curl -s -X POST http://127.0.0.1:8100/__test__/reset   # vide les dossiers du portail reproduit ; attendu {"reset":true}
ls runtime/journal-archive/ | tail -1                  # le journal précédent est archivé (events.jsonl, anchors.jsonl)
```

**Répétition à blanc obligatoire juste avant de passer devant le jury** : jouer le parcours complet (dont Dell : Signalement, checklist, « Valider », avancer le portail), puis refaire `make reset` et le reset du portail ci-dessus.

`make seed` recrée la base sans passer par l'API (`python -m app.core.reset`) : à utiliser **API arrêtée**, par exemple si `make reset` échoue faute de session. Reset par l'interface : connecté en Samy, page **Démo** → **« Réinitialiser la démo »** → **« Confirmer la remise à zéro »** ; message « Démo réinitialisée. Le journal précédent a été archivé… ». Un opérateur (Paul) ne peut pas faire le reset.

## Dossier Dell depuis l'écran Signalement

Connecté en Samy : menu **« Signalement »** → `Le PC 7XK4L93 de Clément ne démarre plus` → **« Envoyer »** → **« Ouvrir le dossier créé #… »**. Le Service Tag exact identifie l'équipement quel que soit son propriétaire (#40). Vérifié le 14/11/2026 : dossier en 1,0 s, `awaiting_validation`, verdict « Couvert », checklist de 7 étapes, badge **SIMULÉ** puis **REPRODUCTION** après l'action portail.

## Avancer le portail local (simule la clôture côté Dell)

```sh
NUM=$(curl -s http://127.0.0.1:8100/__test__/cases | python3 -c 'import sys,json;d=json.load(sys.stdin);d=d if isinstance(d,list) else d.get("cases",d);print(d[-1]["number"])')
for i in 1 2 3; do curl -s -X POST http://127.0.0.1:8100/__test__/advance/$NUM; echo; done   # in_progress, part_shipped, closed
# si WP_FOLLOWUP_INTERVAL_S n'est pas réglé, ou pour ne pas attendre :
curl -s -b runtime/.make-session -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8001/api/followup/tick
```

Attendu : `{"cases_checked":1,"followups_logged":1,"status_changes":1,…}` puis dossier `resolved`. Un 4ᵉ `advance` renvoie 409 (déjà clos). Le suivi ne résout jamais sans statut `closed` relevé (`backend/app/followup/README.md`).

## Résolution humaine (alternative ou plan B)

Interface : détail du dossier en **Suivi** → **« Note de résolution »** → **« Marquer comme résolu »**. API :

```sh
curl -s -b runtime/.make-session -X POST -H 'Content-Type: application/json' \
  -d '{"note":"Remplacement reçu (démo fictive)."}' http://127.0.0.1:8001/api/cases/$CASE/resolve
```

Note obligatoire (non vide) ; refus `409` si le dossier n'est pas `sent` ou `tracked`. Un opérateur peut résoudre (vérifié avec Paul).

## Port 8100 déjà occupé

`make p0` refuse de tourner si le port 8100 est occupé (`python -m app.core.port_check`, première commande de la cible). Constaté le 14/11/2026, reproduction de démo lancée :

```text
Port 8100 on 127.0.0.1 is already in use; stop the existing Dell reproduction before running make p0.
make: *** [Makefile:28: p0] Error 1
```

Libérer le port, puis relancer :

```sh
ss -ltnp 'sport = :8100'          # qui écoute ?
# si c'est la repro de démo : Ctrl+C dans le terminal 1 ; sinon :
fuser -k 8100/tcp                 # ou kill <pid> lu ci-dessus
ss -ltnp 'sport = :8100'          # doit être vide
make p0
```

Ne jamais lancer `make p0` (ni `make test`) pendant la démo. Après, relancer le terminal 1. Le backend vise `http://127.0.0.1:8100` par défaut (`DEFAULT_PORTAL_URL`, `backend/app/actions/browser/settings.py`) et `make p0` code ce port en dur : il faut libérer 8100.

## Contrôle avant démo (H-5)

- [ ] `make preflight` : `"ok": true` ; en-tête « Journal · Intègre » ; `curl -s -b runtime/.make-session http://127.0.0.1:8001/api/journal/verify` → `"ok": true`.
- [ ] `ss -ltnp | grep -E ':(8001|5173|2525|8100) '` : quatre lignes, toutes sur `127.0.0.1`.
- [ ] Navigateur sur `http://127.0.0.1:5173/`, écran « Connexion opérateur », déconnecté, zoom 100 %.
- [ ] **Garde-fou achat** : Jabra Evolve2 65, 120 €, « Recommandation ». Aucun dossier dans **Dossiers**.
- [ ] Terminal 3 : commande « Avancer le portail » prête.
- [ ] Répétition à blanc faite, puis `make reset` et reset du portail.
- [ ] Wi-Fi coupé, vidéo de secours en pause.

## Réseau coupé

Aucun réseau externe nécessaire : SMTP local, portail Dell local, moteur navigateur `scripted` (`backend/app/actions/browser/settings.py`), règles et Factur-X locaux, suivi limité aux URL loopback (`backend/app/followup/README.md`). Ne pas activer H Company / Browser Use ni un LLM externe. Couper le Wi-Fi avant la démo.

## Le navigateur plante

1. Rouvrir Chrome sur `http://127.0.0.1:5173/`, se reconnecter (la session est un cookie ; l'état est en base SQLite).
2. Reprendre à l'étape en cours (`/cases/<id>`).
3. Action Dell bloquée : `make preflight` (contrôle `no_stuck_sending`) ; si rouge, **« Prendre la main »** sur le dossier.

## Plan B Dell (boutons inutilisables)

`CASE` = identifiant du dossier, lu dans l'URL `/cases/<id>` après `make login` :

```sh
CASE=<id lu dans l'URL>
for s in repair_type backup_verified disk_encryption disk_handling accounts_and_mdm shipping_label return_inspection; do
  curl -s -o /dev/null -w '%{http_code} ' -b runtime/.make-session -X POST -H 'Content-Type: application/json' -d '{}' \
    http://127.0.0.1:8001/api/cases/$CASE/checklist/$s
done; echo
curl -s -b runtime/.make-session -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8001/api/cases/$CASE/validate
```

Vérifié le 14/11/2026 : sept `200`, puis `tracked` en 1,7 s. Ne pas passer un `person_id` différent de la session : `403`.

## Bascule vidéo de secours

Critère : deux échecs de suite ou plus de 20 s perdues. Dire : « Pour tenir le temps, voici l'enregistrement de ce même parcours, fait hier sur cette machine. » Ne jamais présenter la vidéo comme du direct.

## Après la démo

`Ctrl+C` dans les terminaux 1 et 2. `make reset` (ou `make seed`, API arrêtée) si la machine est réutilisée.
