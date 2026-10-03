# Pigeons : le manuel

*Le système d'indication pour travailler avec des sessions d'IA · version du 2026-10-03*

## 1. À qui s'adresse ce manuel

- **À toi qui t'en sers** : les sections 2 à 4 (lancer, se servir des pigeons, les réglages).
- **À la personne ou à l'IA qui reprend le travail** : les sections 5 à 10 (les IA et `montre.py`, le fonctionnement interne, les fichiers, les pièges, la vie privée, comment continuer).
- Ce manuel est fabriqué par `faire_manuel.py` à partir du code : la liste des réglages et le guide sont toujours exacts. Après un changement dans l'app, relance `python faire_manuel.py`.

## 2. Installer et lancer

- **Ce qu'il faut** : Windows 10 ou 11 ; Python 3.11 ou plus récent (essayé avec 3.13) ; les modules `comtypes`, `pywin32` et `Pillow` : `python -m pip install --user comtypes pywin32 pillow`.
- **Lancer** : double-clic sur `Lancer la preuve.bat`, ou `pythonw preuve_pigeons.py` dans le dossier. Une seule copie tourne à la fois (un verrou de Windows) : relancer ramène le panneau devant.
- **Avec Windows** : la case « Lancer les pigeons avec Windows » pose un raccourci dans le dossier Démarrage de Windows.
- **Arrêter** : le bouton « Arrêter » du panneau. Le ✕ de la fenêtre réduit seulement le panneau ; les pigeons continuent.
- **Vérifier sans fenêtre** : `python preuve_pigeons.py --texte` affiche l'état de chaque pigeon (en anglais).
- **Voir les permissions à donner** (facultatif) : un crochet « Notification » de Claude Code, dans `~/.claude/settings.json`, avec le filtre `permission_prompt|elicitation_dialog|elicitation_url_dialog|agent_needs_input` et la commande `python "<dossier>\crochet_notification.py"`.

## 3. Se servir des pigeons

Le même texte que l'onglet « Guide » du panneau.

#### Ce que font les pigeons

Chaque session d'IA (Claude Code, Cowork, une autre IA) a son pigeon et sa couleur. Quand une session a besoin de toi, les pigeons te montrent quoi faire et où cliquer.

Tout reste sur ton ordinateur : les pigeons lisent les journaux de Claude Code et n'envoient rien.

#### À l'écran

- Une ligne pointillée va de ta souris jusqu'à ce qui t'attend : une session, un bouton, un fichier.
- Un encadré épouse la cible. Avec plus d'infos à l'écran, une étiquette dit qui t'attend, pour quoi, et depuis quand.
- Les pigeons eux-mêmes sont cachés par défaut (Réglages, carte Pigeons, pour les afficher). Affichés, le corps a la couleur de sa session ; un anneau qui respire : elle t'attend ; en pointillé : en pause.
- Deux cibles liées (glisser un fichier dans un dossier, ou cliquer ici puis là) : une ligne fléchée va de la première à la seconde, leurs encadrés portent 1 et 2, et des étiquettes disent « prends ceci » et « dépose ici ».
- Les pigeonneaux sont les sous-agents d'une session.

#### Les couleurs d'importance

