# WarrantyPilot — Plan V4 (version finale proposée)

> **Statut :** proposition finale, en attente de ta validation. **Aucun code, aucun test, aucune intégration** avant ton feu vert explicite.
> V4 = V3 + les corrections ciblées que tu as demandées le 14/11/2026. Les parties de la V3 que je ne répète pas restent valables (marché détaillé, concurrence, glossaire) : `PLAN_V3.md`.
>
> **Légende :** ✅ fait vérifié (avec source) · 🔶 hypothèse (commerciale ou juridique) à valider · 💡 ma recommandation · 🧑 ta décision

---

## 0. Ce qui change par rapport à la V3

| # | Sujet | V3 | V4 |
|---|---|---|---|
| 1 | Jabra, 30 jours | « Délai de déclaration de 30 jours » ✅ | **Corrigé** : le texte officiel ne précise pas à partir de quand courent les 30 jours. Pour Warranty+, les 30 jours concernent **l'erreur sur le certificat**, pas la panne. Et une demande Warranty+ se fait auprès du **support Jabra**, pas du revendeur (section 2.1) |
| 2 | Loi européenne sur l'IA | « Signature IA obligatoire dans chaque e-mail » | **Corrigé** : on distingue trois obligations différentes ; la signature des e-mails est un **choix de transparence**, pas une obligation générale (2.2) |
| 3 | Facture électronique | Réception obligatoire | **Complété** : formats UBL, CII et Factur-X, et le rôle des plateformes agréées (2.3) |
| 4 | Gmail | Lecture + envoi, expiration à 7 jours | **Approfondi** : classement de chaque permission, vérification Google, évaluation de sécurité annuelle, stratégie pour la production (2.4) |
| 5 | PC envoyé en réparation | Un simple rappel | **Procédure complète en 7 étapes**, bloquante dans le code (6.3) |
| 6 | Journal | « Ineffaçable » | **Journal en ajout seul + chaîne d'empreintes + vérification d'intégrité** (7) |
| 7 | Garde-fou achat | Un seul état | **Recommandation → Demande de validation → Économie réalisée**, avec des preuves (6.2) |
| 8 | Plusieurs agents | Principe général | **Organisation précise** : responsabilités, contrats, modèles de données, branches, intégration, tests (9) |
| 9 | Périmètre | Cœur / bonus / optionnel | **4 niveaux de priorité** avec une règle stricte : on ne passe au niveau suivant que si le précédent est irréprochable (4) |
| 10 | Réel / reproduction / simulé | Badges | **Tableau étape par étape de toute la démo** (5) |
| 11 | Skills | Liste | **Inventaire et rôle de chacun** ; aucun nouveau skill nécessaire (12) |

---

## 1. L'idée en une phrase

Un agent IA **au service de l'entreprise propriétaire du matériel**. Il transforme une panne, ou une demande d'achat, en démarche de garantie complète et prouvée. Il suit ensuite le dossier jusqu'à sa résolution, et il ne compte une économie que lorsqu'elle est prouvée.

---

## 2. Vérifications et corrections (sources officielles, consultées le 14/11/2026)

### 2.1 Jabra : les délais et les canaux

**Garantie standard (conditions business Jabra)** ✅

