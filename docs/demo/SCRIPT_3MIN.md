# Script de démo — 3 minutes

Données 100 % fictives (Appelia, domaines `.example`, Service Tag fictif `7XK4L93`, voir `data/appelia/README.md`). Aucun envoi à un fabricant, aucun service public : tout écoute sur `127.0.0.1`.

Mesures relevées en local le 14/11/2026 sur la branche `integration` (commit `374cf82`) : scan de 65 documents en 0,8 s, dossier Dell envoyé à la reproduction locale en 1,9 s après validation (moteur `scripted`, valeur par défaut de `backend/app/actions/browser/settings.py`).

## Pré-requis (fait à H-30, voir `RUNBOOK.md`)

- `make dev` (API `127.0.0.1:8001`, front `127.0.0.1:5173`), `make smtp` (Maildir `runtime/mail`), reproduction Dell (`127.0.0.1:8100`).
- `make reset` puis création du dossier Dell (commande `curl …/api/dev/fake-case`, `RUNBOOK.md` §H-30). Ce dossier doit exister **avant** la démo, voir « Écart connu » ci-dessous.
- Onglets ouverts : 1) `http://127.0.0.1:5173/dashboard`, 2) `http://127.0.0.1:5173/chat`, 3) `http://127.0.0.1:5173/` (Décisions), 4) `http://127.0.0.1:5173/purchase-guard`, 5) la vidéo de secours en pause.

## Légende réalité

| Badge | Sens dans ce dépôt | Preuve |
|---|---|---|
| **RÉEL** | Calcul ou action réellement exécuté par le code, sans tiers externe | code cité |
| **REPRODUCTION LOCALE** | Action technique réellement exécutée, mais vers une cible locale fictive (SMTP local, faux portail Dell) | `backend/app/actions/email/README.md`, `repro/dell/README.md` |
| **SIMULÉ** | État produit par un faux adaptateur, sans action réelle | `FakeFollowUp` dans `backend/app/testing/fakes.py`, branché par `backend/app/api/main.py` |

## Minutage

