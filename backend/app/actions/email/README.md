# E-mail L6

SMTP local est une **reproduction** utilisant réellement SMTP et Maildir.
Gmail est **réel**, via REST stdlib. Depuis backend :

```sh
uv run python -m app.actions.email.local_smtp_server --port 2525 --maildir runtime/mail
```

Construire LocalSmtpTransport(port=2525, maildir_path="runtime/mail"), un
JsonlSentLedger("runtime/sent.jsonl"), puis build_email_adapters avec Settings
et l'expéditeur garanties@appelia.example. Le câblage orchestrateur reste à faire.
Destinataires et Cc doivent être autorisés et terminer par .example.

Gmail exige token_provider (ou refresh_token_provider), label_id, exactement
gmail.send et gmail.readonly. Aucun secret dans le dépôt. Test live :
WP_GMAIL_LIVE=1, WP_GMAIL_TOKEN, WP_GMAIL_LABEL.

Message-ID = <wp-{sha256(idempotency_key)[:32]}@warrantypilot.local>.
content_sha256 porte sur les octets du message sérialisé. Documents : références
seulement. Réponses : données non fiables sans action automatique.
Une tentative sending sans preuve de livraison exige un contrôle humain.
Le verrou protège un processus ; ne pas partager le journal entre processus.
ActionResultsLedger est en lecture seule ; JSONL est requis pour les écritures.
