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

Le dossier `invoices/` contient 50 PDF ordinaires et 10 factures Factur-X au
profil EN16931. Le cinquantième PDF ordinaire est une seconde copie exacte de la
facture 001, pour le scénario de doublon. Les dix XML CII embarqués contiennent
les numéros de série dans la description de ligne (`ram:Description`) : le modèle
CII conserve cette preuve avec le modèle et le SKU; les SKU figurent aussi dans
`ram:SellerAssignedID`.

`annotations.json` contient la vérité terrain et les pages des champs de chacune
des 60 factures. `traps.json` décrit 15 pièges, deux cas nominaux et un cas
supplémentaire dont la facture ne précise pas la durée de garantie.
Chaque piège fournit aussi `equipment`, `incident` et `facts` selon les contrats
Pydantic, afin que le moteur L3 puisse évaluer directement les cas. Le doublon
du piège 5 conserve un seul ensemble de faits.
`documents/` contient le contrat de location, deux certificats Warranty+, le
contrat Dell ProSupport et le bon de livraison associé au piège 7.

Les factures Dell indiquent la durée de garantie sur chaque ligne et
`annotations.json` la reprend dans `warranty_term_months`. Le cas de démonstration
`demo-dell-no-warranty-term` est l'exception sans durée probante : son verdict
attendu est `to_verify`. Les certificats Warranty+ indiquent `extension_months`;
les équipements reconditionnés portent `condition: "refurbished"`.

Chargement des objets des contrats Pydantic, sans accès à une base :

```python
from data.appelia.load import load_dataset

dataset = load_dataset()
```

Les PDF sont produits avec des métadonnées à date fixe pour que la génération
soit reproductible. Les outils de génération (`reportlab` et `factur-x`) sont
uniquement des dépendances du groupe de développement.
