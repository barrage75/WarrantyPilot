# WarrantyPilot

## Tester la démo sur mon PC

Tout fonctionne **sur votre ordinateur**, avec des données fictives. Aucun dossier
n'est envoyé à Dell : le portail Dell est une **reproduction locale**.

### Sur Windows (pas besoin de Make ni de Bash)

1. Installez [Git pour Windows](https://git-scm.com/downloads/win), puis récupérez
   le dépôt, ou plus simplement [téléchargez le ZIP de la branche integration](https://github.com/barrage75/gare/archive/refs/heads/integration.zip)
   et **extrayez-le** dans un dossier (pas dans le ZIP).
2. Installez **uv**, qui gère Python pour vous. Ouvrez PowerShell et collez la
   commande officielle de [docs.astral.sh](https://docs.astral.sh/uv/getting-started/installation/) :

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. Installez **Node.js LTS**, npm inclus, avec l'installateur de
   [nodejs.org](https://nodejs.org/). Fermez et rouvrez votre terminal après installation.
4. Dans le dossier extrait, **double-cliquez sur `demo.cmd`**, ou ouvrez un terminal
   dans ce dossier et lancez :

   ```powershell
   .\demo.cmd
   ```

La première fois, les dépendances, Python 3.12 et Chromium sont téléchargés : cela
peut prendre plusieurs minutes. La base locale est initialisée. Un navigateur
s'ouvre sur **http://127.0.0.1:5173** quand tout est prêt. Choisissez **Karim Benali** ;
le mot de passe de démonstration par défaut, lu dans les réglages du backend, est
indiqué dans la console. Si vous avez personnalisé `WP_DEMO_PASSWORD` dans `.env`,
utilisez votre propre valeur. Ne projetez pas cette console devant le jury.

Gardez la fenêtre du lanceur ouverte. **Ctrl+C** arrête les quatre services ;
vous pouvez ensuite fermer la fenêtre. Sous Windows, la fermeture de cette
fenêtre arrête également ses processus enfants. Les relances conservent les
données ; pour repartir à zéro (base WarrantyPilot **et** portail Dell) :

```powershell
.\demo.cmd --reset
```

Pour la démonstration de clôture Dell, ouvrez un **deuxième terminal** dans le même
dossier, après avoir créé et validé le dossier Dell dans l'interface :

```powershell
.\demo.cmd advance
```

Cette commande avance le dernier dossier du portail local jusqu'à « clôturé »,
puis déclenche le suivi authentifié de WarrantyPilot. Voir le parcours complet
dans [le script de démonstration de 3 minutes](docs/demo/SCRIPT_3MIN.md).

### macOS / Linux et options

Installez [uv](https://docs.astral.sh/uv/) et Node.js LTS, puis lancez
`sh demo.sh` (ou `sh demo.sh advance`). La commande directe sur tous les systèmes :
`uv run --project backend python scripts/demo.py`.

- `--no-browser` : ne pas ouvrir automatiquement le navigateur.
- `--skip-setup` : ignorer installations et migrations, uniquement après une
  première préparation réussie. `--reset` reste actif avec cette option.
- Le lanceur utilise le moteur navigateur **scripted**, le SMTP local et le
  runtime Dell persistant `repro/dell/runtime`, jamais un dossier temporaire.
  Le suivi s'exécute toutes les 5 secondes. Les identifiants Gmail sont refusés.

**En cas de souci :**
- Port occupé (8001, 5173, 2525 ou 8100) : arrêtez l'ancienne démo ou le programme
  indiqué ; ne lancez pas `make dev` en parallèle.
- Antivirus / pare-feu : autorisez Python et Node pour cette démo locale si
  demandé, sans désactiver votre protection ni ouvrir de port sur Internet.
- Premier lancement long : laissez les téléchargements se terminer ; consultez
  `runtime/logs/` si une erreur apparaît (la fenêtre Windows reste ouverte).
- Outil introuvable : rouvrez le terminal après installation ; pour Python,
  lancez `uv python install 3.12`. Sur Linux, si Chromium signale une bibliothèque
  système absente, suivez le diagnostic Playwright (`uv run --project backend playwright install-deps chromium`).

Agent local qui transforme une panne d'équipement en demande de garantie
documentée, validée par un humain, envoyée et suivie. Le dépôt contient le
socle L0; les connecteurs et les données des lots suivants ne sont pas encore
présents.

## Installer

Prérequis : Python 3.12 géré par [uv](https://docs.astral.sh/uv/), et Node/npm
(nvm est utilisé sur la VM). Installer uv depuis sa documentation officielle;
pour installer Node sur une machine qui utilise déjà nvm :

```sh
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm install --lts
cp .env.example .env
uv python install 3.12
make setup
```

`WP_JOURNAL_ANCHOR_KEY` dans `.env` doit être remplacée avant toute utilisation
qui dépasse les données fictives locales. Ne jamais committer `.env`.

## Lancer

```sh
make dev
```

L'API écoute sur `http://127.0.0.1:8001/api`; l'interface Vite est sur
`http://localhost:5173`. Swagger : `/docs`. L'API L0 n'a pas d'authentification
et doit rester liée à la machine locale.

## Commandes

```sh
make test
make lint
make typecheck
make frontend-build
make openapi
make reset       # API lancée
make preflight   # API lancée
```

Architecture et frontières de confiance : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Voir aussi [l'API](docs/API_DOCUMENTATION.md), la
[sécurité](docs/SECURITY.md), les [contributions](docs/CONTRIBUTING.md) et la
[propriété des dossiers](OWNERSHIP.md), les
[décisions](DECISIONS.md) et le [changelog](CHANGELOG.md).
