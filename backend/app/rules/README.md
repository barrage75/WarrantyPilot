# Moteur déterministe (lot L3)

`load_rules(DEFAULT_RULES_DIR)` charge les YAML par nom avec SafeLoader (ancres et
fusions résolues), valide chaque règle et interdit les identifiants dupliqués.
Le moteur n'utilise ni réseau ni horloge implicite : injecter une date ou une fonction.
La référence de démonstration est le 20/11/2026.

## Faits consommés

Seuls les faits globaux (`equipment_id=None`) ou attachés à l'équipement et de
confiance ≥ 0,5 sont consommés. Les dates acceptent `date`, ISO `YYYY-MM-DD` ou
`DD/MM/YYYY`, les entiers acceptent les chaînes numériques, les booléens acceptent
`bool` ou les chaînes `true`/`false`. Une date d'inventaire n'est jamais une preuve d'achat.

| Champs | Usage |
| --- | --- |
| `purchase_date`, `invoice_date` | Preuve d'achat ; facture utilisée en approximation si nécessaire |
| `delivery_date`, `ship_date` | Départ ; inventaire puis facture en repli, signalés en approximation |
| `warranty_term_months` | Durée standard lorsque la règle indique zéro mois |
| `extension_months` | Durée Warranty+ ou ProSupport |
| `warranty_plus_certificate` | Preuve de certificat Warranty+ |
| `service_contract` | Preuve de contrat ProSupport |
| `lease_contract` | Preuve de location prioritaire |
| `serial_number`, `brand`, `model_number` | Contrôle d'identité avec l'inventaire |
| `condition` | `refurbished` remplace la règle standard ; sinon `new` |
| `buyer_name` | Doit contenir le nom normalisé de la société configurée |
| `equipment_ambiguous`, `security.suspicious` | Blocage pour vérification humaine |
| `incident_category` | Exclusion certaine à 0,8 ; possible entre 0,5 et 0,8 |

Les noms de ces champs sont définis dans `FactField` (`app.contracts.enums`) et
partagés avec les extracteurs L2. Les champs propres aux factures (fournisseur,
numéro et lignes) restent dans l'espace de noms d'ingestion.

Les champs supplémentaires de `proof_required` produisent des avertissements et
des entrées `missing`. Les droits `lease_contract` et `extension` doivent être liés
à l'équipement ; leurs preuves sont ajoutées au verdict. La fin d'un droit
d'extension peut fournir sa durée. La fin calculée est inclusive.

## Classification

Sans fait de catégorie, le classificateur n'est utilisé que s'il est injecté.
Priorité stable : réparation par tiers, liquide, accident, usure, vol, perte, abus,
défaut. Casse et accents sont ignorés ; mots entiers, priorité au premier groupe.
Les formulations hésitantes abaissent la confiance à 0,6 (sinon 0,9 ; défaut sans
mot-clé à 0,5). `to_fact` rattache le fait à `incident_id` et utilise la source
`classifier`, jamais `llm`.
