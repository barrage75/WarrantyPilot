# Suivi L8 — service API

L'API compose ces composants avec le transport e-mail L6 et l'orchestrateur.
Ils n'envoient aucun message, ne retournent aucun matériel et n'accordent aucune
autorisation. Les pages Dell sont une **reproduction locale**, jamais Dell réel.

## Constructeurs / contrat FollowUpChecker

```python
from pathlib import Path
from app.actions.email import EmailReplyChecker
from app.followup import (
    CompositeFollowUp,
    DellPortalFollowUp,
    PortalReference,
    ReminderPlanner,
    ReminderOutbox,
    ReminderScheduler,
    ReminderState,
    ReturnDeadlineChecker,
    ReturnRequirement,
)

email = EmailReplyChecker(transport=transport_l6, ledger=sent_ledger_l6)
dell = DellPortalFollowUp(resolve_reference=resolve_reference)
follow_up = CompositeFollowUp(email=email, portal=dell)
# Le service de production est construit par app.api.main.
```

`resolve_reference(case: Case) -> PortalReference | None` lit la **preuve de
soumission réussie** de ce dossier et retourne
`PortalReference.from_number(proof.case_number)`. Il ne doit pas inventer une
référence. L'URL de confirmation L4b n'est pas l'URL de suivi : on utilise le
numéro pour construire `/support/status/{number}`. `None` signifie aucune
référence disponible, donc aucun résultat. Les lectures portent exclusivement
sur `http://127.0.0.1:8100`, vérifient aussi `UrlAllowlist` L4b, refusent toutes
les redirections et désactivent les proxies d'environnement. `localhost`, les
autres ports, identifiants, paramètres et fragments sont refusés ici.

`check(case)` retourne des dictionnaires compatibles `FollowUpChecker` :
`received`, `in_progress`, `part_shipped` → `status=tracked`; `closed` →
`status=resolved`, avec `proof={url, case_number, portal_status, observed_at}`
et `reality=reproduction`. Une page invalide/inconnue ou un échec HTTP donne
`kind=followup_error` **sans** statut de résolution. Un cas sans preuve donne
`[]`. Les statuts autres que `sent/tracked` ne sont pas interrogés.

Composite route selon `case.verdict.channel` puis `case.channel`, comme le
cœur : `email_*` délègue **sans transformation** à `EmailReplyChecker` L6,
`browser_portal` au checker Dell, `manual/api` à rien. Une acceptation e-mail
L6 n'est pas convertie en résolution.

## Appel périodique et idempotence

`POST /api/followup/tick` et la tâche périodique configurée par
`WP_FOLLOWUP_INTERVAL_S` (0 désactive la tâche) relisent les dossiers
`sent/tracked` depuis la base avant chaque traitement :

1. Appeler `follow_up.check(case)` ; journaliser les nouveautés (e-mail par
   `message_id`, Dell par `case_number + portal_status`, et non par horodatage).
   Appliquer les transitions autorisées du cœur seulement ; ne jamais résoudre
   sur une erreur ou sur `accepted` L6.
2. Recharger le dossier après ce suivi, puis calculer l'état de relance depuis
   les **preuves d'envoi réussies** et les réponses déjà journalisées :
   `ReminderState(sent_at, reminder_sent_at=tuple(...), last_response_at=...)`.
   Ne pas utiliser `Case.updated_at` (un polling le ferait dériver). Toute réponse
   depuis l'envoi initial suspend les relances automatiques. Pour Dell,
   une nouvelle progression est une réponse, pas une répétition de `received`.
3. Construire une fois
   `ReminderScheduler(ReminderPlanner(after_days=7), ReminderOutbox(Path("runtime/followup.sqlite3")))`.
   Appeler `scheduler.run(case, state)` : persiste un brouillon unique puis
   retourne uniquement les nouvelles recommandations. Les lectures suivantes
   passent par `scheduler.pending(case, state)` : reprise après crash et
   suppression des brouillons devenus inéligibles après réponse/résolution.
