# Contribuer

## Branches et commits

Créer `devin/<timestamp>-lot-<nom>` depuis `integration`, garder les branches
à jour chaque jour et ouvrir une PR vers `integration`. Viser au moins une PR
par lot et par jour. Utiliser Conventional Commits, avec un sujet français
concis, par exemple `feat: ajoute la vérification du journal`.

Les contrats, dépendances, migrations et fichiers de configuration sont des
fichiers partagés : seul l'intégrateur les modifie. Les propriétaires de lots
et leurs chemins sont listés dans `OWNERSHIP.md`.

## Vérifications

```sh
make setup
make lint typecheck test
make frontend-build
```

## Brancher une implémentation aux tests de contrat

Les assertions réutilisables sont dans `backend/tests/contract/helpers.py`.
Un lot fournit son implémentation d'un Protocol dans les paramètres de test
correspondants : `assert_action_adapter_contract`,
`assert_extractor_contract`, `assert_rules_engine_contract` ou
`assert_follow_up_contract`. Un `ActionAdapter` ne lève pas pour un échec
métier et fournit une preuve non vide en cas de succès. Un `DocumentExtractor`
rattache chaque fait à une provenance; un `RulesEngine` renvoie un verdict avec
une trace de contrôles. Ajouter chaque implémentation aux tests sans modifier
les modèles partagés.