- Texte exact : « *contact the GN partner from which the product was purchased **inside 30 days** or visit our Support pages* ».
- ⚠️ **Le texte ne dit pas à partir de quand** courent les 30 jours (date de la panne ? date d'achat ?). La V3 se trompait en parlant d'un « délai de déclaration de la panne » vérifié.
- Le produit défectueux doit être **renvoyé et reçu avant** l'expédition du remplacement, sauf indication contraire de Jabra ✅.
- L'envoi du produit vers Jabra est **à la charge du client** ; le retour est payé par Jabra si la garantie s'applique ✅.
- Un produit réparé ou remplacé est garanti **12 mois, ou le reste de la garantie d'origine** si c'est plus long ✅.
- Les consommables (cordons, coussinets, serre-têtes…) sont **exclus**, sauf s'ils sont défectueux dans les 14 jours après l'achat ✅.
- Sans preuve d'achat, Jabra **peut**, à sa discrétion, se baser sur le numéro de série ✅.

**Jabra Warranty+ (extension, conditions du 16/06/2025)** ✅

- Elle ne s'achète **qu'en même temps que le produit**.
- Elle prolonge **uniquement la durée** de la garantie, pas ce qu'elle couvre. Elle démarre à la fin de la garantie standard.
- Les **30 jours** concernent ici une autre chose : signaler une **erreur dans le certificat Warranty+** (par exemple un numéro de série faux), dans les 30 jours après sa réception.
- La demande se fait auprès du **support Jabra** (téléphone ou e-mail), **pas du revendeur**, et dans le pays d'achat. Ces conditions s'appliquent même pendant la période standard pour un produit couvert par Warranty+.
- Pièces demandées : le certificat Warranty+, le modèle, la référence du produit (SKU), le numéro de série, la date d'achat et une description de la panne. La preuve d'achat du produit et de Warranty+ peut être demandée.

**Ce que ça change dans le moteur de règles** 💡

- `delai_contact_jours: 30` avec `point_de_depart: non_precise`. L'agent affiche « contacter le revendeur au plus vite », mais **ne bloque jamais** une demande à cause de ce délai.
- Deux règles Jabra différentes :
  - garantie standard → canal **e-mail au revendeur** ;
  - Warranty+ → canal **support Jabra**, avec le certificat obligatoire.
- Un nouveau cas de test : « casque avec Warranty+ au-delà de 2 ans » → `Couvert`, canal support Jabra, certificat joint.
- Exclusion des consommables : « le coussinet est usé » → `Non couvert`, avec la raison.
- Suivi : « produit à renvoyer avant remplacement » devient une étape de suivi, avec prise en charge des frais d'envoi.

### 2.2 Loi européenne sur l'IA (AI Act, article 50) : trois obligations différentes

Les obligations de l'article 50 s'appliquent depuis le **2/8/2026** ✅ (Commission européenne).

| Obligation | À qui | S'applique à WarrantyPilot ? |
|---|---|---|
| **50(1) Informer** les personnes qui **interagissent directement** avec un système d'IA, sauf si c'est évident | Fournisseur du système | ✅ **Oui pour le chat** : l'employé parle à l'agent → mention « assistant IA » visible dès le début. 🔶 Pour l'e-mail au revendeur : incertain, puisque le revendeur ne « dialogue » pas forcément avec l'IA |
| **50(2) Marquer** les contenus générés (texte, image, son, vidéo) dans un format **lisible par une machine**, quand c'est techniquement possible (exception : simple aide à la rédaction) | Fournisseur d'un système qui génère du contenu synthétique | 🔶 **À faire vérifier par un juriste** avant un vrai produit. Selon toute vraisemblance, l'obligation porte surtout sur les fournisseurs de modèles et d'outils génératifs |
| **50(4) Signaler** un texte généré **publié pour informer le public** sur des sujets d'intérêt public (sauf relecture humaine et responsabilité éditoriale) | Celui qui utilise le système | ❌ **Non** : un e-mail privé à un revendeur n'est pas « publié » au sens des lignes directrices (lu par un nombre indéterminé de personnes) ✅ |

💡 **Ce qu'on fait :**

- **Chat** : mention « Vous échangez avec l'assistant IA de WarrantyPilot ». C'est une **obligation**.
- **E-mails** : la phrase « préparé par l'assistant IA WarrantyPilot pour le compte d'Appelia » est un **choix de transparence et de confiance**, pas une obligation générale. En plus, on ajoute un marqueur technique invisible dans l'e-mail (en-tête `X-WarrantyPilot-AI: generated`), qui ne coûte rien et prépare le 50(2).
- On ne dit **jamais** au jury « la loi oblige à signer chaque e-mail ».

### 2.3 Facturation électronique en France ✅

- Depuis le **1/9/2026**, toutes les entreprises assujetties à la TVA doivent pouvoir **recevoir** des factures électroniques. L'**émission** est obligatoire en 2026 pour les grandes entreprises et les ETI, en 2027 pour les PME et micro-entreprises.
- **Les trois formats** du socle :
  - **UBL** et **CII** : des fichiers de données purs (XML) ;
  - **Factur-X** : un PDF lisible par un humain, avec les données XML intégrées dedans (format « hybride »).
- **Le rôle des plateformes agréées (PA)** : ce sont des prestataires immatriculés par l'administration (pour 3 ans, renouvelable). Elles :
  1. **émettent, transmettent et reçoivent** les factures, et peuvent les **convertir** dans le format du destinataire ;
  2. **extraient et transmettent** les données fiscales à l'administration ;
  3. transmettent les données de transaction et de paiement (*e-reporting*) ;
  4. **suivent le statut** de chaque facture (reçue, acceptée, payée…).

**Conséquences pour WarrantyPilot** 💡

- Dans le MVP : sur 60 factures, **10 en Factur-X**. L'agent lit directement les données XML (pas de lecture IA, donc pas d'erreur de lecture) et l'affiche : « Données structurées : fiabilité maximale ».
- Les UBL et CII purs viendront après le MVP (même logique, sans PDF).
- Après le MVP : se brancher sur la **plateforme agréée du client** pour recevoir toutes les factures d'achat de matériel automatiquement. C'est notre « pourquoi maintenant ».
- 🔶 Les plateformes agréées ouvrent-elles une API aux logiciels tiers comme le nôtre ? Ça dépend de chaque plateforme, c'est à vérifier.

### 2.4 Gmail : les permissions et leurs contraintes ✅