| Temps | Clic exact | Phrase à dire | Réalité | Plan B |
|---|---|---|---|---|
| 0:00–0:10 | Onglet 1 (Tableau de bord), bouton **« Lancer le scan »** | « Appelia, 230 équipements, 60 factures fictives. WarrantyPilot lit tout et applique des règles déterministes. Je lance le scan, on revient aux chiffres à la fin. » | **RÉEL** : lecture locale du jeu Appelia, extraction Factur-X, moteur de règles YAML (`backend/app/api/routers/scan.py`). Le badge affiché par l'API est `reproduction` car les données sont fictives. | Si le scan échoue : ne pas insister, dire « on y revient », relancer à 2:40. |
| 0:10–0:20 | Onglet 2 (Signalement). Liste **« Vous agissez en tant que »** → **Paul Martin** | « Paul est au service client. Son casque Jabra vient de lâcher. Il le dit simplement, dans le chat. » | **RÉEL** : la mention IA s'affiche (`DISCLOSURE_TEXT`, `backend/app/api/routers/chat.py`). | Si Paul n'apparaît pas : `make reset` a échoué → vidéo de secours (segment Paul). |
| 0:20–0:40 | Champ **« Décrivez votre panne »** : `Mon casque Jabra Evolve2 65 ne fonctionne plus.` → bouton **« Envoyer »** | « L'agent identifie l'équipement, retrouve la facture, la règle Jabra dit : couvert. Le montant est sous 300 €, pas d'ambiguïté, pas d'exclusion : il envoie seul. » | **RÉEL** : identification, verdict, politique d'envoi (`backend/app/core/policy.py`, seuil 300 € posé par `backend/app/core/reset.py`). | Si « Quel équipement… ? » apparaît : répondre `Jabra Evolve2 65`. |
| 0:40–0:55 | Menu **« Dossiers »** → dossier Jabra (statut **Résolu**) → section « Ligne de temps » | « Voici l'e-mail parti au revendeur, avec la facture et le marqueur IA. Tout est dans un journal en ajout seul, chaîné par hash. » | **REPRODUCTION LOCALE** : un vrai message SMTP, déposé dans `runtime/mail/new`, destinataire `factures@revendeur-test.example`. **SIMULÉ** : le passage à « Résolu » vient de `FakeFollowUp` (réponse `resolved`). | Montrer le fichier dans `runtime/mail/new` (terminal pré-ouvert : `ls -t runtime/mail/new \| head -1`). |
| 0:55–1:05 | Onglet 3 (Décisions). Liste **« Vous agissez en tant que »** → **Karim Benali** | « Deuxième cas : un PC Dell, 1 249 €. Au-dessus du seuil, et un PC contient des données : l'agent s'arrête et demande un humain. » | **RÉEL** : politique `blocked` / raison `data_checklist_incomplete` (`backend/app/core/policy.py`). | Si la carte Dell est absente : le dossier n'a pas été créé à H-30 → lancer la commande `fake-case` du RUNBOOK (5 s). |
| 1:05–1:30 | Lien **« Voir le détail »** de la carte Dell → section « Données du PC » → **7 × « Compléter »** | « Sept étapes : type de réparation, sauvegarde, chiffrement, disque, comptes et MDM, étiquette, contrôle au retour. Chaque clic est signé par Karim dans le journal. » | **RÉEL** : `POST /api/cases/{id}/checklist/{step}` (`backend/app/api/routers/cases.py`), événement `checklist_step_done`. Les étapes sont déclarées, pas contrôlées physiquement. | Si un bouton ne répond pas : vérifier que Karim est sélectionné ; sinon terminal : boucle `curl` du RUNBOOK §Plan B Dell. |
| 1:30–1:40 | Bouton **« Valider »** (apparaît en haut du détail) | « Karim valide. L'agent prend la main. » | **RÉEL** : événement `validated` avec l'identité de Karim. | Si « Valider » n'apparaît pas : recharger la page (F5). |
| 1:40–2:05 | Rester sur le détail ; faire défiler « Actions et preuves d'exécution » puis « Ligne de temps » | « L'agent ouvre le portail, se connecte, remplit le formulaire avec le Service Tag 7XK4L93, et obtient un numéro de dossier. Chaque étape a sa capture. Attention : c'est une reproduction locale du site Dell ; en production, on passera par l'API officielle. » | **REPRODUCTION LOCALE** : navigateur Playwright piloté par script vers `http://127.0.0.1:8100` (bandeau « Reproduction locale du support Dell France — Données fictives, aucun envoi à Dell »). Numéro de dossier et 4 captures (`01-signin` → `04-confirmation`) dans `runtime/browser/screenshots/<action_id>/`. **SIMULÉ** : « Résolu » (`FakeFollowUp`). | Si l'action échoue (statut « Échec ») : bouton **« Prendre la main »**, puis montrer les captures pré-enregistrées (RUNBOOK §captures). |
| 2:05–2:15 | Onglet 4 (Garde-fou achat) | « Pendant ce temps, quelqu'un commande un casque neuf à 120 €. Or l'ancien est encore sous garantie. » | **RÉEL** : demande d'achat fictive insérée par `backend/app/core/reset.py`, verdict `covered`. | Recharger. Si vide : `make reset` n'a pas tourné. |
| 2:15–2:25 | Bouton **« Lancer la garantie et suspendre l'achat »** | « On ne dit pas encore qu'on a économisé : l'achat est seulement suspendu. » | **RÉEL** : état `purchase_suspended` (`backend/app/api/routers/purchase_guard.py`). | Si erreur : vidéo de secours (segment garde-fou). |
| 2:25–2:40 | Bouton **« Confirmer l’annulation de l’achat »** | « L'économie n'est comptée que si l'achat est annulé **et** le dossier résolu. Les deux sont vrais : 120 € économisés. » | **RÉEL** : la règle « annulé + résolu » est appliquée côté serveur. **SIMULÉ** : la résolution du dossier lié vient de `FakeFollowUp`. Le bouton « Vérifier la résolution du dossier » n'apparaît que si le dossier n'est pas encore résolu. | Si l'état reste « annulé » sans « économisés » : cliquer « Vérifier la résolution du dossier ». |
| 2:40–2:55 | Onglet 1 (Tableau de bord), **« Lancer le scan »** de nouveau | « Trois chiffres : 9 266 € de matériel couvert, 0 € d'économies encore possibles, 120 € d'économies réalisées. » | **RÉEL** : calcul de `scan.py` sur les données fictives. Valeurs mesurées : avant le garde-fou 9 266 / 120 / 0 €, après 9 266 / 0 / 120 €, 60 factures, 65 documents. | Si le scan échoue : citer les chiffres de ce tableau, en disant qu'ils ont été mesurés à la répétition. |
| 2:55–3:00 | — | « WarrantyPilot : de la panne à la garantie prouvée, avec un humain là où ça compte. Merci. » | — | — |

## Écart connu (à ne pas cacher si on vous le demande)

- Un PC Dell signalé **par le chat** ne crée pas la procédure « Données du PC » : la page n'affiche pas les boutons « Compléter » (`Checklist` renvoie `null` sur 404, `frontend/src/pages/Cases.tsx`). Le dossier Dell de la démo est donc créé avant, par la route de développement `POST /api/dev/fake-case`, qui crée la checklist pour les catégories `computer` / `laptop` / `notebook` (`backend/app/api/routers/demo.py`). Conséquence visible : le formulaire Dell est rempli avec la personne et le texte par défaut de cette route (observé : « Thomas Dupont », « Le casque ne fonctionne plus. »).
- Le verdict Dell affiché est **« À vérifier : preuve d'achat absente »** (règle `dell-latitude` v1, `purchase_date` manquante), alors que `data/appelia/equipment.json` contient une date d'achat. Dire : « le moteur ne trouve pas la preuve datée, donc il ne conclut pas : c'est pour ça qu'un humain valide ».
- L'en-tête du détail du dossier Dell affichait le libellé « E-mail revendeur » alors que le canal est `browser_portal`.
- Les captures sont référencées par leur chemin dans la ligne de temps (pas d'aperçu image) ; elles sont servies par `GET /api/cases/{id}/screenshots/{name}?action_id=…`.
- Le « scan en fond » prend moins d'une seconde sur ce jeu : on le lance au début et on le relance à la fin pour rafraîchir les chiffres.
