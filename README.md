# WarrantyPilot

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