| Permission | Classement Google | Ce qu'elle permet |
|---|---|---|
| `gmail.send` | **Sensible** | Envoyer seulement |
| `gmail.readonly` | **Restreinte** | Lire tous les e-mails |
| `gmail.metadata` | Restreinte | Lire les en-têtes, pas le contenu |
| `gmail.compose`, `gmail.modify`, `mail.google.com` | Restreintes | Brouillons, modification, suppression |

**Les règles de Google** ✅

- **Application en test** : aucune vérification n'est nécessaire, mais il y a un écran « application non validée », 100 utilisateurs maximum, et **l'autorisation expire au bout de 7 jours**.
- **Application publique** avec une permission **sensible** : vérification par Google.
- **Application publique** avec une permission **restreinte**, si les données passent par **notre serveur** : vérification **plus** une **évaluation de sécurité annuelle** (CASA) par un évaluateur agréé. Ça prend **plusieurs semaines** et se refait chaque année.

**MVP** 💡

- Un compte Gmail de test dédié, en mode test.
- Seulement deux permissions : `gmail.readonly` et `gmail.send`. **Jamais** `modify` ni `mail.google.com`.
- L'agent lit seulement le **libellé** « Factures » et le libellé « Pannes ». C'est un filtre dans notre code : la permission Google, elle, donne accès à toute la boîte.
- Le « Contrôle avant démo » vérifie la date d'expiration de l'autorisation ; on se reconnecte la veille de chaque démo.

**Production (après le MVP)** 💡, pour éviter l'évaluation de sécurité annuelle :

1. **Adresse de transfert** : le client transfère ou met en copie ses factures vers `factures@<client>.warrantypilot.app`. Aucune permission Gmail n'est nécessaire.
2. **Plateforme agréée** pour les factures électroniques (2.3).
3. **Envoi depuis notre propre domaine**, avec « répondre à » = le client. Plus besoin de `gmail.send`.
4. On ne garde l'accès direct à la boîte (restreint) que si un client le demande, et on prévoit alors l'évaluation de sécurité.

🔶 Microsoft 365 (Outlook) a des règles différentes, à étudier si les clients sont surtout sur Outlook.

---

## 3. Marché et modèle économique (rappel de la V3, inchangé)

- 🔶 **Segment de départ** : centres de service client (casques, PC). **Vision** : toutes les entreprises.
- 🔶 **Sponsor probable** : le DAF, parce que le produit parle d'économies prouvées.
- 🧑 **Modèle économique** : scan gratuit + abonnement par équipement. 🔶 Le prix sera fixé après les entretiens.
- ✅ **Concurrence** : ScalePad suit les garanties pour les infogérants sans faire les demandes ; il existe aussi des agents de demande de garantie, côté revendeurs et fabricants.
- 🔶 **Notre différence** : côté propriétaire, jusqu'à la résolution, des décisions vérifiables, multi-canal, et la prévention à l'achat.
- ❌ **Aucune preuve client** pour l'instant → 10 entretiens et des scans gratuits réels, en parallèle du développement.

---

## 4. Périmètre du MVP : 4 niveaux de priorité

**Règle d'or :** on ne commence un niveau que si le niveau précédent passe sa porte de passage. Chaque fonction des niveaux 1 à 3 a un **bouton marche/arrêt**, ce qui permet de l'éteindre le jour J sans rien casser.

### P0 — Indispensable : le parcours principal irréprochable
| Fonction | Pourquoi c'est indispensable |
|---|---|
| Jeu de données Appelia (≈ 230 équipements, 60 factures annotées dont 10 Factur-X, 15 pièges) | Sans données fiables, rien n'est mesurable |
| Lecture des factures (glisser-déposer) + contrôles du code | Base de toutes les décisions |
| Moteur de règles multi-droits, avec trace et 40 cas de référence | Fiabilité |
| Chat de signalement (mention IA) | Point de départ de la démo |
| Validation humaine + politique d'envoi à 6 conditions | Confiance |
| **Jabra** : vrai e-mail au revendeur (adresse de test) | Une action réelle |
| **Dell** : reproduction locale remplie par l'agent (H Company, Browser Use en secours) | Le « waouh » |
| Statuts honnêtes + reprise après coupure + bouton « Pause de l'agent » | Jamais de faux « Envoyée » |
| Journal en ajout seul + vérification d'intégrité | Preuve |
| Procédure « données du PC » avant l'envoi Dell | Sécurité réelle |
| Remise à zéro + Contrôle avant démo | Répétable 10 fois sur 10 |

**Porte P0** : le parcours Jabra + Dell passe **10 fois sur 10** après remise à zéro, avec **0** « Couvert » à tort.

### P1 — Secondaire : complète la démo de 3 minutes
Scan (3 chiffres + « expire bientôt » + rapport) · lecture de la boîte Gmail de test · **garde-fou achat** · suivi (réponse du revendeur, numéro de retour, statut Dell, relances) · FR/EN.
**Porte P1** : la démo de 3 minutes complète passe 10 fois sur 10.

