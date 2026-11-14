# Réception locale et documents non fiables

`POST /api/intake/poll` lit le Maildir `runtime/inbox` (variable
`WP_INTAKE_MAILDIR`), au même format que `LocalSmtpTransport`. Les sous-dossiers
comme `.sent` ne sont pas relevés. Aucun service externe n'est lancé.

Injecter `services={"intake": IntakeService(inbox, DocumentIntake(root), classifier)}`
dans `create_app`. `GmailTransport(token_provider, label_id)` de ce lot expose
uniquement la lecture, avec `gmail.readonly` ; il réemploie la pagination et le
filtrage du transport Gmail existant. Le consentement OAuth et le fournisseur
de jeton sont à fournir par l'appelant. La connexion distante reste non vérifiée
sans identifiants ; les tests injectent les réponses HTTP.

Les signalements exigent une adresse `From` unique connue dans `people`, dans le
domaine exact `appelia.example`. Les instructions suspectes bloquent le message,
y compris celles présentes uniquement dans une alternative HTML. Le classifieur
déterministe utilise des mots-clés ; son complément LLM est injectable, borné à
un type et désactivé sans `MISTRAL_API_KEY`. Aucun e-mail ne déclenche d'action
fabricant. Les heuristiques ne constituent pas une garantie de détection de
toute instruction malveillante.

Le pont `chat_bridge` réemploie intégralement `chat.send_message` et son
identification d'équipement, avec état privé et orchestrateur limité à la
préparation. Une session liée à la transaction externe contient son commit.
Un dossier ambigu conserve `equipment_id=None`, un verdict `to_verify` et les
questions du chat ; aucune réponse sortante n'est nécessaire. Tous les nouveaux
dossiers attendent une vérification humaine. Le premier événement de création
émis par chat conserve sa provenance `chat` ; l'incident et l'événement intake
suivant indiquent `email`. Extraire un service commun supprimera ce compromis.

Le reçu Message-ID et les dossiers/documents/faits sont atomiques dans la base
SQLite existante, dont `BEGIN IMMEDIATE` sérialise les écritures, même entre
processus. Une interruption avant commit autorise la reprise sans doublon.
Les messages sans identifiant unique sont ignorés et journalisés par empreinte.
`FOLLOWUP_RECEIVED(actor=intake)` sert de reçu en attendant des événements dédiés.
Un stockage différent de SQLite nécessitera une contrainte unique dédiée.

`POST /api/documents/upload` accepte un seul champ multipart `file`, PDF ou XML
UBL/CII de 10 Mio maximum, reconnu par son contenu. Le parseur MIME standard
borne aussi la taille totale du corps à 10 Mio + 64 Kio ; aucun ajout de
dépendance partagée n'est nécessaire. Les noms de chemins sont refusés avant
assainissement, les DTD sont interdites et les octets sont enregistrés sous une
empreinte SHA-256 dans `runtime/intake/documents` (`WP_INTAKE_DOCUMENTS`).

L'extraction passe par `ExtractorRegistry`, structurée pour Factur-X/UBL/CII,
avec confiance 1.0. La confiance décrit la méthode de lecture, pas l'authenticité
de la facture. Les PDF ordinaires sans clé et les extractions en échec restent
`pending_extraction` avec leurs octets conservés. Les signaux suspects donnent
`quarantined` et des faits `security.suspicious` ; ils ne passent jamais au LLM.
Le dédoublonnage reprend les contrôles existants (SHA-256, numéro + fournisseur).
Un rollback peut laisser un fichier adressé par empreinte sans ligne en base ;
il est réutilisé à la prochaine tentative et ne constitue pas un reçu.

Vérification : `uv run --project backend pytest backend/tests/integration/intake`.
