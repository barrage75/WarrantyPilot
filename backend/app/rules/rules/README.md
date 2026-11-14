# Règles de garantie (données, pas du code)

Rédigées par le lead à partir des sources officielles citées en tête de chaque fichier. Le moteur (lot L3) **lit** ces fichiers ; il ne les modifie pas. Toute modification passe par une PR du lead avec la source et la date.

## Sémantique (contrat pour le moteur)
- **Correspondance** : `brand` égal (insensible à la casse) ; `model_glob` au sens `fnmatch` (insensible à la casse). Un modèle **sans glob** (`Engage 55`) ne correspond qu'à ce nom exact : `Engage 55` ≠ `Engage 55 SE`. Si plusieurs règles du même `right_type` correspondent, la plus spécifique gagne (motif exact > glob ; puis le plus long préfixe littéral). `condition: refurbished` ne s'applique qu'aux équipements dont le fait `condition` vaut `refurbished` (et dans ce cas elle remplace la règle standard).
- **Durée** : `duration_days` (si présent) prime sur `duration_months`. `duration_months: 0` sans `duration_days` = durée **lue dans la preuve** (`warranty_term_months` pour une facture/contrat, `extension_months` pour un certificat) ; absente → `to_verify`.
- **Point de départ** : `purchase_date` | `delivery_date` | `ship_date` | `standard_warranty_end` (extensions). Si l'événement requis est inconnu, la date de facture sert d'approximation, signalée dans la trace ; si l'expiration calculée est à moins de 30 jours (ou dépassée de moins de 30 jours) → `likely_covered` au mieux.
- **Extensions** (`right_type: extension`) : n'existent que si la preuve correspondante existe (certificat Warranty+ si `requires_certificate`, contrat ProSupport). Elles prolongent la durée, jamais la couverture : mêmes exclusions.
- **Location** (`lease_contract`) : prioritaire sur tout le reste → `out_of_manufacturer`, canal `email_lessor`.
- **Délai de contact** : `contact_delay_days` avec `contact_delay_start: unspecified` → avertissement seulement, **jamais** bloquant.
- **Exclusions** (codes) : `accidental_damage`, `liquid_damage`, `third_party_repair`, `non_certified_accessory`, `consumable_wear`, `loss`, `theft`, `misuse`. Exclusion certaine → `not_covered` ; possible → `possible_exclusions` (pas d'envoi automatique).
- **Modèle sans règle** → `to_verify`. Jamais de durée par défaut.