### P2 — Bonus : enrichissent les questions-réponses
Signalement par e-mail · vocal (Gladia) · matériel de prêt · alerte « pannes en série » · Warranty+ (canal support Jabra) en démo.
**Porte P2** : chaque bonus passe 5 fois sur 5, sans dégrader P0 ni P1.

### P3 — Optionnel : seulement s'il reste du temps
Reproduction HP · API de test Dell (si tu as un compte TechDirect) · photo de l'étiquette.

**Règle de coupe** 💡 : si la semaine 4 arrive et que P1 n'est pas prêt, on coupe d'abord P3, puis P2. On ne touche jamais à P0, et on ne réduit jamais la qualité de P0 pour finir P1.

---

## 5. Réel, reproduction ou simulé : toute la démo, étape par étape

| Temps | Étape | Statut | Ce qui est vraiment réel | Ce qui ne l'est pas |
|---|---|---|---|---|
| 0:00 | Présentation d'Appelia | **Données fictives** | — | L'entreprise, les employés et les factures sont inventés |
| 0:15 | Lancement du scan des 60 factures | **RÉEL** | La lecture IA, la lecture Factur-X, le moteur de règles, les calculs | Les factures sont fictives |
| 0:25 | Panne Jabra dans le chat | **RÉEL** | Le chat IA, l'identification, le verdict et ses preuves | — |
| 0:45 | E-mail au revendeur | **RÉEL** | Un vrai e-mail part par Gmail, avec la facture jointe | Le destinataire est **notre** adresse de test, pas un vrai revendeur |
| 1:00 | PC Dell : validation + procédure données | **RÉEL** | La politique d'envoi, la liste de contrôle bloquante | — |
| 1:15 | L'agent remplit le site Dell | **REPRODUCTION** | Le vrai H Company pilote un vrai navigateur, en direct | Le site est une **copie locale** de Dell, avec les vrais logos ; le numéro de dossier est généré par la copie |
| 1:50 | Garde-fou achat | **RÉEL** | La détection, le verdict, la demande de validation | — |
| 2:15 | Résultats du scan | **RÉEL** | Les 3 chiffres sont calculés | « Économies réelles » = 0 € au début de la démo (honnête) |
| 2:30 | (Si on a le temps) Réponse du revendeur | **RÉEL** | L'agent lit une vraie réponse dans la boîte de test | La réponse est écrite **par nous**, qui jouons le revendeur |
| — | Bouton « avancer le temps » (relance après 7 jours) | **SIMULÉ** | — | L'horloge est accélérée |
| — | Dossier « Résolu » + économie réelle | **RÉEL dans l'app** | Le calcul et la preuve sont réels | L'e-mail de confirmation vient de notre adresse de test |

À l'écran, chaque étape porte son badge : **RÉEL** (vert), **REPRODUCTION** (orange), **SIMULÉ** (gris). À l'oral, on dit : « Ce site est une reproduction locale du site Dell ; en production, on passera par l'API officielle de Dell. »

---

## 6. Workflows modifiés

### 6.1 Panne (inchangé, rappel)
Signalement → identification → preuve d'achat → moteur de règles → politique d'envoi → action par le bon canal (avec preuve d'exécution) → suivi → résolution.

### 6.2 Garde-fou achat : trois niveaux bien séparés

| Niveau | Ce qui se passe | Ce que l'app affiche | Compté dans… |
|---|---|---|---|
| **1. Recommandation** | Une demande d'achat arrive. L'agent trouve l'équipement actuel → `Couvert` ou `Probablement couvert` | « Cet équipement est probablement encore sous garantie. Nous recommandons de ne pas racheter. » | Rien encore |
| **2. Demande de validation** | Le responsable choisit : **« Lancer la garantie et suspendre l'achat »** ou **« Acheter quand même »** (avec un motif obligatoire) | Une décision horodatée, inscrite au journal | **Économies possibles** (seulement si l'achat est suspendu) |
| **3. Économie réalisée** | Les **deux** preuves existent : l'achat est **annulé**, ce qui est confirmé par le responsable, **et** le dossier de garantie est **Résolu** (preuve de réparation ou de remplacement) | « 120 € économisés : achat annulé le…, remplacement reçu le… » | **Économies réelles** |

Règles :

- **Jamais de blocage automatique d'un achat** : l'agent recommande, l'humain décide.
- Si on achète quand même → aucune économie n'est comptée, et le motif est gardé.
- Si la garantie est refusée → l'économie possible est annulée, et l'achat peut reprendre.
- Verdict `À vérifier` → pas de recommandation, juste une information.

### 6.3 Avant d'envoyer un ordinateur en réparation : la procédure « données »

Le code **bloque** l'action « envoyer le PC » tant que la liste n'est pas validée par un **humain identifié**. L'agent ne peut pas cocher les cases à sa place.

