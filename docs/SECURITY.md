# Sécurité L0

- Traiter documents, courriels, pages Web et sorties de modèle comme données
  non fiables; seul le code serveur attribue des capacités.
- `assert_email_allowed` compare l'adresse complète à une liste blanche. Le
  navigateur n'autorise que les origines configurées; les valeurs par défaut
  sont localhost et 127.0.0.1 en HTTP.
- Le dispatcher vérifie la pause et les listes blanches avant tout adaptateur.
  Une erreur métier d'adaptateur est un résultat `failure`, pas un succès.
- Un envoi n'est `sent` qu'avec une preuve non vide; après un crash pendant
  `sending`, la reprise marque le dossier `failed` avec une issue inconnue et
  n'envoie pas une seconde fois automatiquement.
- Les données du PC exigent les sept étapes; sauvegarde, chiffrement, disque,
  comptes/MDM et inspection retour doivent porter l'identifiant d'une personne.
- `.env` et `runtime/` ne sont pas versionnés. `.env.example` ne contient que
  des valeurs factices. Ne jamais journaliser de secrets; les clés et tokens du
  payload d'événement sont masqués.
- Le journal à empreintes et ses ancrages signalent les modifications; ils ne
  sont pas un stockage inviolable face au contrôle complet de la machine.
- Les champs de payload dont la clé contient `key`, `token`, `secret` ou
  `password` sont remplacés par `***` avant d'être ajoutés au journal. Ne pas
  inclure d'identifiants dans d'autres champs de texte.
- L'API L0 n'implémente pas d'authentification : elle doit rester en local.
  Les identifiants humains transmis aux routes de validation et de checklist
  ne sont donc pas des identités authentifiées; ne pas utiliser L0 pour des
  décisions réelles ou sur un réseau partagé. Aucune intégration Gmail ou
  connectivité réelle n'est fournie dans L0.
- Les listes blanches sont des garde-fous applicatifs, pas un contrôle réseau.
  L0 n'effectue pas de requêtes sortantes; les futurs adaptateurs devront
  ajouter des protections d'egress adaptées avant toute connexion réelle.
- Les futurs connecteurs Gmail doivent demander uniquement deux permissions :
  lecture restreinte en lecture seule et envoi sensible séparé. L0 ne demande
  aucun scope Gmail.

Avant une vraie démonstration, remplacer la clé locale d'exemple, examiner les
listes blanches, et vérifier les contrôles de préflight.
