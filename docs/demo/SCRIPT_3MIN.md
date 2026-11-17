# Script de démo — 3 minutes

Données 100 % fictives (Appelia, domaines `.example`, Service Tag fictif `7XK4L93`, voir `data/appelia/README.md`). Aucun envoi à un fabricant, aucun service public : tout écoute sur `127.0.0.1`.

Rejoué le 14/11/2026 sur `integration` (après #35, #37, #38, #39), par l'API (script complet : 7,9 s) puis par l'interface (Playwright, Chromium 1440×900). Durées de l'interface, sans pauses de parole :

| Étape | Durée |
|---|---|
| Connexion Paul | 0,2 s |
| Scan 65 documents | 2,2 s |
| Chat Jabra → dossier créé, e-mail parti | 1,0 s |
| Garde-fou : suspendre + annuler | 2,6 s |
| Résolution humaine Jabra + économie réalisée | 3,5 s |
| Scan final | 1,8 s |

Partie Dell rejouée seule dans l'interface après #40 (session Samy, depuis l'écran Signalement) :

| Étape Dell | Durée |
|---|---|
| « Envoyer » la phrase → lien « Ouvrir le dossier créé » | 1,0 s |
| Page du dossier affichée | 0,3 s |
| 7 × « Compléter » + « Valider » | 2,6 s |
| « Valider » → statut `tracked` (portail local rempli) | 1,7 s |
| Portail avancé à `closed` → `resolved` (suivi périodique 5 s) | 0,5 s |
| **Total Dell, de « Envoyer » à « Résolu »** | **7,7 s** |

**Consigne** : faire une répétition à blanc complète juste avant de passer devant le jury, puis `make reset` et le reset du portail (`RUNBOOK.md` § H-30).

Le reste des 3 minutes, c'est la parole. Les temps du tableau « Minutage » sont des cibles de répétition, pas des mesures.

## Pré-requis (fait à H-30, voir `RUNBOOK.md`)

- Services lancés : SMTP local (`127.0.0.1:2525`, Maildir `runtime/mail`), reproduction Dell (`127.0.0.1:8100`), `WP_FOLLOWUP_INTERVAL_S=5 make dev` (API `127.0.0.1:8001`, front `127.0.0.1:5173`).
- `make reset` (connexion admin + confirmation `RESET`, journal archivé), `make preflight` vert.
- Onglets : 1) `http://127.0.0.1:5173/` (écran « Connexion opérateur »), 2) la vidéo de secours en pause. Un terminal ouvert à la racine du dépôt avec la commande du RUNBOOK §« Avancer le portail local » prête.
- Connexion en démo locale : n'importe quel mot de passe, y compris vide, fonctionne en `WP_ENV=dev`. Ne pas saisir de vrai secret.

## Légende réalité

| Badge | Sens dans ce dépôt | Preuve |
|---|---|---|
| **RÉEL** | Exécuté par le code, sans tiers externe | code cité |
| **REPRODUCTION LOCALE** | Action technique réellement exécutée, vers une cible locale fictive (SMTP local, portail Dell reproduit) | `backend/app/actions/email/README.md`, `repro/dell/README.md` |
| **SIMULÉ** | État ou donnée produit sans action réelle | voir ci-dessous |

Ce qui reste simulé dans ce parcours :
- l'avancement du dossier **côté Dell** : c'est nous qui faisons passer la reproduction à `closed` par `POST /__test__/advance/<numéro>` (`repro/dell/README.md`). La lecture de ce statut par WarrantyPilot et le passage à « Résolu », eux, sont **réels** (`DellPortalFollowUp`, `backend/app/followup/portal.py`, `POST /api/followup/tick`) ;
- la réception du remplacement Jabra : un humain la déclare avec une note (« Marquer comme résolu », `POST /api/cases/{id}/resolve`). Le geste et sa trace sont réels, le colis est fictif ;
- l'achat de 120 € : une demande d'achat fictive insérée par le seed (`backend/app/core/reset.py`).

