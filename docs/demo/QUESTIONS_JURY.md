# Questions probables du jury (25)

Chaque réponse sépare **Fait vérifié** (code ou commande du dépôt, ou source officielle citée dans `docs/PLAN_V4.md`) et **Hypothèse** (commercial, futur, non vérifié dans ce MVP).

## Produit et réalité de la démo

**1. Qu'est-ce qui est vraiment exécuté dans la démo ?**
- Fait : scan, règles, politique d'envoi, journal et checklist sont exécutés par le code (`backend/app/api/routers/scan.py`, `backend/app/core/policy.py`). L'e-mail part réellement en SMTP, mais vers un serveur local (`make smtp`, `runtime/mail`). Le portail Dell est une reproduction locale (`repro/dell/README.md`). La résolution des dossiers est simulée (`FakeFollowUp`, `backend/app/testing/fakes.py`).
- Hypothèse : en production, suivi réel par lecture des réponses revendeur/fabricant.

**2. Avez-vous fait une vraie demande à Dell ou Jabra ?**
- Fait : non. Données fictives, destinataires `.example`, portail sur `127.0.0.1:8100` avec bandeau « aucun envoi à Dell ». L'allowlist navigateur est limitée à `localhost` / `127.0.0.1` (`GET /api/settings`).

**3. Qui décide si l'équipement est couvert ?**
- Fait : un moteur de règles YAML déterministe, versionné, avec trace de chaque contrôle (`backend/app/rules/README.md`) ; le LLM ne décide pas du verdict.