- Bloquée : une permission à donner (#ff2d55)
- Haute : un geste à faire (#ff5a5f)
- Normale : une question posée (#ffb020)
- Basse : à toi quand tu veux (#5aa0ff)

Ces couleurs se changent dans Réglages.

#### Le panneau

À faire pour toi : une carte par session qui t'attend, la plus importante en haut. Au travail : les sessions qui travaillent, leur fichier et leur rythme. Au repos : celles qui dorment.

- Aller : ouvre la session dans Claude.
- Guider : la ligne et le pigeon te montrent le chemin.
- C'est fait : le geste demandé est fait.
- Plus tard : 5 min, 15 min, 1 h ou sans limite.
- Terminer : la session est finie ; elle revient si tu lui écris.
- Copier, Ouvrir, Montrer : les liens et les fichiers cités par la session.
- Aide active : quand une session te demande d'aller dans un dossier, d'ouvrir un fichier ou une fenêtre, sa carte offre « Ouvrir le dossier », « Ouvrir le fichier » ou « Amener devant ».
- Au travail : « Dossier » ouvre l'endroit où la session travaille ; la ligne dit depuis quand dure son tour et la taille de son contexte (une compaction vient près de la limite) ; un avertissement si deux sessions travaillent dans le même dossier.

Survole un bouton : il dit ce qu'il fait. Le ✕ de la fenêtre réduit le panneau ; « Arrêter » arrête les pigeons.

#### Avec la souris

- Clique l'endroit montré : c'est fait, le pigeon dit merci.
- Si les pigeons sont affichés : clique un pigeon pour plus tard (reclique : reprendre) ; clic droit : terminer sa session.
- Survole un pigeon : sa bulle complète.

#### Au clavier

- Ctrl+Alt+P : va à la chose la plus importante ; rappuie dans les 6 s pour la suivante.
- Ctrl+Alt+T : « C'est fait » ou « Terminer » sur la première chose à faire.

#### Fermer une session finie

« Terminer » (sur la carte, au clic droit, ou Ctrl+Alt+T), archiver la session dans Claude, ou la session elle-même à la fin de sa passation (montre.py --termine). Elle revient si tu lui écris.

#### Pour les IA : montre.py

Une session qui a besoin d'un geste lance : python montre.py --texte "Clique sur Accepter" --fenetre "Chrome" --element "Accepter".

Autres cibles : --fichier, --point X Y. Un glisser : --vers-… Deux étapes : --puis-… Et aussi --importance, --fin, --termine. Une autre IA : --session nom --titre "Nom".

La coordination : les pigeons tiennent activite.json à jour (qui travaille où, toutes les 2 s). Une autre IA s'annonce par annonce.py --session nom --fichier CHEMIN --ecrit, et demande avant d'écrire : annonce.py --qui CHEMIN (libre, occupé). Le panneau avertit quand deux IA écrivent le même fichier.

#### Les réglages

En bas du panneau : le guidage (lignes ou flèches), les infos à l'écran, la forme et le mouvement des lignes, le fondu, les encadrés, les pigeons, les couleurs, la langue. Tout se garde dans reglages.json.

La ligne vers une session qui a fini son tour : jamais par défaut (Ctrl+Alt+P ou « Guider » la montrent), quelques minutes, ou jusqu'à ta réponse. Une question posée, une permission et un geste demandé sont toujours guidés ; une question vise son questionnaire, jusqu'au bouton « Envoyer ». Si Windows a coupé ses animations, les lignes ne bougent plus non plus.

#### Les fichiers

Le dossier : %USERPROFILE%\Desktop\Pigeons. MANUEL.docx (ou MANUEL.md) explique tout en détail ; preuve_pigeons.log garde les erreurs.

## 4. Tous les réglages

Le bouton « Réglages » du panneau ouvre la fenêtre des réglages, dans le style des paramètres de Claude : à gauche, une recherche et les catégories (le guidage : Guidage, Lignes, Encadrés ; l'app : Apparence, Pigeons, Général) ; à droite, leurs sections. La recherche montre les sections de toutes les catégories qui contiennent le mot tapé. Chaque changement s'applique tout de suite et se garde dans `reglages.json`. « Remettre par défaut » garde la langue, la place du panneau et le démarrage avec Windows.

#### Apparence

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Thème | Système ; Clair ; Sombre | Système | `theme` |
| Thème sombre | Par défaut ; Nuit ; Ambre | Par défaut | `theme_sombre` |
| Contraste | Normal ; Fort | Normal | `contraste` |
| Mes couleurs : | oui ou non | non | `theme_perso` |
| Fond | une couleur | #16171b | `couleur_fond` |
| Texte | une couleur | #e9e9ec | `couleur_texte` |
| Accent | une couleur | #8ab4ff | `couleur_accent` |
| Bulles et étiquettes | Papier (claires) ; Aux couleurs du thème | Papier (claires) | `bulles_couleurs` |

- « Système » suit le thème clair ou sombre de Windows. « Ambre » reprend les couleurs d'Antigravity.

#### Général

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Langue | English ; Français | English | `langue` |
| Le panneau | Libre (je le place moi-même) ; Collé à droite de Claude ; Collé à gauche de Claude | Libre (je le place moi-même) | `ancrer_claude` |
| Lancer les pigeons avec Windows | oui ou non | non | `demarrage_windows` |

- Ctrl+Alt+P : prochaine action (rappuyer dans les 6 s passe à la suivante).
- Ctrl+Alt+T : « C'est fait » ou « Terminer » sur la première chose à faire. Clic droit sur un pigeon : terminer sa session.

#### Guidage

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Guidage vers ce que tu as à faire | Des lignes pointillées de ma souris au but ; Des flèches autour de ma souris | Des flèches autour de ma souris | `guidage` |
| Guider vers les sessions qui m'attendent | oui ou non | oui | `fleche_attente` |
| Infos à l'écran | Discrètes (la ligne et l'encadré) ; Détaillées (une étiquette : qui, quoi, depuis quand) ; Complètes (et le geste à faire, avec son raccourci) | Discrètes (la ligne et l'encadré) | `infos_ecran` |
| Flèches creuses (juste le contour) | oui ou non | oui | `fleche_creuse` |
| Taille des flèches (px) | de 14 à 44 | 23 | `taille_fleche` |

#### Quand une session m'attend

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Ligne vers une session qui attend ma réponse | Jusqu'à ma réponse (ou « Terminer ») ; Pendant 15 min ; Pendant 5 min ; Pendant 1 min ; Jamais : Ctrl+Alt+P ou « Guider » la montrent | Jamais : Ctrl+Alt+P ou « Guider » la montrent | `lignes_reponse` |
| Le pigeon vient près de ma souris | oui ou non | non | `appel_souris` |
| Pendant (secondes) | de 5 à 60 | 20 | `duree_appel_s` |
| Clic sur un pigeon : plus tard (min, 0 = sans fin) | de 0 à 120 | 15 | `report_clic_min` |

- Une fin de tour. L'encadré et l'étiquette restent. Une question posée (son questionnaire), une permission à donner et un geste demandé sont toujours guidés.

#### Lignes pointillées

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Style | Des points ; Des tirets | Des points | `lignes_style` |
| Grosseur (px) | de 2 à 10 | 4 | `lignes_epaisseur` |
| Espacement (px) | de 6 à 30 | 11 | `lignes_espacement` |

#### Forme et mouvement

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Forme | Droite ; En arc ; Sinueuse ; En vol | En arc | `lignes_forme` |
| Courbure (%) | de 0 à 100 | 35 | `lignes_courbure` |
| La ligne se dessine à son apparition | oui ou non | oui | `lignes_trace` |
| Animation continue | Aucune ; Les points avancent ; Une onde | Aucune | `lignes_animation` |
| Vitesse de l'animation | de 1 à 10 | 4 | `lignes_vitesse` |

- « En vol » : un arc et de petites vagues, comme un pigeon. Une animation continue redessine les lignes 15 fois par seconde : un peu plus de processeur.

#### Fondu

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Opacité près de ma souris (%) | de 0 à 100 | 90 | `lignes_opacite_depart` |
| Opacité près du but (%) | de 0 à 100 | 90 | `lignes_opacite_arrivee` |
| Le fondu commence à (% du trajet) | de 0 à 100 | 0 | `lignes_fondu_debut` |
| Le fondu finit à (% du trajet) | de 0 à 100 | 100 | `lignes_fondu_fin` |

- 0 % du trajet : à ta souris ; 100 % : au but. Deux opacités égales : pas de fondu. Exemple : 90 puis 0, de 50 à 100 : la ligne est pleine jusqu'à mi-chemin et s'éteint en arrivant.

#### Couleur des lignes

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Couleur des lignes | De la couleur du guide ; D'une seule couleur : | De la couleur du guide | `lignes_couleur` |
| la couleur unique des lignes | une couleur | #ffffff | `lignes_couleur_unique` |

#### Encadrés

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Encadrés | Actifs, toujours affichés ; Actifs quand ma souris approche ; Désactivés | Actifs, toujours affichés | `encadres` |
| Encadrer aussi l'endroit montré par une demande | oui ou non | oui | `encadres_montre` |
| Style | En pointillés ; En trait plein | En pointillés | `encadres_style` |
| Taille autour de la cible (px) | de -3 à 12 | 0 | `encadres_marge` |
| Coins arrondis (px) | de 0 à 12 | 6 | `encadres_arrondi` |
| Épaisseur du trait (px) | de 1 à 4 | 1 | `encadres_epaisseur` |

#### Pigeons

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Quand une fenêtre cache l'icône où il travaille | Il va sur la barre des tâches ; Il se perche sur cette fenêtre ; Il se cache | Il va sur la barre des tâches | `cible_cachee` |
| Taille des pigeons | de 5 à 14 | 8 | `taille_pigeon` |
| Afficher les pigeons (sinon : les lignes, les flèches et les encadrés seulement) | oui ou non | non | `afficher_pigeons` |
| Montrer aussi les pigeons au travail | oui ou non | oui | `pigeons_au_travail` |
| Montrer les pigeonneaux (sous-agents) | oui ou non | oui | `pigeonneaux` |
| Ligne vers l'endroit exact où il travaille | Au survol du pigeon ; Toujours ; Jamais | Au survol du pigeon | `lignes_travail` |

#### Couleurs et bulles

| Réglage | Choix possibles | Par défaut | Clé dans reglages.json |
|---|---|---|---|
| Couleur des guides | La couleur de la tâche ; Le code d'importance | La couleur de la tâche | `couleur_guides` |
| Bloquée : une permission à donner | une couleur | #ff2d55 | `couleur_bloquee` |
| Haute : un geste à faire | une couleur | #ff5a5f | `couleur_haute` |
| Normale : une question posée | une couleur | #ffb020 | `couleur_normale` |
| Basse : à toi quand tu veux | une couleur | #5aa0ff | `couleur_basse` |
| Bulles | Une ligne courte quand il montre ou m'appelle ; Seulement au survol | Une ligne courte quand il montre ou m'appelle | `bulles` |
| Opacité des bulles (%) | de 40 à 100 | 90 | `opacite_bulles` |

#### Les réglages gardés par le programme

Ils ne sont pas dans la fenêtre : le programme les tient seul (la place du panneau), ou ils restent d'une ancienne version, pour lire les vieux fichiers. Ne les change pas à la main.

- `panneau_geometrie` : `''`
- `lignes_opacite` : `80`
- `lignes_fondu` : `'aucun'`
- `lignes_fondu_portee` : `100`
- `lignes_fondu_min` : `0`

## 5. Pour les IA et les scripts

### 5.1 Montrer un geste : montre.py

Une session qui a besoin d'un geste de l'utilisateur lance, par exemple :

```
python "%USERPROFILE%\Desktop\Pigeons\montre.py" --texte "Clique sur Accepter" --fenetre "Chrome" --element "Accepter"
```

| Option | Ce qu'elle fait |
|---|---|
| `--texte TEXTE` | la consigne, en une phrase |
| `--fichier CHEMIN` | une icône du Bureau ou d'un dossier ouvert |
| `--fenetre TITRE --element NOM` | un bouton, un lien ou une case d'une fenêtre, par une partie de son nom (lu par l'automatisation de Windows) ; avec --fenetre "Pigeons", un bouton du panneau (« Réglages », « Guide »...) |
| `--point X Y` | un point de l'écran, en pixels physiques |
| `--vers-fichier, --vers-fenetre, --vers-element, --vers-point` | l'arrivée d'un glisser |
| `--puis-fichier, --puis-fenetre, --puis-element, --puis-point, --puis-texte` | une deuxième étape (« clique ici, puis là ») : encadrés numérotés 1 et 2 |
| `--importance haute\|normale\|basse` | haute par défaut |
| `--minutes N` | la durée de la demande (15 par défaut) ; elle finit aussi au prochain message de l'utilisateur à la session |
| `--fin` | efface la demande tout de suite |
| `--termine` | la séance est finie : le pigeon, la carte et les lignes s'en vont (à lancer en tout dernier, juste avant la dernière réponse) |
| `--session NOM, --titre NOM` | pour une autre IA sans journal Claude Code ; par défaut, la session est lue dans la variable CLAUDE_CODE_SESSION_ID |

### 5.2 Les fichiers d'échange (JSON)

- **`demandes\<session>.json`** (écrit par `montre.py`) : `session`, `heure`, `duree_s`, `texte`, `cible`, `vers`, `puis`, `texte_puis`, `titre`, `importance`. Une cible vaut `{"fichier": chemin}`, `{"fenetre": titre, "element": nom}` ou `{"point": [x, y]}`.
- **`signaux\<session>.json`** (écrit par `crochet_notification.py`) : `session`, `type` (`permission_prompt`, `elicitation_dialog`, `elicitation_url_dialog`, `agent_needs_input`), `message`, `heure`. Rangé dès que la session repart.
- **`fermetures\<session>.json`** : `session`, `heure`, `par` (`danny` ou `session`). Oublié après 3 jours, ou dès que la session repart.
- **`demandes\_vivant.txt`** : l'heure du dernier tour ; `montre.py` y voit si les pigeons tournent.
- Chaque fichier s'écrit d'abord à côté, puis se renomme : le programme ne lit jamais un fichier à moitié écrit.

### 5.3 Les règles données aux sessions Claude

Dans `Desktop\CLAUDE.md`, que lit chaque session lancée dans le Bureau :

- montrer chaque geste demandé à l'utilisateur par `montre.py` ;
- lancer `montre.py --termine` à la fin de la passation ;
- écrire en clair les liens et les chemins des livrables : le panneau les offre (Copier, Ouvrir, Montrer).

Une autre IA (Cowork, Gemini, un script) passe `--session nom --titre "Nom"`, ou écrit elle-même le fichier de demande ; son pigeon vit tant que sa demande existe.

### 5.4 Se coordonner entre IA : activite.json et annonce.py

Pour que deux IA n'écrivent pas le même fichier en même temps (l'utilisateur, 3 octobre 2026) :

- **Le registre** `activite.json` : les pigeons y écrivent toutes les 2 s qui travaille où (session, outil, fichier, dossier de projet, état, fichiers écrits depuis 10 min) et les conflits. Pour une IA qui a fait une demande, `demande.trouvee` dit si sa cible est trouvée à l'écran, et `demande.precision` pourquoi sinon. Les sessions Claude Code y sont seules, par leur journal.
- **S'annoncer** (une autre IA) : `python annonce.py --session ag --titre "AG" --ia Antigravity --fichier CHEMIN --ecrit` ; ou `--dossier CHEMIN` ; `--fin` à la fin. L'annonce tient 10 min (`--minutes`) : la refaire en changeant de fichier.
- **Demander avant d'écrire** : `python annonce.py --qui CHEMIN --session ag`. Code de sortie 0 : libre (avec un « attention » si une autre IA travaille dans le même dossier) ; 1 : occupé (une autre IA a écrit ce fichier depuis 10 min, ou travaille dessus) ; 2 : je ne sais pas (les pigeons ne tournent pas).
- **Le conflit** : deux IA qui écrivent le même fichier à moins de 5 min font apparaître un bandeau en haut du panneau.

## 6. Comment ça marche dedans

Tout tient dans `preuve_pigeons.py` (environ 4200 lignes), en trois parties qui se parlent par un état partagé.

#### Le guetteur (classe Guetteur, un fil à part, un tour par seconde)

- Il lit la fin des journaux de Claude Code (`~/.claude/projects/*/*.jsonl`, et `subagents/` pour les sous-agents) : la classe `Session` y suit les outils, les fichiers touchés, les fins de tour, les questions, les messages de l'utilisateur et les liens cités.
- Il lit les demandes, les signaux, les fermetures, et les fiches de l'app Claude (`%APPDATA%\Claude\claude-code-sessions`, pour savoir qu'une session est archivée).
- Il situe les cibles par l'automatisation de Windows (UIA, module `comtypes`) : les icônes du Bureau et de l'Explorateur, les boutons d'une fenêtre, la ligne d'une session dans l'app Claude, un bouton de la barre des tâches.
- Il décide le mode de chaque pigeon (`placer`) et dépose le tout dans l'état partagé.

#### Les modes et les importances

- **Les modes** : `montre` (une demande de `montre.py`), `appel` puis `attend` (une session attend l'utilisateur), `pose` (sur l'icône du fichier où elle travaille), `perche` (cette icône est cachée), `parc` (pas de fichier), `repos` (2 min sans outil) ; côté affichage, `pause` et `merci`.
- **Les importances** : `bloquee` (une permission, par le crochet), `haute` (un geste demandé), `normale` (une question posée), `basse` (une fin de tour).
- **Une session fermée** (`Session.est_fermee`) : un fichier dans `fermetures\`, ou archivée dans l'app. Elle se rouvre si l'utilisateur lui écrit, si elle demande une permission ou un geste, ou si elle relance un outil plus de 2 min après.

#### L'affichage (classe Volee, le fil de Tk, 30 images par seconde)

- Chaque pigeon, flèche, encadré et bulle est une petite fenêtre transparente qu'on déplace (une toile plein écran coûtait 13 % d'un cœur).
- Les lignes pointillées sont des fenêtres en couches (classe `Voile`, `UpdateLayeredWindow`) : chaque point a sa propre transparence ; elles ne couvrent que la boîte des lignes et ne se redessinent que si quelque chose bouge.
- `chemin()` donne le trajet (droite, arc, sinueuse, en vol) ; `points_de_ligne()` y pose les points à intervalles réguliers ; `tracer_lignes()` fait le tracé en 250 ms et les animations.
- `guider_attente()` pose les encadrés, les étiquettes et les lignes vers les sessions qui attendent ; `guetter_clic()` reconnaît le clic sur l'endroit montré ; la classe `Raccourci` (un fil) reçoit Ctrl+Alt+P et Ctrl+Alt+T.

#### Le panneau (classe Panneau)

- Les onglets « À faire » et « Guide », les cartes, les infobulles (classe `Infobulle`), et la fenêtre des réglages (`Volee.ouvrir_reglages`). Il ne se refait que si son contenu change.
- La langue : le français est écrit dans le code ; `tr()` le traduit avec la table `ANGLAIS` ; le guide a ses deux versions dans `contenu_guide()`.
- Le journal d'erreurs : `preuve_pigeons.log`, 1 Mo au plus, puis trois copies.
- Mesuré : environ 4,6 % d'un cœur sans lignes, 7,2 % avec.

## 7. Les fichiers du dossier

| Fichier | Rôle |
|---|---|
| `preuve_pigeons.py` | le programme entier |
| `montre.py` | la commande qu'une session lance pour montrer un geste |
| `crochet_notification.py` | reçoit les notifications de Claude Code (permissions) et les dépose dans signaux\ |
| `faire_manuel.py` | fabrique ce manuel |
| `annonce.py` | une autre IA dit où elle travaille, ou demande qui travaille quelque part (section 5.4) |
| `activite.json, annonces\` | le registre de qui travaille où, et les annonces des autres IA |
| `Lancer la preuve.bat` | lance les pigeons |
| `reglages.json` | les réglages de l'utilisateur : ne jamais les écraser |
| `couleurs.json` | la couleur fixe de chaque session |
| `demandes\, signaux\, fermetures\` | les fichiers d'échange (section 5.2) |
| `preuve_pigeons.log` | le journal d'erreurs |
| `MANUEL.md, MANUEL.docx, MANUAL.md, MANUAL.docx` | ce manuel, en français et en anglais |

## 8. Les pièges connus

- **`reglages.json`** : arrêter le programme avant d'y écrire, sinon il réécrit par-dessus. Ce sont les réglages de l'utilisateur.
- **Ne jamais nommer une fonction `t()`** : des variables locales s'appellent `t` (le haut d'une fenêtre).
- **Les fenêtres en couches** : ni `-alpha` ni `-transparentcolor` de Tk sur une `Voile` (ils empêchent `UpdateLayeredWindow`).
- **Les pixels physiques partout** (`SetProcessDpiAwarenessContext(-4)`) : un écran peut être à 125 %.
- **UIA est par fil** : le guetteur a la sienne, l'affichage aussi.
- **Le panneau se reconnaît** à sa classe `TkTopLevel`, à son titre « Pigeons » et au fait qu'il n'est pas une fenêtre outil.
- **Capturer les lignes** : `ImageGrab.grab(all_screens=True, include_layered_windows=True)`, sinon elles n'apparaissent pas.
- **Créer les toiles des lignes prend environ 0,45 s** : une ligne se redessine jusqu'à avoir été dessinée en entier une fois.
- **Arrêter seulement les pigeons**, pas tous les `pythonw` : filtrer sur la ligne de commande `preuve_pigeons.py`.
- **Les fiches de l'app Claude** sont internes et non documentées : elles peuvent changer.
- **Les heures** se lisent dans les journaux ou par un outil, jamais de tête.

## 9. Vie privée

Tout reste sur l'ordinateur. Les pigeons lisent les journaux de Claude Code et les fiches de l'app, sans rien y écrire ; ils n'envoient rien sur le réseau et n'ont aucune télémétrie. Ils n'écrivent que dans leur dossier (réglages, couleurs, demandes, signaux, fermetures, journal) et, si on le demande, un raccourci dans le dossier Démarrage.

## 10. Continuer le travail

- **Essayer sans fenêtre** : `python preuve_pigeons.py --texte`.
- **Relancer** : arrêter le `pythonw` dont la ligne de commande contient `preuve_pigeons.py`, puis `pythonw preuve_pigeons.py`.