| # | Étape | Qui |
|---|---|---|
| 1 | **Type de réparation** : intervention sur place, envoi de pièce ou envoi de l'appareil ? Si l'appareil ne quitte pas l'entreprise, la procédure est allégée | Agent (lu dans le dossier) |
| 2 | **Sauvegarde** des données de l'utilisateur, faite et **vérifiée** (date de la dernière sauvegarde réussie) | Humain |
| 3 | **Chiffrement du disque activé** (par exemple BitLocker), avec la clé de récupération mise en lieu sûr **hors de l'appareil** | Humain |
| 4 | **Disque** : si le contrat Dell inclut « *Keep Your Hard Drive* » ✅ (le client garde le disque défectueux ; c'est inclus dans ProSupport Plus ✅, mais impossible sur un disque soudé ✅) → on le garde. Sinon, et si l'appareil ne doit pas revenir (remplacement), effacement sécurisé selon une méthode reconnue (NIST SP 800-88) | Humain, guidé par l'agent |
| 5 | **Comptes** : déconnecter les sessions et retirer les mots de passe enregistrés ; si l'appareil est remplacé, le retirer de la gestion à distance (MDM) | Humain |
| 6 | **Étiquetage** : numéro de dossier, numéro de série, date d'envoi, transporteur | Agent |
| 7 | **Retour** : à la réception, vérifier l'appareil avant de le rendre à l'utilisateur | Humain, avec un rappel de l'agent |

Chaque étape est enregistrée au journal (qui, quand). Dans la démo, on montre la liste de contrôle remplie en 10 secondes.

---

## 7. Journal : ajout seul et vérification d'intégrité

« Ineffaçable » était une promesse trop forte : quelqu'un qui contrôle entièrement la machine peut tout modifier. Voici une stratégie honnête et vérifiable 💡 :

1. **Ajout seul** : une table `evenements` (numéro, heure, auteur, type, contenu, empreinte précédente, empreinte). Des règles dans la base **refusent toute modification et toute suppression**.
2. **Les corrections sont de nouveaux événements** : on n'efface jamais. Une correction de date, par exemple, = un événement « correction » qui pointe vers l'événement d'origine.
3. **Chaîne d'empreintes** : chaque événement contient l'empreinte (SHA-256) de l'événement précédent **et** de son propre contenu. Modifier un seul ancien événement casse toute la suite.
4. **Ancrages extérieurs** : à la fin de chaque dossier et chaque jour, la dernière empreinte est signée avec une clé secrète conservée **hors de la base**, puis copiée dans un fichier séparé. Elle est aussi imprimée dans le rapport PDF du dossier.
5. **Vérification** : un bouton « Vérifier le journal » recalcule toute la chaîne et la compare aux ancrages. Le résultat est soit « Journal intègre ✓ », soit « Modification détectée à l'événement n° X ». Ce test fait partie du Contrôle avant démo.
6. **Pas de secrets ni de données inutiles** dans le journal (clés masquées).
7. **Limite assumée** : ça **détecte** une modification, ça ne l'**empêche** pas physiquement. Pour un vrai produit, on enverra les ancrages vers un stockage externe en écriture seule 🔶.

Démo de réserve : on modifie un événement à la main dans la base, puis « Vérifier le journal » affiche immédiatement l'alerte.

---

## 8. Sécurité (rappel de la V3 + ajouts)

- Documents, e-mails, pages web et sorties de l'IA = **données non fiables**, jamais des ordres. Le texte caché est détecté.
- L'agent du navigateur ne reçoit que des **consignes fabriquées par notre code** à partir de champs vérifiés.
- **Listes blanches dans le code** : les adresses e-mail autorisées, et les sites autorisés (localhost uniquement).
- **Secrets** dans `.env`, jamais journalisés ni transmis à l'agent. Faux identifiants sur la reproduction.
- **Plafond** de sessions H Company par jour, et bouton **« Pause de l'agent »**.
- **Idempotence** : chaque action porte une clé unique, donc une reprise après coupure ne renvoie jamais deux fois le même e-mail.
- **Gmail** : 2 permissions seulement, avec un filtre par libellé dans le code (2.4).
- **Procédure données** obligatoire avant l'envoi d'un PC (6.3).
- **Journal vérifiable** (7).

---

## 9. Organisation du développement à plusieurs agents 🧑

### 9.1 Les rôles
| Rôle | Qui | Responsabilités |
|---|---|---|
| **Chef de projet / intégrateur** | Moi (session principale) | Les contrats, les modèles de données, le noyau commun, les fichiers partagés, la relecture et l'intégration de chaque lot, les portes de passage, et ce que je te rapporte |
| **Agents de lot** | Sessions Devin enfants, **une par lot** | Un seul dossier du code chacun ; leurs propres tests ; ils ne modifient **jamais** les fichiers d'un autre lot ni les contrats |

Au maximum **4 agents en même temps**. Au-delà, l'intégration devient le goulot d'étranglement.

### 9.2 Les lots et leurs dossiers (aucun chevauchement)
| Lot | Dossier | Dépend de | Agent |
|---|---|---|---|
| L0 Noyau : modèles, statuts, orchestrateur, journal, contrats | `backend/app/core`, `backend/app/contracts` | — | **Moi seul** |
| L1 Jeu de données Appelia | `data/appelia` | Contrats | Agent A |
| L2 Lecture des documents + contrôles + Factur-X | `backend/app/ingestion` | Contrats | Agent B |
| L3 Moteur de règles + règles YAML + cas de référence | `backend/app/rules` | Contrats | Agent C |
| L4a Reproduction du site Dell | `repro/dell` (application séparée) | Rien | Agent D |
| L5 Interface (d'abord avec de fausses données) | `frontend/` | Contrat d'API | Agent E (2e vague si besoin) |
| L4b Pilotage du navigateur (H Company / Browser Use) | `backend/app/actions/browser` | L0, L4a | Agent D |
| L6 E-mail : Gmail en lecture et envoi, suivi des réponses | `backend/app/actions/email` | L0 | Agent B (après L2) |
| L7 Garde-fou achat + suivi + relances | `backend/app/purchase_guard`, `backend/app/followup` | L0, L3 | Agent C (après L3) |
| L8 Bonus (vocal, prêt, pannes en série) | `backend/app/bonus/*` | L0 | Agent A (après L1) |

### 9.3 Les contrats (définis avant tout travail parallèle)

- **Les modèles de données** sont écrits une seule fois, en Python (Pydantic), dans `backend/app/contracts`. C'est l'unique source de vérité.
- **L'API** est décrite automatiquement à partir de ces modèles (fichier OpenAPI). Les types de l'interface en sont **générés** automatiquement, jamais réécrits à la main.
- **Les interfaces entre modules** (chaque lot implémente la sienne) :
  - Lecture : `extraire(document) → liste de Faits` (chaque fait avec sa provenance et sa confiance)
  - Règles : `evaluer(equipement, faits, incident, regles) → Verdict` (avec la trace)
  - Action : `executer(action) → ResultatAction` (avec une clé unique et une preuve d'exécution)
  - Suivi : `verifier(dossier) → liste d'Événements`
- **Le catalogue des événements** (tous les types possibles du journal) est fixé dans les contrats.
- **Un changement de contrat** se fait uniquement par moi. L'agent qui en a besoin me le demande ; je modifie, je préviens tous les lots, et chacun s'adapte.

**Modèles de données principaux** : `Equipement`, `Personne`, `Document`, `Fait`, `Droit`, `Regle`, `Incident`, `DemandeAchat`, `Dossier`, `Verdict`, `Action`, `ResultatAction`, `ChecklistDonnees`, `Evenement`, `Reglage`.

### 9.4 Les branches Git
| Branche | Rôle | Qui y écrit |
|---|---|---|
| `main` | Toujours présentable (uniquement après une porte de passage réussie) | Moi seul, avec ton accord |
| `integration` | Assemblage de tous les lots | Moi seul (fusion après relecture) |
| `devin/<horodatage>-lot-<nom>` | Une branche par lot | L'agent du lot |

- Des demandes de fusion **petites et fréquentes** (au moins une par jour et par lot) vers `integration`.
- Chaque agent remet sa branche à jour depuis `integration` chaque matin.
- **Les fichiers partagés** (dépendances, migrations de base, configuration, contrats) n'appartiennent qu'à moi. Un agent qui a besoin d'une nouvelle bibliothèque me la demande.
- **Les traductions** FR/EN : un fichier par lot, donc personne ne touche le même fichier.
- Rien n'est poussé sur GitHub sans ton accord (ta règle habituelle).

### 9.5 Les tests entre modules
| Niveau | Quoi | Qui | Quand |
|---|---|---|---|
| Tests du lot | Chaque fonction du lot | L'agent du lot | À chaque modification |
| Tests de contrat | Le lot respecte exactement les modèles et les interfaces (avec de faux modules à la place des autres) | L'agent, avec des faux modules que je fournis | À chaque demande de fusion |
| Tests d'intégration | Un dossier complet traverse tous les vrais modules, avec de faux adaptateurs (pas de vrai Gmail ni de vrai H Company) | Moi | À chaque fusion dans `integration` |
| Tests de bout en bout | Le scénario de démo, avec les vrais adaptateurs (Gmail de test, H Company, reproduction) | Moi | À chaque porte de passage |
| Vérifications automatiques | Style du code, types, tests du lot et de contrat | Automatique | À chaque demande de fusion ; une fusion est impossible si c'est rouge |

### 9.6 Ce qu'on ne parallélise pas

- Le noyau et les contrats (semaine 1, moi seul).
- Les tests techniques H Company, Gmail et OCR (jours 1–2, moi seul).
- Toute tâche qui touche deux lots à la fois : je la fais moi-même, ou je la découpe.

### 9.7 Coût 🔶
Plusieurs agents en parallèle consomment plus de crédits Devin, mais font gagner du temps calendaire. Je te donnerai une estimation avant de lancer chaque vague.

---

## 10. Roadmap (≈ 6 semaines)

| Étape | Contenu | Agents | Porte de passage |
|---|---|---|---|
| **Jours 1–2** | Tests techniques : H Company sur une page locale, Mistral OCR, Gmail (permissions, expiration) | Moi | H Company **5/5**, sinon Browser Use ; OCR utilisable ; Gmail connecté |
| **Semaine 1** | **L0** : contrats, modèles, orchestrateur, journal avec chaîne d'empreintes, squelette de l'interface | Moi | Un faux dossier traverse tous les statuts ; « Vérifier le journal » fonctionne |
| **Semaine 2** | **Vague 1** : L1 données · L2 lecture · L3 règles · L4a reproduction Dell | 4 agents | Chaque lot passe ses tests et ses tests de contrat |
| **Semaine 3** | **Vague 2** : L4b navigateur · L6 e-mail · L5 interface · procédure données · intégration P0 | 3–4 agents | **Porte P0** : Jabra + Dell **10/10** = version présentable |
| **Semaine 4** | **Vague 3** : L7 garde-fou + suivi · scan · FR/EN (P1) | 2–3 agents | **Porte P1** : démo de 3 min **10/10** |
| **Semaine 5** | **Vague 4** : L8 bonus (P2), puis P3 s'il reste du temps | 1–2 agents | **Porte P2** : chaque bonus 5/5, sans régression |
| **Semaine 6** | Gel du code, finitions, vidéo de secours, répétitions, pitch | Moi | **10 répétitions réussies d'affilée** |
| **En parallèle** | 10 entretiens + scans gratuits réels | Toi | Citations et chiffres réels |

---

## 11. Critères d'acceptation

| Critère | Mesure |
|---|---|
| Parcours principal (P0) | Jabra + Dell 10 passages d'affilée après remise à zéro |
| Démo complète (P1) | 3 min, 10 passages d'affilée |
| Lecture des factures | ≥ 95 % de champs critiques justes sur 50 PDF ; 100 % sur les 10 Factur-X |
| Aucune garantie inventée | 15 pièges + 40 cas de référence : **0** « Couvert » à tort |
| Jabra | Le cas Warranty+ part bien vers le support Jabra ; le délai de 30 jours ne bloque jamais ; le consommable usé est « Non couvert » |
| Garde-fou achat | 10 cas : 0 recommandation à tort ; « économie réalisée » **seulement** avec les 2 preuves |
| Procédure données | Impossible d'envoyer un PC sans la liste validée par un humain (testé) |
| Journal | Un événement modifié à la main est détecté ; modification et suppression sont refusées par la base |
| Aucun faux « Envoyée » | Une coupure du navigateur donne « Échec » ; une reprise ne renvoie jamais deux fois le même e-mail |
| Listes blanches | Un envoi vers une adresse non autorisée est refusé ; une navigation hors localhost est refusée |
| Gmail | Seulement 2 permissions demandées ; expiration détectée par le Contrôle avant démo |
| Transparence IA | Mention dans le chat ; phrase et en-tête dans les e-mails |
| Rapidité | Site Dell rempli en moins de 90 s (médiane) ; scan de 60 factures en moins de 2 min |
| FR / EN | Aucun texte non traduit |

---

## 12. Les skills : inventaire et contribution

Installés dans `~/.config/devin/skills/`, tous vérifiés : texte uniquement, aucun programme exécutable, licence MIT.

| Skill | Source | Ce qu'il a apporté à la conception |
|---|---|---|
| grill-me | Matt Pocock | Les 13 questions de la V1 |
| grilling | Matt Pocock | Les questions V3, une par une, avec une recommandation argumentée |
| grill-with-docs | Matt Pocock | Les questions confrontées aux documents existants (PLAN_V2, revue externe) |
| domain-modeling | Matt Pocock | Le glossaire (Équipement, Fait, Droit, Règle, Dossier…) et les modèles de données de la section 9.3 |
| research | Matt Pocock | La méthode : sources primaires, résultats écrits dans un fichier (`NOTES_ANALYSE_V3.md`) |
| product-discovery | magnus919 | La séparation utilisateur / acheteur / payeur / sponsor ; « un compliment n'est pas une preuve » ; les entretiens sur des faits passés |
| product-shaping | magnus919 | Les 4 niveaux de priorité, les portes de passage, la règle de coupe |
| secure-software-engineering | magnus919 | Ce qu'on protège, les frontières de confiance, des contrôles dans le code (pas dans les consignes), les documents non fiables, le journal vérifiable |
| setup-matt-pocock-skills | Matt Pocock | Pas encore utilisé : il sert à préparer le dépôt de code au début du développement |

**Aucun nouveau skill installé.** Les besoins restants sont déjà couverts :

- l'organisation de plusieurs agents est couverte par les outils intégrés à Devin (sessions enfants, workflows) ;
- la sécurité est couverte par secure-software-engineering.

Installer davantage de skills ajouterait des doublons.

---

## 13. Risques résiduels

| Risque | Gravité | Réponse | Reste après la réponse |
|---|---|---|---|
| H Company ne pilote pas bien la reproduction | Haute | Test aux jours 1–2, Browser Use en secours | Faible |
| L'intégration de plusieurs agents dérape | Haute | Contrats d'abord, dossiers séparés, fusions quotidiennes, 4 agents max | Moyen |
| P1 en retard | Moyenne | Règle de coupe (P3, puis P2) | Faible |
| L'autorisation Gmail expire le jour J | Moyenne | Contrôle avant démo + reconnexion la veille | Faible |
| Logos (droit des marques) 🧑 | Moyenne | Local uniquement, pas de publication, annonce orale | **Moyen, assumé** |
| AI Act 50(2) mal interprété | Faible (MVP) | En-tête technique + avis d'un juriste avant un vrai produit | Faible |
| Évaluation de sécurité Gmail en production | Moyenne (après le MVP) | Adresse de transfert + plateforme agréée + envoi depuis notre domaine | Faible |
| Aucune preuve client | **Haute** pour les investisseurs | Entretiens + scans gratuits | **Élevé tant qu'aucun entretien n'est fait** |
| ScalePad ajoute les demandes de garantie | Moyenne | Cible : entreprises sans infogérant + exécution | Moyen |
| Coût en crédits Devin de plusieurs agents | Moyenne | Estimation avant chaque vague | Moyen |

---

## 14. Décisions finales

### 14.1 Tes décisions (toutes les versions)
Public : investisseurs, incubateurs et hackathons · Vision : toutes les entreprises, en commençant par les centres de service client · Scénario Appelia · Copies locales des sites avec les vrais logos, vidéo comprise · Pas de vérification sur un vrai site · H Company (Browser Use en secours) · Factures : boîte de test + glisser-déposer · Signalement : chat + e-mail, vocal en bonus · Automatique sous un seuil réglable + 6 conditions · Scan gratuit + abonnement par équipement · FR/EN · Date : 1 mois ou plus · Direct + vidéo de secours · Application pour une entreprise · Tout le périmètre, développé par plusieurs agents · Tout doit vraiment fonctionner · Garde-fou achat dans la démo, facture piégée en réserve.

### 14.2 Mes décisions techniques (contestables)
FastAPI + React + SQLite · un seul agent dans le produit · règles en YAML versionnées · contrats Pydantic + types générés · journal à chaîne d'empreintes · 2 permissions Gmail · 4 niveaux de priorité · 4 agents de développement maximum en même temps.

### 14.3 Encore ouvert (sans urgence)
L'IA principale (au jour 1, selon tes clés) · un compte Dell TechDirect (optionnel) · le prix de l'abonnement (après les entretiens) · l'avis d'un juriste sur l'AI Act 50(2) et les logos (avant toute publication).

---

## Annexe — Sources officielles

- Jabra, garantie business : jabra.com/supportpages/warranty-terms-business
- Jabra Warranty+, conditions du 16/06/2025 : jabra.com/footerpages/business-services-terms (PDF « Jabra Warranty+ Service descriptions and terms and conditions »)
- AI Act, article 50 : ai-act-service-desk.ec.europa.eu/en/ai-act/article-50 ; FAQ de la Commission : digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act ; lignes directrices de la Commission sur l'article 50 (JO C/2026/6005, eur-lex.europa.eu)
- Facture électronique : impots.gouv.fr/facturation-electronique-et-plateformes-agreees ; entreprendre.service-public.gouv.fr/actualites/A18953
- Gmail, permissions : developers.google.com/workspace/gmail/api/auth/scopes ; vérification des permissions restreintes : developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification ; évaluation de sécurité : support.google.com/cloud/answer/13465431 ; applications non validées : support.google.com/cloud/answer/7454865 ; mode test et 7 jours : support.google.com/cloud/answer/15549945
- Dell Keep Your Hard Drive : i.dell.com (PDF services-keep-your-hard-drive) ; description ProSupport Plus (Dell)
- Effacement des supports : NIST SP 800-88 (Guidelines for Media Sanitization)
- Dell Acceptable Use Policy : dell.com/en-us/legal/lp/acceptable-use-policy
- Sources V2/V3 : ScalePad, Lenovo eSupport API, HP/Poly, Dell TechDirect, H Company, Lansweeper, Lapsewise, ReclaimDesk, OWASP