**4. Quand l'agent envoie-t-il seul ?**
- Fait : seulement si les 6 conditions sont vraies (sous le seuil, couvert, équipement non ambigu, pas d'exclusion, pas de signal suspect, action à faible engagement), agent non en pause, checklist PC complète si requise (`backend/app/core/policy.py`). Seuil de démo : 300 € (`backend/app/core/reset.py`).

**5. Pourquoi le Dell affiche « À vérifier » ?**
- Fait : la règle `dell-latitude` v1 ne trouve pas de `purchase_date` dans les faits du dossier, donc le verdict est `to_verify` et un humain valide. C'est un écart connu (date présente dans `data/appelia/equipment.json` mais non transmise au dossier).

**6. Comment prouvez-vous ce qui s'est passé ?**
- Fait : journal en ajout seul, chaîné par hash avec ancre HMAC, vérifiable via `GET /api/journal/verify` et le préflight (`DECISIONS.md`, `backend/app/core/preflight.py`). Il détecte une modification ; il ne protège pas si la machine et la clé sont compromises (`docs/SECURITY.md`).

## Sécurité et injection de prompt

**7. Une facture piégée peut-elle ordonner à l'agent d'envoyer un e-mail ailleurs ?**
- Fait : documents, e-mails, pages web et sorties du modèle sont traités comme non fiables ; seul le code serveur attribue des capacités (`docs/SECURITY.md`). Les destinataires e-mail sont limités par `email_allowlist`, les URL du navigateur par `browser_allowed_origins` (une URL hors liste arrête l'action avec `url_not_allowed`, `backend/app/actions/browser/README.md`).

**8. L'allowlist du navigateur suffit-elle ?**
- Fait : non, c'est une garde applicative, pas un contrôle réseau (`docs/SECURITY.md`).
- Hypothèse : en production, proxy de sortie et isolation réseau.

**9. L'API est-elle sécurisée ?**
- Fait : pas d'authentification au stade L0 ; elle doit rester sur `127.0.0.1` (`README.md`, `docs/SECURITY.md`). Les secrets sont masqués (`***`) dans le journal.
- Hypothèse : SSO et rôles avant tout pilote client.

**10. Que se passe-t-il si l'agent se trompe en plein envoi ?**
- Fait : bouton « Mettre en pause » global, clé d'idempotence par action, contrôle `no_stuck_sending` au préflight, reprise manuelle « Prendre la main » sur un échec (`backend/app/api/routers/cases.py`).

## RGPD et AI Act

**11. Quelles données personnelles traitez-vous ?**
- Fait : dans le MVP, uniquement des personnes fictives (`data/appelia/README.md`).
- Hypothèse : en production, nom/e-mail des employés et adresse d'expédition ; base légale intérêt légitime, minimisation et durée de conservation à définir avec un DPO.

**12. Les données d'un PC envoyé en réparation ?**
- Fait : procédure en 7 étapes obligatoire avant envoi (sauvegarde, chiffrement, disque, comptes/MDM…), chaque étape signée dans le journal. Elles sont déclaratives : le logiciel ne vérifie pas physiquement le disque.

**13. Êtes-vous conformes à l'AI Act ?**
- Fait : le chat affiche « Cette conversation est assistée par une intelligence artificielle… » (`backend/app/api/routers/chat.py`) — article 50(1). Les e-mails portent l'en-tête `X-WarrantyPilot-AI: generated` et une phrase de transparence (observé dans `runtime/mail/new`).
- Hypothèse : la portée exacte de 50(2) pour nos e-mails est à faire valider par un juriste (`docs/PLAN_V4.md` §2.2). On ne dit pas que la loi impose de signer chaque e-mail.

**14. Est-ce un système à haut risque ?**
- Hypothèse : a priori non (gestion de garanties matérielles, humain dans la boucle), à confirmer juridiquement.

## Dell, fabricants, canaux

**15. Avez-vous le droit d'automatiser le site Dell ?**
- Fait : nous ne l'automatisons pas ; nous automatisons une reproduction locale.
- Hypothèse : les conditions d'utilisation des sites fabricants peuvent interdire l'automatisation ; en production on passe par l'API officielle (Dell TechDirect) quand elle existe, le navigateur restant une exception validée (`docs/PLAN_V4.md` §5).

**16. Avez-vous un accès à l'API Dell ?**
- Fait : non, pas de compte TechDirect dans ce MVP (`docs/PLAN_V4.md` §14.3, « optionnel »).

**17. Pourquoi un agent navigateur alors ?**
- Fait : moteurs prévus `scripted` (défaut, démo), H Company, Browser Use (`backend/app/actions/browser/settings.py`). En démo, le moteur scripté remplit le formulaire et capture 4 écrans.
- Hypothèse : beaucoup de fabricants n'ont qu'un portail web ; l'agent couvre la longue traîne.

## Gmail

**18. Lisez-vous la boîte mail du client ?**
- Fait : la démo utilise un SMTP/Maildir local. Le plan limite Gmail à `gmail.readonly` (restreinte) et `gmail.send` (sensible) (`backend/app/actions/email/README.md`, `docs/PLAN_V4.md` §2.4).
- Fait (source Google citée dans le plan) : en mode test, l'autorisation expire après 7 jours ; en production, une permission restreinte avec données sur notre serveur impose une vérification et une évaluation CASA annuelle.
- Hypothèse : en production, adresse de transfert `factures@<client>…` et envoi depuis notre domaine pour éviter le scope restreint.

## Facture électronique

**19. Lisez-vous les factures avec un LLM ?**
- Fait : les Factur-X sont lues directement depuis le XML embarqué (CII ou UBL, `backend/app/ingestion/README.md`) ; 10 des 60 factures fictives sont en Factur-X. Un PDF ordinaire sans clé de modèle reste « extraction en attente ».

**20. Pourquoi maintenant ?**
- Fait (source officielle citée dans `docs/PLAN_V4.md` §2.3) : réception obligatoire des factures électroniques depuis le 1/9/2026 ; émission 2026 grandes entreprises/ETI, 2027 PME. Formats UBL, CII, Factur-X.
- Hypothèse : se brancher sur la plateforme agréée du client ; l'ouverture d'API aux tiers dépend de chaque plateforme.

## Modèle économique et marché

**21. Comment gagnez-vous de l'argent ?**
- Hypothèse : scan gratuit puis abonnement par équipement ; prix fixé après entretiens (`docs/PLAN_V4.md` §3).

**22. Qui achète ?**
- Hypothèse : le DAF (économies prouvées), en commençant par les centres de service client (casques, PC).

**23. Vos chiffres d'économies sont-ils réels ?**
- Fait : sur le jeu fictif, 9 266 € de matériel couvert et 120 € réalisés après annulation + résolution (simulée). Le serveur ne compte une économie qu'avec ces deux conditions (`backend/app/api/routers/purchase_guard.py`).
- Hypothèse : aucun chiffre client réel à ce jour.

**24. Et la concurrence ?**
- Fait (cité dans `docs/PLAN_V4.md` §3) : ScalePad suit les garanties pour les infogérants sans faire les demandes ; il existe des agents de demande de garantie côté revendeurs et fabricants.
- Hypothèse : notre différence est côté propriétaire, jusqu'à la résolution, multi-canal, avec prévention à l'achat.

**25. Qu'est-ce qui manque pour un pilote ?**
- Fait : authentification, suivi réel des réponses (aujourd'hui `FakeFollowUp`), checklist PC depuis le chat, transmission de la date d'achat au dossier Dell, cible `make p0`.
- Hypothèse : 4 à 6 semaines selon la feuille de route (`docs/PLAN_V4.md` §10).