La **résolution n'est plus simulée par un faux adaptateur** : `FakeFollowUp` n'est plus branché en production (`backend/app/api/main.py` branche `CompositeFollowUp` + `DellPortalFollowUp`).

## Minutage

| Temps | Clic exact | Phrase à dire | Réalité | Plan B |
|---|---|---|---|---|
| 0:00–0:10 | Écran **« Connexion opérateur »** : **Personne** → *Paul Martin*, **Mot de passe**, **« Se connecter »** | « Chaque action est faite par une personne identifiée. Paul, opérateur, se connecte. » | **RÉEL** : `POST /api/auth/login`, session par cookie, rôle `operator` (`backend/app/api/routers/auth.py`). | « Identifiants invalides » : vérifier la personne sélectionnée et que `WP_ENV=dev` avec `WP_DEMO_ANY_PASSWORD=true`. |
| 0:10–0:20 | Menu **« Tableau de bord »** → **« Lancer le scan »** | « Appelia, 60 factures fictives. Le serveur lit tout, Factur-X compris, et applique des règles déterministes. On revient aux chiffres à la fin. » | **RÉEL** : lecture locale + moteur de règles (`backend/app/api/routers/scan.py`). Le tableau de bord porte le badge **REPRODUCTION** (données fictives). | Si le scan échoue : « on y revient », relancer à 2:40. |
| 0:20–0:40 | Menu **« Signalement »** : champ **« Décrivez votre panne »** → `Mon casque Jabra Evolve2 65 ne fonctionne plus.` → **« Envoyer »** | « Le chat annonce qu'il est assisté par une IA. Paul décrit la panne en une phrase. L'agent identifie le casque, retrouve la facture : couvert, sous 300 €, aucune ambiguïté. Il envoie seul. » | **RÉEL** : mention IA, identification, verdict, politique `auto_send` (`backend/app/core/policy.py`, seuil 300 € posé par le seed). **REPRODUCTION LOCALE** : vrai message SMTP vers `factures@revendeur-test.example`, déposé dans `runtime/mail/new`. | Si « Quel équipement… ? » : répondre `Jabra Evolve2 65`. |
| 0:40–0:50 | Lien **« Ouvrir le dossier créé #… »** | « Dossier en Suivi, canal e-mail revendeur, preuve d'envoi dans la ligne de temps, chaque événement signé HMAC dans le journal. » | **RÉEL** : statut `tracked`, journal (`backend/app/core/journal.py`). | Terminal : `ls -t runtime/mail/new \| head -1`. |
| 0:50–1:00 | **« Se déconnecter »** → se connecter en *Samy Benzeguir* | « Samy, administrateur, gère le parc. Clément l'appelle : son PC Dell ne démarre plus. » | **RÉEL** : rôle `admin`. | — |
| 1:00–1:10 | Menu **« Signalement »** : champ **« Décrivez votre panne »** → `Le PC 7XK4L93 de Clément ne démarre plus` → **« Envoyer »** → lien **« Ouvrir le dossier créé #… »** | « Samy signale pour Clément. Le Service Tag suffit : l'agent identifie le Latitude 7440 de Clément et crée le dossier, avec la procédure PC. » | **RÉEL** : le Service Tag exact identifie l'équipement quel que soit son propriétaire (#40) ; réponse « J'ai identifié Dell Latitude 7440 et créé le dossier de garantie. » ; dossier `awaiting_validation`, verdict **Couvert** (« acheté le 20/11/2025, facture (jusqu'au 19/11/2028) »), checklist de 7 étapes. Badge d'en-tête **SIMULÉ** tant que rien n'est exécuté. | Si « Quel équipement… ? » : répondre `7XK4L93`. |
| 1:10–1:20 | Lire « Verdict et trace des règles » et « Politique d'envoi » | « Couvert, mais 1 249 € et un PC contient des données : validation requise. » | **RÉEL** : `needs_validation`, raisons `under_threshold` et `low_commitment_action` en échec. | — |
| 1:20–1:45 | Section « Données du PC » → **7 × « Compléter »** | « Sept étapes : réparation, sauvegarde, chiffrement, disque, comptes et MDM, étiquette, contrôle au retour. Chaque clic est signé par Samy. » | **RÉEL** : `POST /api/cases/{id}/checklist/{step}`, événement journalisé. Étapes déclaratives, pas de contrôle physique. | RUNBOOK §« Plan B Dell » (boucle `curl`). |
| 1:45–1:55 | Bouton **« Valider »** (en haut du détail) | « Samy valide. L'agent prend la main. » | **RÉEL** : événement `validated` au nom de Samy. | Recharger (F5). |
| 1:55–2:10 | Recharger : statut **Suivi** ; faire défiler « Actions et preuves d'exécution » | « L'agent a rempli le portail avec le Service Tag 7XK4L93 et obtenu un numéro de dossier, avec une capture par étape. C'est une reproduction locale du site Dell : aucun envoi à Dell. » | **REPRODUCTION LOCALE** : navigateur piloté (moteur `scripted`) vers `127.0.0.1:8100`, « Numéro de dossier Dell : … », captures. Le badge d'en-tête passe à **REPRODUCTION** (il suit l'action exécutée). | « Échec » : **« Prendre la main »**, montrer les captures sauvegardées à J-1. |
| 2:10–2:20 | Terminal : RUNBOOK §« Avancer le portail local » (3 × `advance`) ; attendre ≤ 5 s, recharger | « Côté Dell, le dossier se clôt. WarrantyPilot relève le statut tout seul et passe le dossier en Résolu, preuve à l'appui. » | **SIMULÉ** : la clôture côté portail (endpoint de test). **RÉEL** : relève `DellPortalFollowUp`, événements `followup_received` puis `status_changed tracked → resolved`. | Si pas « Résolu » après 10 s : `POST /api/followup/tick` (RUNBOOK) ; sinon résolution humaine avec note. |
| 2:20–2:30 | Menu **« Garde-fou achat »** → **« Lancer la garantie et suspendre l'achat »** | « Pendant ce temps, quelqu'un commande un casque neuf à 120 €. L'ancien est sous garantie : on suspend, on ne compte encore rien. » | **RÉEL** : `purchase_suspended`, lié au dossier Jabra de Paul (`backend/app/api/routers/purchase_guard.py`). | Recharger. |
| 2:30–2:35 | **« Confirmer l’annulation de l’achat »** | « Achat annulé. Économie réelle : toujours 0 €, le remplacement n'est pas confirmé. » | **RÉEL** : état `cancelled`, « Économie réelle : 0,00 € ». | — |
| 2:35–2:45 | Lien **« Dossier de garantie #… »** → **« Note de résolution »** : `Remplacement reçu du revendeur (démo fictive).` → **« Marquer comme résolu »** → retour **« Garde-fou achat »** → **« Vérifier la résolution du dossier »** | « Le revendeur a remplacé le casque ; Samy le déclare, avec une note. Annulé et résolu : 120 € économisés. » | **RÉEL** : `POST /api/cases/{id}/resolve` (note obligatoire), état `saving_realized`. **SIMULÉ** : le colis. | Si le bouton n'apparaît pas : recharger la page. |
| 2:45–2:55 | **« Tableau de bord »** → **« Lancer le scan »** | « Trois chiffres : 14 064 € de matériel couvert, 0 € d'économies encore possibles, 120 € réalisés. » | **RÉEL** : valeurs mesurées 14 064 / 120 / 0 € avant le garde-fou, 14 064 / 0 / 120 € après ; 65 documents, 60 factures. | Citer ces chiffres « mesurés à la répétition ». |
| 2:55–3:00 | — | « WarrantyPilot : de la panne à la garantie prouvée, avec un humain là où ça compte. Merci. » | — | — |

## Écarts constatés au rejeu (à ne pas cacher)

1. Le garde-fou se lie au dossier Jabra ouvert le plus récent (`_ensure_linked_case`) ; si le dossier de Paul est déjà résolu, il en crée un nouveau, à résoudre à son tour.
