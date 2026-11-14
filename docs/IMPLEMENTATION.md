# État d'implémentation

## L0 — Socle

- Contrats Pydantic, catalogue d'événements et Protocols : socle partagé.
- Noyau : persistance SQLAlchemy/Alembic, transitions, journal vérifiable,
  politique, garde-fous de sécurité, reprise et préflight.
- API FastAPI et interface React minimale avec affichage du journal, du préflight,
  des dossiers et de la pause agent.
- Fakes disponibles pour extraction, règles, action et suivi.

La livraison L0 ne contient aucun connecteur réel, aucune donnée Appelia réelle
et aucune intégration Gmail, H Company ou fournisseur.

## Lots à réaliser

| Lot | État |
|---|---|
| L1 — jeu Appelia | À faire |
| L2 — lecture de documents | À faire |
| L3 — moteur de règles | À faire |
| L4a — reproduction Dell | À faire |
| L4b — pilotage navigateur | À faire |
| L5 — interface de démonstration | À faire |
| L6 — e-mail Gmail | À faire |
| L7 — garde-fou achat et suivi | À faire |
| L8 — bonus | À faire |