4. Pour chaque brouillon, un humain gère la validation et la politique
   d'envoi existantes. Avant toute exécution, recharger/revérifier le dossier
   et l'éligibilité, y compris pause, canal et réponse reçue. Réutiliser
   `idempotency_key` dans l'adaptateur d'envoi L6. Une tentative inconnue ne doit
   pas être renvoyée aveuglément. Après preuve d'envoi, enregistrer le timestamp
   dans l'état persistant et appeler `outbox.acknowledge(key)` ; jamais avant.
   Pour `browser_portal`, un brouillon nécessite un canal de contact validé ou
   un humain : ne pas utiliser L4b pour soumettre une seconde demande de réparation.
5. Après deux relances **effectivement envoyées** puis encore N jours sans
   réponse, le résultat est `manual_takeover_recommended` (pas une troisième
   relance). L'API journalise la recommandation et utilise les transitions du
   graphe de statuts.

Les brouillons ne sont **pas** des relances envoyées : sans confirmation
d'envoi, le compteur reste inchangé. Les clés sont bornées à trois par dossier
(`case:{id}:followup:1/2/3`) ; ni redémarrage, ni polling concurrent ne dupliquent
un brouillon. Le stockage SQLite de l'outbox appartient au composant, sans
migration partagée. Un nouveau cycle nécessite un nouveau dossier ; pas de
réarmement automatique après réponse. Les `pending` bruts de l'outbox sont un
outil de diagnostic : pour l'exécution, utiliser `scheduler.pending` et les
garde-fous du cœur.

## Échéances de retour et sécurité PC

`ReturnRequirement(case_id, manufacturer, requested_on, within_days, source,
is_pc=False, received_on=None)` exige un délai positif **explicitement fourni
par une consigne/RMA**, avec source. Aucun « délai Jabra de 30 jours » n'est
inventé ; les exemples de tests sont fictifs. `due_on = requested_on + within_days`
en jours calendaires ; une consigne avec date absolue peut être convertie par
l'appelant en nombre de jours. `ReturnDeadlineChecker(...).check(case,
requirement, checklist)` expose la date, J-3, `due_soon/overdue` et les blocages.
Il faut persister `ReturnRequirement` côté lead et diffuser les alertes de façon
idempotente (clé dossier + échéance + type d'alerte).

Pour Jabra, `replacement_blocked_until_return_received=True`. Pour Dell ou
`is_pc=True`, `return_blocked=True` tant que la `DataChecklist` des sept étapes
du **même dossier** n'est pas complète au sens du contrat ; aucune étape n'est
cochée/modifiée par ce composant. Le lead conserve le garde-fou bloquant dans
le chemin de retour physique. L'échéance reste visible même si la procédure PC
bloque. Une réception confirmée ou annulation masque l'échéance ; une résolution
ne masque pas un retour encore dû. L'échéance n'est pas une autorisation d'envoi.

## Horloge et vérifications

Checkers, planner et échéances acceptent `clock: Callable[[], datetime]` (date
avec fuseau, normalisée UTC) et `demo_today: date | None` (minuit UTC figé,
prioritaire). Pas de lecture implicite d'une variable d'environnement de démo.

```sh
make lint typecheck test
cd backend && uv run mypy --strict app/followup
uv run pytest tests/unit/followup tests/integration/followup
```

Le test d'intégration démarre réellement `repro/dell` via uv sur **127.0.0.1:8100**,
crée un dossier fictif par HTTP, lit la page et avance tous les statuts avec
`/__test__/advance/{number}`. Il échoue si le port est déjà occupé et ne
réinitialise jamais un serveur préexistant. Aucun Playwright n'est nécessaire
au checker HTTP. Les tests de redirection ouvrent également des serveurs
strictement loopback ; aucun accès au vrai fabricant.
