# Pitch

Chiffres : jeu de données fictif Appelia (`data/appelia/README.md`), valeurs mesurées par `POST /api/scan`. Ne pas les présenter comme des résultats clients.

## 60 secondes — FR

Dans une entreprise, quand un casque ou un PC tombe en panne, on en rachète souvent un neuf. Pourtant il est encore sous garantie : la facture est perdue, le portail du fabricant est pénible, et personne n'a le temps.

WarrantyPilot transforme une panne en demande de garantie prouvée. L'employé écrit « mon casque ne marche plus ». L'agent identifie l'équipement, retrouve la facture, applique des règles déterministes, et envoie la demande par le bon canal : e-mail au revendeur, portail du fabricant, ou humain. Sous un seuil et sans doute, il agit seul ; au-dessus, un responsable valide. Chaque personne se connecte, chaque geste est signé dans un journal vérifiable. Puis l'agent suit le dossier jusqu'à sa résolution.

Et il prévient les achats inutiles : un casque neuf à 120 € est suspendu, et l'économie n'est comptée que quand l'achat est annulé et la garantie résolue.

Sur notre entreprise fictive : 14 064 € de matériel couvert retrouvés. WarrantyPilot : la garantie, enfin utilisée.

## 60 seconds — EN

When a headset or laptop breaks at work, companies often just buy a new one — even though it is still under warranty. The invoice is lost, the manufacturer portal is painful, and nobody has time.

WarrantyPilot turns a failure into a proven warranty claim. An employee types "my headset stopped working". The agent identifies the device, finds the invoice, applies deterministic rules, and sends the claim through the right channel: reseller email, manufacturer portal, or a human. Below a threshold and with no doubt, it acts alone; above it, a manager approves. Every person signs in and every action is signed in a verifiable log. Then the agent follows the claim until it is resolved.

It also prevents useless purchases: a new €120 headset is put on hold, and the saving only counts once the purchase is cancelled and the claim resolved.

On our fictitious company: €14,064 of covered equipment found. WarrantyPilot: warranties, actually used.

## 3 minutes — FR

**Le problème (30 s).** Les entreprises paient des garanties qu'elles n'utilisent pas. Un casque de centre d'appels qui lâche, un PC qui ne démarre plus : on rachète. Pourquoi ? Retrouver la facture, savoir si c'est couvert, remplir le bon formulaire chez le bon fabricant, puis relancer : c'est long, et personne n'en est responsable.

**La solution (60 s).** WarrantyPilot est un agent qui part de la panne et va jusqu'à la résolution. L'employé signale dans un chat, qui annonce clairement être assisté par une IA. L'agent identifie l'équipement et retrouve la preuve d'achat ; les factures électroniques Factur-X sont lues directement dans leurs données XML, sans interprétation. Puis la décision n'est pas laissée au modèle : un moteur de règles déterministe et versionné dit « couvert », « à vérifier » ou « non couvert », avec la trace de chaque contrôle. L'envoi suit une politique stricte : sous 300 €, couvert, sans ambiguïté ni exclusion, l'agent envoie seul ; sinon un humain valide. Pour un PC, une procédure en sept étapes protège les données avant tout envoi.

**La démo (40 s).** Vous avez vu Paul se connecter et signaler son casque Jabra : un e-mail au revendeur parti seul, avec la facture. Le PC Dell de Clément : Karim, administrateur, complète la procédure, valide, et l'agent remplit le portail, obtient un numéro de dossier et capture chaque étape ; quand le portail clôt le dossier, WarrantyPilot le relève seul et le passe en résolu. Le casque, lui, est déclaré résolu par un humain, avec une note. Soyons transparents : l'e-mail part vers un serveur local, le portail Dell est une reproduction locale, et c'est nous qui faisons avancer ce portail. Aucune demande réelle n'a été faite avec des données fictives.

**Pourquoi maintenant (20 s).** Depuis septembre 2026, toutes les entreprises françaises reçoivent leurs factures en format électronique. Les preuves d'achat deviennent structurées : c'est le bon moment pour les exploiter.

**Marché et modèle (20 s).** On commence par les centres de service client, avec un sponsor naturel : le DAF. Modèle envisagé : scan gratuit, puis abonnement par équipement — le prix reste à valider en entretiens. Face aux outils qui suivent les garanties sans les réclamer, nous allons jusqu'à la résolution, côté propriétaire, et nous prévenons les achats inutiles.

**Conclusion (10 s).** 14 064 € de matériel couvert retrouvés sur notre entreprise fictive, 120 € économisés et prouvés. WarrantyPilot : la garantie, enfin utilisée.

## 3 minutes — EN

**The problem (30 s).** Companies pay for warranties they never use. A call-centre headset dies, a laptop won't boot: they buy new. Why? Finding the invoice, checking coverage, filling the right form for the right manufacturer, then chasing it up takes time, and nobody owns it.

**The solution (60 s).** WarrantyPilot is an agent that goes from failure to resolution. The employee reports in a chat that clearly states it is AI-assisted. The agent identifies the device and finds the proof of purchase; Factur-X e-invoices are read straight from their embedded XML, with no guesswork. The decision is not left to the model: a deterministic, versioned rules engine says "covered", "to verify" or "not covered", with a trace of every check. Sending follows a strict policy: under €300, covered, unambiguous, no exclusion — the agent sends alone; otherwise a human approves. For a laptop, a seven-step procedure protects data before anything is shipped.

**The demo (40 s).** You saw Paul sign in and report his Jabra headset: a reseller email sent automatically with the invoice. Clément's Dell laptop: Karim, the admin, completes the procedure, approves, and the agent fills the portal, gets a case number and screenshots every step; when the portal closes the case, WarrantyPilot picks it up by itself and marks it resolved. The headset is marked resolved by a human, with a note. To be transparent: the email goes to a local server, the Dell portal is a local reproduction, and we move that portal forward ourselves. No real claim was made with fictitious data.

**Why now (20 s).** Since September 2026, every French company receives its invoices electronically. Proofs of purchase are becoming structured data — the right moment to use them.

**Market and model (20 s).** We start with customer-service centres, with a natural sponsor: the CFO. Planned model: free scan, then a per-device subscription — pricing still to be validated in interviews. Unlike tools that track warranties without claiming them, we go all the way to resolution, on the owner's side, and we prevent useless purchases.

**Close (10 s).** €14,064 of covered equipment found in our fictitious company, €120 saved and proven. WarrantyPilot: warranties, actually used.
