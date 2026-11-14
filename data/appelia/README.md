# Jeu de données Appelia — lot L1

Ce jeu de données est entièrement synthétique et sert de vérité terrain aux lots
de lecture documentaire et de règles. Les quelque 200 personnes, 230 équipements,
revendeurs, factures et contrats sont fictifs. Les e-mails utilisent des domaines
`.example`, les SIRET ont volontairement des chiffres répétés et invalides, et
aucune donnée de client réel n'est incluse.

La date de référence est `2026-11-20`, dans `constants.py`. Tous les identifiants
sont stables et le générateur utilise une graine fixe. Régénérer depuis la racine
du dépôt avec :

```bash
uv run --project backend python data/appelia/generate.py
```

Avec l'environnement virtuel du backend activé, la commande équivalente est
`python data/appelia/generate.py`.

Le dossier `invoices/` contient 47 PDF ordinaires et 13 factures Factur-X au
profil EN16931. La facture 050 est une copie exacte Factur-X de la facture 001,
pour le scénario de doublon. Les XML CII embarqués contiennent
les numéros de série dans la description de ligne (`ram:Description`) : le modèle
CII conserve cette preuve avec le modèle et le SKU; les SKU figurent aussi dans
`ram:SellerAssignedID`.

`annotations.json` contient la vérité terrain et les pages des champs de chacune
des 60 factures. `traps.json` décrit 15 pièges, deux cas nominaux et un cas
supplémentaire dont la facture ne précise pas la durée de garantie.
Chaque piège fournit aussi `equipment`, `incident` et `facts` selon les contrats
Pydantic, afin que le moteur L3 puisse évaluer directement les cas. Le doublon
du piège 5 conserve un seul ensemble de faits.
Le piège 7 répète le numéro de la facture avec une date différente sur le bon de
livraison; `traps.json` conserve les deux faits `invoice_date` et leur provenance.
`documents/` contient le contrat de location, deux certificats Warranty+, le
contrat Dell ProSupport et le bon de livraison associé au piège 7.

L'opérateur informatique de démonstration est Karim Benali
(`responsable informatique`, `karim.benali.002@appelia.example`), dont l'identifiant
stable est `97225c38-d686-5d99-a6cf-53e18aa92e8d`.

### Rôles d'accès (lot SEC1)

La colonne `people.access_role` porte le rôle de connexion à l'interface, dérivé du
poste au reset (`app.core.auth.access_role_for_job`) :

| Personne | Poste (`role`) | Rôle d'accès (`access_role`) |
| --- | --- | --- |
| Karim Benali | `responsable informatique` | `admin` (réglages, reset, étiquette transporteur) |
| Paul (technicien) | `technicien plateau` | `operator` |
| Claire (DAF) | `DAF` | `operator` |
| Autres collaborateurs | `collaborateur` | aucun (pas de connexion) |

Connexion : `POST /api/auth/login` avec `{person_id, password}`. Le mot de passe de
démonstration vient de `WP_DEMO_PASSWORD` ; il est obligatoire hors `WP_ENV=dev`.
En développement uniquement, le défaut documenté est `appelia-demo`.

Le reset de démonstration règle `auto_send_threshold_eur` à 300 € pour montrer
l'envoi automatique du cas Paul. Le modèle `Settings` conserve son défaut prudent
de 0 €.

Les factures Dell indiquent la durée de garantie sur chaque ligne et
`annotations.json` la reprend dans `warranty_term_months`. Le cas de démonstration
`demo-dell-no-warranty-term` est l'exception sans durée probante : son verdict
attendu est `to_verify`. Les certificats Warranty+ indiquent `extension_months`;
les équipements reconditionnés portent `condition: "refurbished"`. Le Latitude
7440 de démonstration porte le Service Tag fictif `7XK4L93`, identique à celui de
la reproduction Dell locale.

Chargement des objets des contrats Pydantic, sans accès à une base :

```python
from data.appelia.load import load_dataset

dataset = load_dataset()
```

Le loader passe les treize factures Factur-X par le registre d'extracteurs et lit
localement le texte étiqueté des 47 autres factures PDF, sans OCR ni service externe.
Chaque fait conserve son extrait et sa page ; aucune durée absente du document
n'est inventée. Il expose aussi les faits et droits déduits des preuves de
location, Warranty+ et ProSupport. Le seed persiste ces faits ; un scan restaure
les faits manquants d'une base déjà initialisée, sans les dupliquer.

Le scan transmet au loader l'extracteur injecté pour les factures Factur-X,
comme auparavant. Les PDF ordinaires restent traités par l'extracteur de texte local :
le scan ne les envoyait pas au hook Mistral et ne déclenche pas de nouvel appel externe.
La progression est publiée après le traitement de chaque document dans le loader,
et non par une boucle vide après son retour. Elle mesure les documents traités ;
le statut ne devient `completed` qu'après la persistance et le calcul des totaux.

Les PDF sont produits avec des métadonnées à date fixe pour que la génération
soit reproductible. Les outils de génération (`reportlab` et `factur-x`) sont
uniquement des dépendances du groupe de développement.
