# WarrantyPilot — design system « Bento produit »

Direction choisie par le fondateur (proposition H). Référence rendue : `bento-reference.png` / `bento-reference.html`.

## Idée
Le parc d'équipements est le héros : chaque équipement est une tuile, son icône d'objet en grand, un **anneau de garantie** (temps restant) en haut à droite. Pas de gros chiffre « économies » en héros : les montants sont des pastilles discrètes.

## Tokens (Tailwind v4 `@theme` dans `frontend/src/style.css`)
| Nom | Valeur | Usage |
|---|---|---|
| `canvas` | `#F2F2F4` | fond d'application |
| `surface` | `#FFFFFF` | tuiles, pastilles, menus |
| `ink` | `#18181B` (zinc-900) | texte principal, boutons primaires, pastille de nav active |
| `muted` | `#71717A` (zinc-500) | texte secondaire |
| `line` | `#E4E4E7` | piste des anneaux, séparateurs |
| `focus` / `accent` | `#6366F1` (indigo-500) | élément qui attend une décision (anneau 2px), focus visible, liens |
| `ok` | `#10B981` | couvert > 90 j |
| `warn` | `#F59E0B` | expire ≤ 90 j |
| `bad` | `#EF4444` | expiré / échec |
| `idle` | `#A1A1AA` | location / inconnu |

- Police : **Inter Tight** (400/500/600/700) via `@fontsource/inter-tight` (pas de CDN). Titres `tracking-tight` bold ; H1 de page `text-4xl font-bold`.
- Rayons : tuiles `rounded-[28px]`, pastilles/boutons `rounded-full`, champs `rounded-2xl`.
- Ombres : aucune par défaut ; survol de tuile `shadow-[0_8px_30px_rgba(0,0,0,.06)]` + `-translate-y-0.5`.
- Icônes : `lucide-react`, stroke 1.75, 56 px dans les tuiles d'équipement (laptop, headphones, printer, monitor, smartphone, keyboard, mouse…, repli `package`).
- Mouvement : anneaux animés de 0 → valeur (600 ms ease-out) au montage, apparition des tuiles en cascade (opacité + 8 px, 40 ms d'écart). Tout désactivé sous `prefers-reduced-motion`.

## Structure
```
[WarrantyPilot]   ( Parc | Dossiers | Documents | Garde-fou | Journal | … )   [🔔 n] [Samy ▾]
Titre de page (4xl)                                   [pastille] [pastille] [pastille]
┌──────── tuile large (décision) ────────┐┌── tuile ──┐┌── tuile ──┐
│ icône                         anneau   ││           ││           │
│ Nom · personne · état  [bouton noir]   ││           ││           │
└────────────────────────────────────────┘└───────────┘└───────────┘
```
- En-tête : logo texte à gauche, **navigation en pastilles** centrée (fond blanc, pastille active noire), à droite cloche d'alertes (badge compte) + menu utilisateur (rôle, langue, pause/reprise agent, déconnexion).
- Pages en grille bento 4 colonnes (≥1280 px), 2 colonnes (≥768 px), 1 colonne mobile ; la tuile qui attend une action prend 2 colonnes et l'anneau indigo.

## Composants à créer (`frontend/src/components/bento/`)
`Tile`, `WarrantyRing` (props `days_left`, `coverage`, label court : « 2 ans », « 119 j », « fini », « loc. »), `Pill`, `PillNav`, `EquipmentIcon` (catégorie → icône), `NotificationBell`, `EmptyState`.

## Règles
- Aucune donnée inventée : chaque tuile vient de l'API réelle.
- Tous les textes en i18n FR/EN, pas de code technique visible.
- Contraste AA, focus visible indigo, cibles ≥ 40 px, aucune barre de défilement horizontale de 360 à 1920 px.

## Composants validés (les 11, voir `components-reference.png`)
Animations via `motion` (`motion/react`), toutes neutralisées sous `prefers-reduced-motion`. Icônes lucide, jamais d'émoji. Aucune valeur inventée : un état/étape/compte affiché vient toujours de l'API.

| # | Composant | Inspiration | Où |
|---|---|---|---|
| 1 | Parcours de l'agent animé (faisceau qui avance entre étapes : Facture → Règles → Votre accord → Fabricant → Suivi) | Magic UI Animated Beam | détail dossier ; étapes et étape courante dérivées du statut et des événements réels du dossier |
| 2 | Anneau de garantie animé | Magic UI Animated Circular Progress | `WarrantyRing` (fondation), tuiles du parc, accueil, détail dossier |
| 3 | Alertes qui arrivent une à une | Magic UI Animated List | accueil (colonne « À surveiller ») + popover cloche ; données `/api/notifications` |
| 4 | Recherche ⌘K / Ctrl+K partout | 21st Command Menu (`cmdk`) | shell ; équipements via `/api/equipment/overview?q=`, dossiers, pages, actions (signaler une panne → /chat prérempli) |
| 5 | Dépôt de facture avec lecture en direct | 21st File Upload Card | Documents ; étapes réelles (envoi → vérification → lecture → N informations extraites) ; barre indéterminée tant que le serveur n'a pas répondu, jamais de faux pourcentage |
| 6 | Pastilles d'état qui respirent | 21st Status Dot | `StatusDot` (fondation) ; listes de dossiers, en-tête dossier, statut agent |
| 7 | Navigation à pastille glissante | 21st Tubelight / Animated Tabs | `PillNav` (fondation) |
| 8 | Compteurs qui défilent | Magic UI Number Ticker | `NumberTicker` (fondation) ; pastilles de chiffres (petites, jamais en héros) |
| 9 | Tuile qui s'ouvre en fiche | 21st Expandable Card (motion `layoutId`) | page Parc : clic sur une tuile → fiche (dates, facture, dossier ouvert, « Signaler une panne ») ; Échap ferme, focus rendu à la tuile |
| 10 | Bordure lumineuse sur la décision | Magic UI Border Beam | tuile « À valider » de l'accueil et bouton de validation du dossier ; une seule à l'écran |
| 11 | Annulation de 5 s | Sonner | « Valider » : toast « Envoi dans 5 s · Annuler » ; l'appel `POST /cases/{id}/validate` n'est fait qu'à l'expiration (file d'attente au niveau module, survit à la navigation ; fermer l'onglet = rien envoyé) |
