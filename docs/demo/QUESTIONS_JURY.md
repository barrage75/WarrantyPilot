# Questions probables du jury (25)

Chaque réponse sépare **Fait vérifié** (code ou commande du dépôt, rejoué le 14/11/2026 sur `integration`, ou source officielle citée dans `docs/PLAN_V4.md`) et **Hypothèse** (commercial, futur, non vérifié dans ce MVP).

## Produit et réalité de la démo

**1. Qu'est-ce qui est vraiment exécuté dans la démo ?**
- Fait : connexion, scan, règles, politique d'envoi, checklist, validation, journal, relève du suivi et résolution sont exécutés par le code. L'e-mail part réellement en SMTP vers un serveur local (`runtime/mail`). Le portail Dell est une reproduction locale (`repro/dell/README.md`). Seuls la clôture du dossier côté portail (`POST /__test__/advance/<numéro>`), le remplacement physique et l'achat de 120 € sont simulés.

**2. Avez-vous fait une vraie demande à Dell ou Jabra ?**
- Fait : non. Données fictives, destinataires `.example`, portail sur `127.0.0.1:8100` avec bandeau « aucun envoi à Dell » ; le suivi refuse toute URL non loopback et les redirections (`backend/app/followup/README.md`).

**3. Qui décide si l'équipement est couvert ?**
- Fait : un moteur de règles YAML déterministe et versionné, avec trace de chaque contrôle (`backend/app/rules/README.md`). Le Dell 7XK4L93 est « Couvert » (36 mois, jusqu'au 19/11/2028) grâce à sa facture Factur-X. Le LLM ne décide pas du verdict.

**4. Quand l'agent envoie-t-il seul ?**
- Fait : seulement si les 6 conditions sont vraies (sous le seuil, couvert, non ambigu, sans exclusion, sans signal suspect, action à faible engagement), agent non en pause, checklist PC complète si requise (`backend/app/core/policy.py`). Seuil de démo 300 € (`backend/app/core/reset.py`). Jabra : `auto_send` ; Dell : `needs_validation`.

**5. Comment un dossier passe-t-il à « Résolu » ?**
- Fait : deux voies seulement. (a) Le suivi (`POST /api/followup/tick` ou tâche périodique `WP_FOLLOWUP_INTERVAL_S`) relève le statut du portail via `DellPortalFollowUp` ; au statut `closed`, il journalise `followup_received` et passe `tracked → resolved`. (b) Un humain clique « Marquer comme résolu » avec une note obligatoire (`POST /api/cases/{id}/resolve`). `FakeFollowUp` n'est plus branché en production (`backend/app/api/main.py`).

**6. Comment prouvez-vous ce qui s'est passé ?**
- Fait : journal en ajout seul, chaîné par hash, HMAC sur chaque événement et ancres (`backend/app/core/journal.py`), vérifiable par `GET /api/journal/verify` (rejeu : `"ok": true`, 67 événements). Le reset archive le journal dans `runtime/journal-archive/<horodatage>/` avant de recréer la base. Cela détecte une modification ; cela ne protège pas si la machine et la clé sont compromises (`docs/SECURITY.md`).

## Sécurité et injection de prompt

**7. Une facture piégée peut-elle ordonner à l'agent d'envoyer un e-mail ailleurs ?**
- Fait : documents, e-mails, pages web et sorties du modèle sont non fiables ; seul le code serveur attribue des capacités (`docs/SECURITY.md`). Destinataires limités par `email_allowlist`, URL du navigateur par `browser_allowed_origins` (`url_not_allowed`, `backend/app/actions/browser/README.md`).

**8. L'allowlist du navigateur suffit-elle ?**
- Fait : non, c'est une garde applicative, pas un contrôle réseau (`docs/SECURITY.md`).
- Hypothèse : en production, proxy de sortie et isolation réseau.

**9. L'API est-elle protégée ?**
- Fait : session obligatoire après `POST /api/auth/login` (mot de passe `WP_DEMO_PASSWORD`, exigé hors `WP_ENV=dev`) ; rôles `admin` (Karim Benali) et `operator` ; reset et réglages réservés à l'admin (`require_admin`, `backend/app/api/dependencies.py`) avec confirmation `RESET`. Contrôle Host/Origin : constaté 401 sans session, 400 pour `Host: evil.example`, 403 pour `Origin: http://evil.example`. Un `person_id` différent de la session est refusé (403).
- Hypothèse : SSO de l'entreprise et mots de passe individuels avant un pilote ; aujourd'hui un mot de passe de démo partagé, services sur `127.0.0.1` seulement.

**10. Que se passe-t-il si l'agent se trompe en plein envoi ?**
- Fait : « Mettre en pause » global, clé d'idempotence par action et par relève de suivi, contrôle `no_stuck_sending` au préflight, « Prendre la main » sur un échec (`backend/app/api/routers/cases.py`).

## RGPD et AI Act

**11. Quelles données personnelles traitez-vous ?**
- Fait : dans le MVP, uniquement des personnes fictives (`data/appelia/README.md`).
- Hypothèse : en production, nom/e-mail des employés et adresse d'expédition ; base légale, minimisation et conservation à définir avec un DPO.

**12. Les données d'un PC envoyé en réparation ?**
- Fait : procédure en 7 étapes créée automatiquement quand le PC est signalé par le chat ou l'e-mail, obligatoire avant envoi, chaque étape signée au nom de la personne connectée. Déclaratif : le logiciel ne vérifie pas physiquement le disque.

**13. Êtes-vous conformes à l'AI Act ?**
- Fait : le chat affiche « Cette conversation est assistée par une intelligence artificielle… » (`backend/app/api/routers/chat.py`), cf. article 50(1). Les e-mails portent l'en-tête `X-WarrantyPilot-AI: generated` et une phrase de transparence.
- Hypothèse : la portée de l'article 50(2) pour nos e-mails reste à valider par un juriste (`docs/PLAN_V4.md` §2.2).

**14. Est-ce un système à haut risque ?**
- Hypothèse : a priori non (garanties matérielles, humain dans la boucle), à confirmer juridiquement.

## Dell, fabricants, canaux

**15. Avez-vous le droit d'automatiser le site Dell ?**
- Fait : nous n'automatisons pas le site Dell, mais une reproduction locale.
- Hypothèse : les CGU des sites fabricants peuvent interdire l'automatisation ; en production, API officielle (Dell TechDirect) quand elle existe, navigateur en exception validée (`docs/PLAN_V4.md` §5).

**16. Avez-vous un accès à l'API Dell ?**
- Fait : non, pas de compte TechDirect dans ce MVP.

**17. Pourquoi un agent navigateur alors ?**
- Fait : moteurs `scripted` (défaut, démo), H Company, Browser Use (`backend/app/actions/browser/settings.py`). En démo, le moteur scripté remplit le formulaire avec le Service Tag, obtient un numéro de dossier et capture chaque étape ; le suivi relit ensuite la page de statut du même portail.
- Hypothèse : beaucoup de fabricants n'ont qu'un portail web.

## Gmail et boîte de réception

**18. Lisez-vous la boîte mail du client ?**
- Fait : la démo utilise un SMTP/Maildir local ; l'écran **Documents** et `POST /api/intake/poll` relèvent une boîte locale (`backend/app/api/routers/intake.py`). Le plan limite Gmail à `gmail.readonly` (restreinte) et `gmail.send` (sensible) (`docs/PLAN_V4.md` §2.4).
- Fait (source Google citée dans le plan) : en mode test l'autorisation expire après 7 jours ; en production, une permission restreinte avec stockage serveur impose vérification et évaluation CASA annuelle.
- Hypothèse : adresse de transfert `factures@<client>` et envoi depuis notre domaine pour éviter le scope restreint.

## Facture électronique

**19. Lisez-vous les factures avec un LLM ?**
- Fait : les Factur-X sont lues depuis le XML embarqué (CII ou UBL, `backend/app/ingestion/README.md`) ; c'est cette lecture qui fournit la date d'achat du Dell. Le scan traite 65 documents, dont 60 factures fictives.

**20. Pourquoi maintenant ?**
- Fait (source officielle citée dans `docs/PLAN_V4.md` §2.3) : réception obligatoire des factures électroniques depuis le 1/9/2026 ; émission 2026 grandes entreprises/ETI, 2027 PME. Formats UBL, CII, Factur-X.
- Hypothèse : connexion à la plateforme agréée du client, selon l'ouverture de son API.

## Modèle économique et marché

**21. Comment gagnez-vous de l'argent ?**
- Hypothèse : scan gratuit puis abonnement par équipement ; prix fixé après entretiens (`docs/PLAN_V4.md` §3).

**22. Qui achète ?**
- Hypothèse : le DAF (économies prouvées), en commençant par les centres de service client.

**23. Vos chiffres d'économies sont-ils réels ?**
- Fait : sur le jeu fictif, 14 064 € de matériel couvert ; 120 € réalisés seulement après annulation de l'achat **et** résolution du dossier lié (`backend/app/api/routers/purchase_guard.py`, état `saving_realized`).
- Hypothèse : aucun chiffre client réel à ce jour.

**24. Et la concurrence ?**
- Fait (cité dans `docs/PLAN_V4.md` §3) : ScalePad suit les garanties pour les infogérants sans faire les demandes ; il existe des agents de demande côté revendeurs et fabricants.
- Hypothèse : notre différence est côté propriétaire, jusqu'à la résolution, multi-canal, avec prévention à l'achat.

**25. Qu'est-ce qui manque pour un pilote ?**
- Fait : les écarts relevés au rejeu précédent (signalement par Service Tag, badge du dossier, « p. None ») sont corrigés par #40. Reste constaté : le garde-fou se lie au dossier Jabra ouvert le plus récent.
- Hypothèse : comptes individuels/SSO, vrais connecteurs fabricants (API officielles), boîte réelle ; 4 à 6 semaines selon `docs/PLAN_V4.md` §10.
