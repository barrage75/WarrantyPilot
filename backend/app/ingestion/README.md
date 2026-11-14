# Ingestion documentaire

- `fields.py` : noms canoniques des faits.
- `facturx.py` : extraction réelle du XML Factur-X embarqué, CII ou UBL ;
  analyse XML durcie, provenance structurée et recherche de signaux suspects.
- `mistral_client.py` et `pdf_llm.py` : OCR puis extraction JSON avec le SDK
  Mistral, séparation des instructions et des données non fiables, validation
  des citations ; les faits mal formés sont ignorés avec journalisation.
- `controls/` : plausibilité, dédoublonnage, signaux suspects et rapprochement
  avec l'inventaire, sans modifier les faits d'origine.

Le parsing Factur-X est réel. Les appels Mistral sont du code réel, mais leur
exécution distante reste non vérifiée sans `MISTRAL_API_KEY`. Les tests utilisent
des réponses enregistrées et un faux client ; le test `live` nécessite la clé.
Les factures et PDF de test sont entièrement fictifs (Appelia).

`SuspicionReport.suspicious` est destiné au paramètre `suspicious_signal` de
`app/core/policy.py`, qui empêche l'envoi automatique lorsqu'il est vrai.
Les extracteurs exposent les signaux via le fait `security.suspicious` ; le
passage à la politique reste à effectuer par l'appelant. Ces signaux sont des
heuristiques, pas une preuve de fraude. L'écart texte/OCR exige par défaut au
moins trois mots significatifs distincts manquants et 20 % des mots significatifs
distincts de la page ; ces deux seuils sont configurables.
