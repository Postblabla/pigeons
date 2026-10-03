"""
faire_manuel.py : fabrique le manuel des Pigeons, en français et en anglais, en Markdown et en Word.

Ce qu'il fait : il assemble le manuel à partir de trois sources.
- Le code lui-même (preuve_pigeons.py) : la liste exacte des réglages (lue dans la fenêtre des réglages,
  Volee.ouvrir_reglages), leurs choix et leurs valeurs par défaut (REGLAGES_DEFAUT), leur traduction (ANGLAIS),
  et le texte de l'onglet « Guide » (contenu_guide). Ces parties sont donc toujours exactes.
- Le texte rédigé ci-dessous (TEXTES), dans les deux langues : installer, les IA, le fonctionnement interne,
  les fichiers, les pièges, la vie privée, comment continuer.
- Le nombre de lignes du code et la date du jour.

Il écrit : MANUEL.md et MANUEL.docx (français), MANUAL.md et MANUAL.docx (anglais).

Qui s'en sert : l'utilisateur, la personne qui découvre l'app, et la prochaine IA qui reprend le travail
(demande de l'utilisateur, 3 octobre 2026). Après un changement dans l'app, on relance :
    python faire_manuel.py
Il faut le module python-docx (python -m pip install --user python-docx).
"""

import ast
import inspect
import re
import textwrap
from datetime import date
from pathlib import Path

import preuve_pigeons as P

ICI = Path(__file__).resolve().parent


# ----------------------------------------------------------------- le texte rédigé, dans les deux langues

TEXTES = {
    "fr": {
        "titre": "Pigeons : le manuel",
        "sous_titre": "Le système d'indication pour travailler avec des sessions d'IA · version du {d}",
        "h_lecteurs": "1. À qui s'adresse ce manuel",
        "lecteurs": [
            ("ul", [
                "**À toi qui t'en sers** : les sections 2 à 4 (lancer, se servir des pigeons, les réglages).",
                "**À la personne ou à l'IA qui reprend le travail** : les sections 5 à 10 (les IA et `montre.py`, le "
                "fonctionnement interne, les fichiers, les pièges, la vie privée, comment continuer).",
                "Ce manuel est fabriqué par `faire_manuel.py` à partir du code : la liste des réglages et le guide sont "
                "toujours exacts. Après un changement dans l'app, relance `python faire_manuel.py`.",
            ]),
        ],
        "h_lancer": "2. Installer et lancer",
        "lancer": [
            ("ul", [
                "**Ce qu'il faut** : Windows 10 ou 11 ; Python 3.11 ou plus récent (essayé avec 3.13) ; les modules "
                "`comtypes`, `pywin32` et `Pillow` : `python -m pip install --user comtypes pywin32 pillow`.",
                "**Lancer** : double-clic sur `Lancer la preuve.bat`, ou `pythonw preuve_pigeons.py` dans le dossier. "
                "Une seule copie tourne à la fois (un verrou de Windows) : relancer ramène le panneau devant.",
                "**Avec Windows** : la case « Lancer les pigeons avec Windows » pose un raccourci dans le dossier "
                "Démarrage de Windows.",
                "**Arrêter** : le bouton « Arrêter » du panneau. Le ✕ de la fenêtre réduit seulement le panneau ; les "
                "pigeons continuent.",
                "**Vérifier sans fenêtre** : `python preuve_pigeons.py --texte` affiche l'état de chaque pigeon (en "
                "anglais).",
                "**Voir les permissions à donner** (facultatif) : un crochet « Notification » de Claude Code, dans "
                "`~/.claude/settings.json`, avec le filtre `permission_prompt|elicitation_dialog|elicitation_url_dialog|"
                "agent_needs_input` et la commande `python \"<dossier>\\crochet_notification.py\"`.",
            ]),
        ],
        "h_guide": "3. Se servir des pigeons",
        "guide_intro": "Le même texte que l'onglet « Guide » du panneau.",
        "h_reglages": "4. Tous les réglages",
        "reglages_intro": "Le bouton « Réglages » du panneau ouvre la fenêtre des réglages, dans le style des "
                          "paramètres de Claude : à gauche, une recherche et les catégories (le guidage : Guidage, "
                          "Lignes, Encadrés ; l'app : Apparence, Pigeons, Général) ; à droite, leurs sections. La "
                          "recherche montre les sections de toutes les catégories qui contiennent le mot tapé. "
                          "Chaque changement s'applique tout de suite et se garde dans `reglages.json`. « Remettre par "
                          "défaut » garde la langue, la place du panneau et le démarrage avec Windows.",
        "colonnes_reglages": ["Réglage", "Choix possibles", "Par défaut", "Clé dans reglages.json"],
        "oui": "oui", "non": "non", "couleur": "une couleur", "de_a": "de {a} à {b}", "case": "oui ou non",
        "notes": "À savoir",
        "h_internes": "Les réglages gardés par le programme",
        "internes_intro": "Ils ne sont pas dans la fenêtre : le programme les tient seul (la place du panneau), ou ils "
                          "restent d'une ancienne version, pour lire les vieux fichiers. Ne les change pas à la main.",
        "h_ia": "5. Pour les IA et les scripts",
        "h_montre": "5.1 Montrer un geste : montre.py",
        "montre_intro": "Une session qui a besoin d'un geste de l'utilisateur lance, par exemple :",
        "montre_exemple": 'python "%USERPROFILE%\\Desktop\\Pigeons\\montre.py" --texte "Clique sur Accepter" '
                          '--fenetre "Chrome" --element "Accepter"',
        "colonnes_montre": ["Option", "Ce qu'elle fait"],
        "montre": [
            ("--texte TEXTE", "la consigne, en une phrase"),
            ("--fichier CHEMIN", "une icône du Bureau ou d'un dossier ouvert"),
            ("--fenetre TITRE --element NOM", "un bouton, un lien ou une case d'une fenêtre, par une partie de son nom "
                                              "(lu par l'automatisation de Windows) ; avec --fenetre \"Pigeons\", un "
                                              "bouton du panneau (« Réglages », « Guide »...)"),
            ("--point X Y", "un point de l'écran, en pixels physiques"),
            ("--vers-fichier, --vers-fenetre, --vers-element, --vers-point", "l'arrivée d'un glisser"),
            ("--puis-fichier, --puis-fenetre, --puis-element, --puis-point, --puis-texte",
             "une deuxième étape (« clique ici, puis là ») : encadrés numérotés 1 et 2"),
            ("--importance haute|normale|basse", "haute par défaut"),
            ("--minutes N", "la durée de la demande (15 par défaut) ; elle finit aussi au prochain message de "
                            "l'utilisateur à la session"),
            ("--fin", "efface la demande tout de suite"),
            ("--termine", "la séance est finie : le pigeon, la carte et les lignes s'en vont (à lancer en tout dernier, "
                          "juste avant la dernière réponse)"),
            ("--session NOM, --titre NOM", "pour une autre IA sans journal Claude Code ; par défaut, la session est "
                                           "lue dans la variable CLAUDE_CODE_SESSION_ID"),
        ],
        "h_formats": "5.2 Les fichiers d'échange (JSON)",
        "formats": [
            ("ul", [
                "**`demandes\\<session>.json`** (écrit par `montre.py`) : `session`, `heure`, `duree_s`, `texte`, "
                "`cible`, `vers`, `puis`, `texte_puis`, `titre`, `importance`. Une cible vaut `{\"fichier\": chemin}`, "
                "`{\"fenetre\": titre, \"element\": nom}` ou `{\"point\": [x, y]}`.",
                "**`signaux\\<session>.json`** (écrit par `crochet_notification.py`) : `session`, `type` "
                "(`permission_prompt`, `elicitation_dialog`, `elicitation_url_dialog`, `agent_needs_input`), "
                "`message`, `heure`. Rangé dès que la session repart.",
                "**`fermetures\\<session>.json`** : `session`, `heure`, `par` (`danny` ou `session`). Oublié après "
                "3 jours, ou dès que la session repart.",
                "**`demandes\\_vivant.txt`** : l'heure du dernier tour ; `montre.py` y voit si les pigeons tournent.",
                "Chaque fichier s'écrit d'abord à côté, puis se renomme : le programme ne lit jamais un fichier à moitié "
                "écrit.",
            ]),
        ],
        "h_regles": "5.3 Les règles données aux sessions Claude",
        "regles": [
            ("p", "Dans `Desktop\\CLAUDE.md`, que lit chaque session lancée dans le Bureau :"),
            ("ul", [
                "montrer chaque geste demandé à l'utilisateur par `montre.py` ;",
                "lancer `montre.py --termine` à la fin de la passation ;",
                "écrire en clair les liens et les chemins des livrables : le panneau les offre (Copier, Ouvrir, Montrer).",
            ]),
            ("p", "Une autre IA (Cowork, Gemini, un script) passe `--session nom --titre \"Nom\"`, ou écrit elle-même "
                  "le fichier de demande ; son pigeon vit tant que sa demande existe."),
        ],
        "h_coord": "5.4 Se coordonner entre IA : activite.json et annonce.py",
        "coord": [
            ("p", "Pour que deux IA n'écrivent pas le même fichier en même temps (l'utilisateur, 3 octobre 2026) :"),
            ("ul", [
                "**Le registre** `activite.json` : les pigeons y écrivent toutes les 2 s qui travaille où (session, "
                "outil, fichier, dossier de projet, état, fichiers écrits depuis 10 min) et les conflits. Pour une IA "
                "qui a fait une demande, `demande.trouvee` dit si sa cible est trouvée à l'écran, et `demande.precision` "
                "pourquoi sinon. Les sessions "
                "Claude Code y sont seules, par leur journal.",
                "**S'annoncer** (une autre IA) : `python annonce.py --session ag --titre \"AG\" --ia Antigravity "
                "--fichier CHEMIN --ecrit` ; ou `--dossier CHEMIN` ; `--fin` à la fin. L'annonce tient 10 min "
                "(`--minutes`) : la refaire en changeant de fichier.",
                "**Demander avant d'écrire** : `python annonce.py --qui CHEMIN --session ag`. Code de sortie 0 : libre "
                "(avec un « attention » si une autre IA travaille dans le même dossier) ; 1 : occupé (une autre IA a "
                "écrit ce fichier depuis 10 min, ou travaille dessus) ; 2 : je ne sais pas (les pigeons ne tournent pas).",
                "**Le conflit** : deux IA qui écrivent le même fichier à moins de 5 min font apparaître un bandeau en "
                "haut du panneau.",
                "**La limite** : seules les sessions Claude Code sont suivies sans rien faire ; les autres IA comptent "
                "sur leur bonne volonté (s'annoncer, demander). Le crochet qui arrêterait une écriture de Claude Code "
                "sur un fichier occupé est une idée, pas encore posée.",
            ]),
        ],
        "h_dedans": "6. Comment ça marche dedans",
        "dedans": [
            ("p", "Tout tient dans `preuve_pigeons.py` (environ {n} lignes), en trois parties qui se parlent par un état "
                  "partagé."),
            ("h3", "Le guetteur (classe Guetteur, un fil à part, un tour par seconde)"),
            ("ul", [
                "Il lit la fin des journaux de Claude Code (`~/.claude/projects/*/*.jsonl`, et `subagents/` pour les "
                "sous-agents) : la classe `Session` y suit les outils, les fichiers touchés, les fins de tour, les "
                "questions, les messages de l'utilisateur et les liens cités.",
                "Il lit les demandes, les signaux, les fermetures, et les fiches de l'app Claude "
                "(`%APPDATA%\\Claude\\claude-code-sessions`, pour savoir qu'une session est archivée).",
                "Il situe les cibles par l'automatisation de Windows (UIA, module `comtypes`) : les icônes du Bureau "
                "et de l'Explorateur, les boutons d'une fenêtre, la ligne d'une session dans l'app Claude, un bouton de "
                "la barre des tâches.",
                "Il décide le mode de chaque pigeon (`placer`) et dépose le tout dans l'état partagé.",
            ]),
            ("h3", "Les modes et les importances"),
            ("ul", [
                "**Les modes** : `montre` (une demande de `montre.py`), `appel` puis `attend` (une session attend "
                "l'utilisateur), `pose` (sur l'icône du fichier où elle travaille), `perche` (cette icône est cachée), "
                "`parc` (pas de fichier), `repos` (2 min sans outil) ; côté affichage, `pause` et `merci`.",
                "**Les importances** : `bloquee` (une permission, par le crochet), `haute` (un geste demandé), "
                "`normale` (une question posée), `basse` (une fin de tour).",
                "**Une session fermée** (`Session.est_fermee`) : un fichier dans `fermetures\\`, ou archivée dans "
                "l'app. Elle se rouvre si l'utilisateur lui écrit, si elle demande une permission ou un geste, ou si "
                "elle relance un outil plus de 2 min après.",
            ]),
            ("h3", "L'affichage (classe Volee, le fil de Tk, 30 images par seconde)"),
            ("ul", [
                "Chaque pigeon, flèche, encadré et bulle est une petite fenêtre transparente qu'on déplace (une toile "
                "plein écran coûtait 13 % d'un cœur).",
                "Les lignes pointillées sont des fenêtres en couches (classe `Voile`, `UpdateLayeredWindow`) : chaque "
                "point a sa propre transparence ; elles ne couvrent que la boîte des lignes et ne se redessinent que si "
                "quelque chose bouge.",
                "`chemin()` donne le trajet (droite, arc, sinueuse, en vol) ; `points_de_ligne()` y pose les points à "
                "intervalles réguliers ; `tracer_lignes()` fait le tracé en 250 ms et les animations.",
                "`guider_attente()` pose les encadrés, les étiquettes et les lignes vers les sessions qui attendent ; "
                "`guetter_clic()` reconnaît le clic sur l'endroit montré ; la classe `Raccourci` (un fil) reçoit "
                "Ctrl+Alt+P et Ctrl+Alt+T.",
            ]),
            ("h3", "Le panneau (classe Panneau)"),
            ("ul", [
                "Les onglets « À faire » et « Guide », les cartes, les infobulles (classe `Infobulle`), et la fenêtre "
                "des réglages (`Volee.ouvrir_reglages`). Il ne se refait que si son contenu change.",
                "La langue : le français est écrit dans le code ; `tr()` le traduit avec la table `ANGLAIS` ; le guide "
                "a ses deux versions dans `contenu_guide()`.",
                "Le journal d'erreurs : `preuve_pigeons.log`, 1 Mo au plus, puis trois copies.",
                "Mesuré : environ 4,6 % d'un cœur sans lignes, 7,2 % avec.",
            ]),
        ],
        "h_fichiers": "7. Les fichiers du dossier",
        "colonnes_fichiers": ["Fichier", "Rôle"],
        "fichiers": [
            ("preuve_pigeons.py", "le programme entier"),
            ("montre.py", "la commande qu'une session lance pour montrer un geste"),
            ("crochet_notification.py", "reçoit les notifications de Claude Code (permissions) et les dépose dans signaux\\"),
            ("faire_manuel.py", "fabrique ce manuel"),
            ("annonce.py", "une autre IA dit où elle travaille, ou demande qui travaille quelque part (section 5.4)"),
            ("activite.json, annonces\\", "le registre de qui travaille où, et les annonces des autres IA"),
            ("pixellab.py", "les images des pigeons en pixel art, par PixelLab (pas encore essayé : il manque la clé)"),
            ("Lancer la preuve.bat", "lance les pigeons"),
            ("Ranger la clé PixelLab.bat", "range la clé PixelLab de l'utilisateur dans cle_pixellab.txt"),
            ("reglages.json", "les réglages de l'utilisateur : ne jamais les écraser"),
            ("couleurs.json", "la couleur fixe de chaque session"),
            ("demandes\\, signaux\\, fermetures\\", "les fichiers d'échange (section 5.2)"),
            ("preuve_pigeons.log", "le journal d'erreurs"),
            ("MANUEL.md, MANUEL.docx, MANUAL.md, MANUAL.docx", "ce manuel, en français et en anglais"),
            ("PASSATION.md", "la page de reprise : comment c'est fait, où toucher, la suite"),
            ("IDEES.md", "les idées triées, avec leur coût"),
            ("MANUEL.md", "l'histoire complète, avec les heures et les choix de l'utilisateur"),
            ("PROMPT_PROCHAINE_SESSION.txt", "l'invite à coller pour reprendre dans une session neuve"),
            ("EVALUATION_POUR_AG.md, EVALUATION_ET_RECOMMANDATIONS_AG.md, VERIFICATION_DU_RAPPORT_AG.md",
             "l'évaluation par une autre IA (Antigravity) et sa vérification"),
            ("modele\\", "l'image modèle des pigeons en pixel art"),
        ],
        "h_pieges": "8. Les pièges connus",
        "pieges": [
            ("ul", [
                "**`reglages.json`** : arrêter le programme avant d'y écrire, sinon il réécrit par-dessus. Ce sont les "
                "réglages de l'utilisateur.",
                "**Ne jamais nommer une fonction `t()`** : des variables locales s'appellent `t` (le haut d'une fenêtre).",
                "**Les fenêtres en couches** : ni `-alpha` ni `-transparentcolor` de Tk sur une `Voile` (ils empêchent "
                "`UpdateLayeredWindow`).",
                "**Les pixels physiques partout** (`SetProcessDpiAwarenessContext(-4)`) : un écran peut être à 125 %.",
                "**UIA est par fil** : le guetteur a la sienne, l'affichage aussi.",
                "**Le panneau se reconnaît** à sa classe `TkTopLevel`, à son titre « Pigeons » et au fait qu'il n'est "
                "pas une fenêtre outil.",
                "**Capturer les lignes** : `ImageGrab.grab(all_screens=True, include_layered_windows=True)`, sinon "
                "elles n'apparaissent pas.",
                "**Créer les toiles des lignes prend environ 0,45 s** : une ligne se redessine jusqu'à avoir été "
                "dessinée en entier une fois.",
                "**Arrêter seulement les pigeons**, pas tous les `pythonw` : filtrer sur la ligne de commande "
                "`preuve_pigeons.py`.",
                "**Les fiches de l'app Claude** sont internes et non documentées : elles peuvent changer.",
                "**Les heures** se lisent dans les journaux ou par un outil, jamais de tête.",
            ]),
        ],
        "h_prive": "9. Vie privée",
        "prive": [
            ("p", "Tout reste sur l'ordinateur. Les pigeons lisent les journaux de Claude Code et les fiches de l'app, "
                  "sans rien y écrire ; ils n'envoient rien sur le réseau et n'ont aucune télémétrie. Ils n'écrivent que "
                  "dans leur dossier (réglages, couleurs, demandes, signaux, fermetures, journal) et, si on le demande, "
                  "un raccourci dans le dossier Démarrage."),
        ],
        "h_suite": "10. Continuer le travail",
        "suite": [
            ("ul", [
                "**Lire dans l'ordre** : `PASSATION.md` (la page de reprise), `IDEES.md` (les idées et leur coût), "
                "`MANUEL.md` (l'histoire, avec les heures), puis le code par morceaux.",
                "**Essayer sans fenêtre** : `python preuve_pigeons.py --texte`.",
                "**Essayer avec des fenêtres sans toucher aux réglages** : dans un script, `P.Guetteur.run = lambda "
                "self: None`, `P.Raccourci.run = lambda self: None` et `P.sauver_reglages = lambda r: None`, puis "
                "remplir `v.partage` avec un faux état. Les fenêtres d'essai vont sur l'écran du bas.",
                "**Relancer** : arrêter le `pythonw` dont la ligne de commande contient `preuve_pigeons.py`, puis "
                "`pythonw preuve_pigeons.py`.",
                "**Après un changement** : tenir à jour `contenu_guide()` (l'onglet Guide), la table `ANGLAIS` et "
                "`PASSATION.md`, puis relancer `python faire_manuel.py`.",
                "**Les règles de l'utilisateur** : ne jamais écraser `reglages.json` ; ne jamais lire un "
                "fichier `cle_*` ; des réponses courtes, le verdict d'abord ; lire l'heure avec un outil.",
                "**La suite recommandée** : en tête de `IDEES.md` (la carte de passation, le retour au poste, le mode "
                "perchoir) ; pour l'open source, découper en modules, des essais, une licence MIT, un exécutable "
                ".",
            ]),
        ],
    },
    "en": {
        "titre": "Pigeons: the manual",
        "sous_titre": "The guidance system for working with AI sessions · version of {d}",
        "h_lecteurs": "1. Who this manual is for",
        "lecteurs": [
            ("ul", [
                "**If you use it**: sections 2 to 4 (launching, using the pigeons, settings).",
                "**If you take over the work, as a person or an AI**: sections 5 to 10 (AIs and `montre.py`, how it "
                "works inside, files, pitfalls, privacy, how to continue).",
                "This manual is built by `faire_manuel.py` from the code: the settings list and the guide are always "
                "accurate. After changing the app, run `python faire_manuel.py` again.",
            ]),
        ],
        "h_lancer": "2. Installing and launching",
        "lancer": [
            ("ul", [
                "**Requirements**: Windows 10 or 11; Python 3.11 or newer (tested with 3.13); the modules `comtypes`, "
                "`pywin32` and `Pillow`: `python -m pip install --user comtypes pywin32 pillow`.",
                "**Launch**: double-click `Lancer la preuve.bat`, or run `pythonw preuve_pigeons.py` in the folder. "
                "Only one copy runs at a time (a Windows mutex): launching again brings the panel to the front.",
                "**With Windows**: the “Start the pigeons with Windows” box puts a shortcut in the Windows Startup "
                "folder.",
                "**Stop**: the panel's “Quit” button. The window's ✕ only minimizes the panel; the pigeons keep going.",
                "**Check without windows**: `python preuve_pigeons.py --texte` prints each pigeon's state.",
                "**See permissions to give** (optional): a Claude Code “Notification” hook in `~/.claude/settings.json`, "
                "with the matcher `permission_prompt|elicitation_dialog|elicitation_url_dialog|agent_needs_input` and "
                "the command `python \"<folder>\\crochet_notification.py\"`.",
            ]),
        ],
        "h_guide": "3. Using the pigeons",
        "guide_intro": "The same text as the panel's “Guide” tab.",
        "h_reglages": "4. All settings",
        "reglages_intro": "The panel's “Settings” button opens the settings window, in the style of Claude's "
                          "settings: on the left, a search box and the categories (guidance: Guidance, Lines, Frames; "
                          "the app: Appearance, Pigeons, General); on the right, their sections. The search shows the "
                          "sections of every category that contain the typed word. Every change applies at once and "
                          "is kept in `reglages.json`. “Reset to defaults” keeps the "
                          "language, the panel's place and the Windows startup.",
        "colonnes_reglages": ["Setting", "Possible values", "Default", "Key in reglages.json"],
        "oui": "yes", "non": "no", "couleur": "a color", "de_a": "from {a} to {b}", "case": "yes or no",
        "notes": "Good to know",
        "h_internes": "Settings kept by the program",
        "internes_intro": "They are not in the window: the program keeps them by itself (the panel's place), or they "
                          "remain from an older version, to read old files. Don't change them by hand.",
        "h_ia": "5. For AIs and scripts",
        "h_montre": "5.1 Showing an action: montre.py",
        "montre_intro": "A session that needs an action from the user runs, for example:",
        "montre_exemple": 'python "%USERPROFILE%\\Desktop\\Pigeons\\montre.py" --texte "Click Accept" '
                          '--fenetre "Chrome" --element "Accept"',
        "colonnes_montre": ["Option", "What it does"],
        "montre": [
            ("--texte TEXT", "the instruction, in one sentence"),
            ("--fichier PATH", "an icon on the Desktop or in an open folder"),
            ("--fenetre TITLE --element NAME", "a button, link or box in a window, by part of its name (read by "
                                               "Windows UI Automation); with --fenetre \"Pigeons\", a panel button "
                                               "(“Réglages”, “Guide”...)"),
            ("--point X Y", "a point on the screen, in physical pixels"),
            ("--vers-fichier, --vers-fenetre, --vers-element, --vers-point", "the end of a drag"),
            ("--puis-fichier, --puis-fenetre, --puis-element, --puis-point, --puis-texte",
             "a second step (“click here, then there”): frames numbered 1 and 2"),
            ("--importance haute|normale|basse", "high (haute) by default"),
            ("--minutes N", "how long the request lasts (15 by default); it also ends at the user's next message to "
                            "the session"),
            ("--fin", "clears the request at once"),
            ("--termine", "the session is finished: its pigeon, card and lines go away (run it last, just before "
                          "the final answer)"),
            ("--session NAME, --titre NAME", "for another AI without a Claude Code log; by default the session is "
                                             "read from the CLAUDE_CODE_SESSION_ID variable"),
        ],
        "h_formats": "5.2 Exchange files (JSON)",
        "formats": [
            ("ul", [
                "**`demandes\\<session>.json`** (written by `montre.py`): `session`, `heure`, `duree_s`, `texte`, "
                "`cible`, `vers`, `puis`, `texte_puis`, `titre`, `importance`. A target is `{\"fichier\": path}`, "
                "`{\"fenetre\": title, \"element\": name}` or `{\"point\": [x, y]}`.",
                "**`signaux\\<session>.json`** (written by `crochet_notification.py`): `session`, `type` "
                "(`permission_prompt`, `elicitation_dialog`, `elicitation_url_dialog`, `agent_needs_input`), "
                "`message`, `heure`. Cleared as soon as the session moves on.",
                "**`fermetures\\<session>.json`**: `session`, `heure`, `par` (`danny` or `session`). Forgotten after "
                "3 days, or as soon as the session moves on.",
                "**`demandes\\_vivant.txt`**: the time of the last round; `montre.py` uses it to see whether the "
                "pigeons are running.",
                "Each file is first written next to its place, then renamed: the program never reads a half-written "
                "file.",
            ]),
        ],
        "h_regles": "5.3 Rules given to Claude sessions",
        "regles": [
            ("p", "In `Desktop\\CLAUDE.md`, which every session launched on the Desktop reads:"),
            ("ul", [
                "show every action asked of the user with `montre.py`;",
                "run `montre.py --termine` at the end of the handoff;",
                "write the links and paths of deliverables in full: the panel offers them (Copy, Open, Show).",
            ]),
            ("p", "Another AI (Cowork, Gemini, a script) passes `--session name --titre \"Name\"`, or writes the "
                  "request file itself; its pigeon lives as long as its request exists."),
        ],
        "h_coord": "5.4 Coordinating AIs: activite.json and annonce.py",
        "coord": [
            ("p", "So that two AIs don't write the same file at the same time (l'utilisateur, October 3, 2026):"),
            ("ul", [
                "**The registry** `activite.json`: every 2 s the pigeons write who works where (session, tool, file, "
                "project folder, state, files written in the last 10 min) and the conflicts. For an AI that made a "
                "request, `demande.trouvee` says whether its target was found on screen, and `demande.precision` why "
                "not. Claude Code sessions are "
                "in it on their own, from their logs.",
                "**Announcing** (another AI): `python annonce.py --session ag --titre \"AG\" --ia Antigravity "
                "--fichier PATH --ecrit`; or `--dossier PATH`; `--fin` at the end. The announcement lasts 10 min "
                "(`--minutes`): announce again when changing files.",
                "**Asking before writing**: `python annonce.py --qui PATH --session ag`. Exit code 0: free (with a "
                "warning if another AI works in the same folder); 1: occupied (another AI wrote this file in the last "
                "10 min, or works on it); 2: unknown (the pigeons are not running).",
                "**Conflicts**: two AIs writing the same file less than 5 min apart bring up a banner at the top of the "
                "panel.",
                "**The limit**: only Claude Code sessions are followed without doing anything; other AIs rely on good "
                "will (announce, ask). A hook that would stop a Claude Code write to an occupied file is an idea "
                ", not installed yet.",
            ]),
        ],
        "h_dedans": "6. How it works inside",
        "dedans": [
            ("p", "Everything is in `preuve_pigeons.py` (about {n} lines), in three parts that talk through a shared "
                  "state."),
            ("h3", "The watcher (Guetteur class, its own thread, one round per second)"),
            ("ul", [
                "It reads the end of Claude Code's logs (`~/.claude/projects/*/*.jsonl`, and `subagents/` for "
                "sub-agents): the `Session` class follows tools, touched files, finished turns, questions, the user's "
                "messages and the links mentioned.",
                "It reads requests, signals, closings, and the Claude app's session files "
                "(`%APPDATA%\\Claude\\claude-code-sessions`, to know a session is archived).",
                "It locates targets with Windows UI Automation (UIA, `comtypes` module): Desktop and Explorer icons, "
                "a window's buttons, a session's row in the Claude app, a taskbar button.",
                "It decides each pigeon's mode (`placer`) and puts everything in the shared state.",
            ]),
            ("h3", "Modes and importances"),
            ("ul", [
                "**Modes**: `montre` (a `montre.py` request), `appel` then `attend` (a session waits for the user), "
                "`pose` (on the icon of the file it works on), `perche` (that icon is hidden), `parc` (no file), "
                "`repos` (2 min without a tool); on the display side, `pause` and `merci`.",
                "**Importances**: `bloquee` (a permission, from the hook), `haute` (a requested action), `normale` "
                "(a question), `basse` (a finished turn).",
                "**A closed session** (`Session.est_fermee`): a file in `fermetures\\`, or archived in the app. It "
                "reopens if the user writes to it, if it asks for a permission or an action, or if it runs a tool "
                "more than 2 min later.",
            ]),
            ("h3", "The display (Volee class, the Tk thread, 30 frames per second)"),
            ("ul", [
                "Each pigeon, arrow, frame and bubble is a small transparent window that is moved around (a "
                "full-screen canvas cost 13 % of a core).",
                "The dotted lines are layered windows (`Voile` class, `UpdateLayeredWindow`): each dot has its own "
                "transparency; they only cover the lines' bounding box and are redrawn only when something moves.",
                "`chemin()` gives the path (straight, arc, wavy, flight); `points_de_ligne()` places the dots at even "
                "intervals along it; `tracer_lignes()` handles the 250 ms trace and the animations.",
                "`guider_attente()` places the frames, labels and lines toward waiting sessions; `guetter_clic()` "
                "detects the click on the shown spot; the `Raccourci` class (a thread) receives Ctrl+Alt+P and "
                "Ctrl+Alt+T.",
            ]),
            ("h3", "The panel (Panneau class)"),
            ("ul", [
                "The “To do” and “Guide” tabs, the cards, the tooltips (`Infobulle` class), and the settings window "
                "(`Volee.ouvrir_reglages`). It is rebuilt only when its content changes.",
                "Language: French is written in the code; `tr()` translates it with the `ANGLAIS` table; the guide "
                "has both versions in `contenu_guide()`.",
                "The error log: `preuve_pigeons.log`, 1 MB at most, then three copies.",
                "Measured: about 4.6 % of a core without lines, 7.2 % with them.",
            ]),
        ],
        "h_fichiers": "7. Files in the folder",
        "colonnes_fichiers": ["File", "Role"],
        "fichiers": [
            ("preuve_pigeons.py", "the whole program"),
            ("montre.py", "the command a session runs to show an action"),
            ("crochet_notification.py", "receives Claude Code notifications (permissions) and drops them in signaux\\"),
            ("faire_manuel.py", "builds this manual"),
            ("annonce.py", "another AI says where it works, or asks who works somewhere (section 5.4)"),
            ("activite.json, annonces\\", "the registry of who works where, and other AIs' announcements"),
            ("pixellab.py", "pixel-art pigeon images from PixelLab (not tried yet: the key is missing)"),
            ("Lancer la preuve.bat", "launches the pigeons"),
            ("Ranger la clé PixelLab.bat", "stores the user's PixelLab key in cle_pixellab.txt"),
            ("reglages.json", "the user's settings: never overwrite them"),
            ("couleurs.json", "each session's fixed color"),
            ("demandes\\, signaux\\, fermetures\\", "the exchange files (section 5.2)"),
            ("preuve_pigeons.log", "the error log"),
            ("MANUEL.md, MANUEL.docx, MANUAL.md, MANUAL.docx", "this manual, in French and English"),
            ("PASSATION.md", "the handoff page: how it's built, where to change things, what's next"),
            ("IDEES.md", "the sorted ideas, with their cost"),
            ("MANUEL.md", "the full history, with times and the user's choices (in French)"),
            ("PROMPT_PROCHAINE_SESSION.txt", "the prompt to paste to resume in a fresh session"),
            ("EVALUATION_POUR_AG.md, EVALUATION_ET_RECOMMANDATIONS_AG.md, VERIFICATION_DU_RAPPORT_AG.md",
             "the evaluation by another AI (Antigravity) and its verification"),
            ("modele\\", "the reference image for the pixel-art pigeons"),
        ],
        "h_pieges": "8. Known pitfalls",
        "pieges": [
            ("ul", [
                "**`reglages.json`**: stop the program before writing to it, or it writes over your changes. These are "
                "the user's settings.",
                "**Never name a function `t()`**: local variables are called `t` (a window's top).",
                "**Layered windows**: no Tk `-alpha` or `-transparentcolor` on a `Voile` (they prevent "
                "`UpdateLayeredWindow`).",
                "**Physical pixels everywhere** (`SetProcessDpiAwarenessContext(-4)`): a screen may be at 125 %.",
                "**UIA is per thread**: the watcher has its own, the display too.",
                "**The panel is recognized** by its `TkTopLevel` class, its “Pigeons” title, and not being a tool "
                "window.",
                "**Capturing the lines**: `ImageGrab.grab(all_screens=True, include_layered_windows=True)`, or they "
                "don't show.",
                "**Creating the line canvases takes about 0.45 s**: a line is redrawn until it has been drawn in full "
                "once.",
                "**Stop only the pigeons**, not every `pythonw`: filter on the `preuve_pigeons.py` command line.",
                "**The Claude app's session files** are internal and undocumented: they may change.",
                "**Times** are read in the logs or with a tool, never guessed.",
            ]),
        ],
        "h_prive": "9. Privacy",
        "prive": [
            ("p", "Everything stays on the computer. The pigeons read Claude Code's logs and the app's session files "
                  "without writing to them; they send nothing over the network and have no telemetry. They write only "
                  "in their own folder (settings, colors, requests, signals, closings, log) and, if asked, a shortcut "
                  "in the Startup folder."),
        ],
        "h_suite": "10. Continuing the work",
        "suite": [
            ("ul", [
                "**Read in this order**: `PASSATION.md` (the handoff page), `IDEES.md` (ideas and their cost), "
                "`MANUEL.md` (the history, with times), then the code piece by piece. These files are in French.",
                "**Try without windows**: `python preuve_pigeons.py --texte`.",
                "**Try with windows without touching the settings**: in a script, `P.Guetteur.run = lambda self: "
                "None`, `P.Raccourci.run = lambda self: None` and `P.sauver_reglages = lambda r: None`, then fill "
                "`v.partage` with a fake state. Test windows go on the bottom screen.",
                "**Restart**: stop the `pythonw` whose command line contains `preuve_pigeons.py`, then run "
                "`pythonw preuve_pigeons.py`.",
                "**After a change**: keep `contenu_guide()` (the Guide tab), the `ANGLAIS` table and `PASSATION.md` up "
                "to date, then run `python faire_manuel.py` again.",
                "**The user's rules**: never overwrite `reglages.json`; never read a `cle_*` file; short "
                "answers, verdict first; read the time with a tool.",
                "**Recommended next steps**: at the top of `IDEES.md` (the handoff card, back-at-the-desk summary, "
                "perch mode); for open source, split into modules, tests, an MIT license, an executable.",
            ]),
        ],
    },
}


# ----------------------------------------------------------------- ce qui se lit dans le code

def lire_reglages_de_la_fenetre():
    """Les cartes de la fenêtre des réglages, dans l'ordre : [(titre, [(genre, clé, libellé, choix), ...], [notes])].
    Lu dans le code de Volee.ouvrir_reglages (ast) : ce que l'utilisateur voit, exactement."""
    source = textwrap.dedent(inspect.getsource(P.Volee.ouvrir_reglages))
    arbre = ast.parse(source)
    appels = sorted((n for n in ast.walk(arbre) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)),
                    key=lambda n: (n.lineno, n.col_offset))
    cartes, par_variable = [], {}
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "carte"):
            par_variable[n.targets[0].id] = n.value
    ordre_cartes = sorted(par_variable.items(), key=lambda kv: kv[1].lineno)
    index = {}
    for variable, appel in ordre_cartes:
        index[variable] = len(cartes)
        cartes.append((ast.literal_eval(appel.args[1]), [], []))
    for a in appels:
        nom = a.func.id
        if nom not in ("choix", "choix_en_ligne", "case", "glissiere", "couleur", "note") or not a.args:
            continue
        if not isinstance(a.args[0], ast.Name) or a.args[0].id not in index:
            continue
        carte = cartes[index[a.args[0].id]]
        if nom == "note":
            carte[2].append(ast.literal_eval(a.args[1]))
        elif nom in ("choix", "choix_en_ligne"):
            carte[1].append(("choix", ast.literal_eval(a.args[1]), None, ast.literal_eval(a.args[2])))
        elif nom == "case":
            carte[1].append(("case", ast.literal_eval(a.args[1]), ast.literal_eval(a.args[2]), None))
        elif nom == "glissiere":
            carte[1].append(("glissiere", ast.literal_eval(a.args[1]), ast.literal_eval(a.args[2]),
                             (ast.literal_eval(a.args[3]), ast.literal_eval(a.args[4]))))
        elif nom == "couleur":
            carte[1].append(("couleur", ast.literal_eval(a.args[1]), ast.literal_eval(a.args[2]), None))
    return cartes


def en(texte, langue):
    return P.ANGLAIS.get(texte, texte) if langue == "en" else texte


def blocs_reglages(langue, T):
    """La section 4 : un tableau par carte, puis les réglages gardés par le programme."""
    blocs, vus = [], set()
    for titre, reglages, notes in lire_reglages_de_la_fenetre():
        lignes = []
        for genre, cle, libelle, choix in reglages:
            vus.add(cle)
            defaut = P.REGLAGES_DEFAUT.get(cle)
            if genre == "choix":
                options = [en(t, langue) for _v, t in choix]
                valeurs = " ; ".join(options)
                defaut_lu = next((en(t, langue) for v, t in choix if v == defaut), str(defaut))
                libelle = libelle_choix(cle, langue)
            elif genre == "case":
                valeurs, defaut_lu = T["case"], T["oui"] if defaut else T["non"]
                libelle = en(libelle, langue)
            elif genre == "glissiere":
                valeurs, defaut_lu = T["de_a"].format(a=choix[0], b=choix[1]), str(defaut)
                libelle = en(libelle, langue)
            else:
                valeurs, defaut_lu = T["couleur"], str(defaut)
                libelle = en(libelle, langue)
            lignes.append([libelle, valeurs, defaut_lu, f"`{cle}`"])
        blocs.append(("h3", en(titre, langue)))
        blocs.append(("table", T["colonnes_reglages"], lignes, [1.9, 2.6, 1.2, 1.3]))
        if notes:
            blocs.append(("ul", [en(n, langue) for n in notes]))
    internes = [k for k in P.REGLAGES_DEFAUT if k not in vus]
    blocs.append(("h3", T["h_internes"]))
    blocs.append(("p", T["internes_intro"]))
    blocs.append(("ul", [f"`{k}` : `{P.REGLAGES_DEFAUT[k]!r}`" if langue == "fr" else f"`{k}`: `{P.REGLAGES_DEFAUT[k]!r}`"
                         for k in internes]))
    return blocs


# Le titre d'un groupe de choix : le sous-titre qui le précède dans la fenêtre, ou un nom écrit ici.
NOMS_DES_CHOIX = {
    "langue": "Langue", "ancrer_claude": "Le panneau", "guidage": "Guidage vers ce que tu as à faire",
    "infos_ecran": "Infos à l'écran", "lignes_reponse": "Ligne vers une session qui attend ma réponse",
    "lignes_style": "Style", "lignes_forme": "Forme", "lignes_animation": "Animation continue",
    "lignes_couleur": "Couleur des lignes", "encadres": "Encadrés", "encadres_style": "Style",
    "cible_cachee": "Quand une fenêtre cache l'icône où il travaille",
    "lignes_travail": "Ligne vers l'endroit exact où il travaille", "couleur_guides": "Couleur des guides",
    "bulles": "Bulles", "theme": "Thème", "theme_sombre": "Thème sombre", "contraste": "Contraste",
    "bulles_couleurs": "Bulles et étiquettes",
}


def libelle_choix(cle, langue):
    return en(NOMS_DES_CHOIX.get(cle, cle), langue)


def blocs_guide(langue, T):
    """La section 3 : le texte de l'onglet « Guide » (contenu_guide), dans la langue voulue."""
    avant = P.LANGUE
    P.LANGUE = langue
    try:
        sections = P.contenu_guide()
    finally:
        P.LANGUE = avant
    blocs = [("p", T["guide_intro"])]
    noms = {"bloquee": "Bloquée : une permission à donner", "haute": "Haute : un geste à faire",
            "normale": "Normale : une question posée", "basse": "Basse : à toi quand tu veux"}
    for s in sections:
        blocs.append(("h3", s["titre"]))
        if s.get("couleurs"):
            blocs.append(("ul", [f"{en(noms[i], langue)} ({P.REGLAGES_DEFAUT['couleur_' + i]})" for i in noms]))
        puces, paragraphes = [], []
        for t in s["texte"]:
            if t.startswith("•"):
                puces += [x.strip(" •") for x in t.split("   •")]
            else:
                if puces:
                    blocs.append(("ul", puces))
                    puces = []
                blocs.append(("p", t))
        if puces:
            blocs.append(("ul", puces))
    return blocs


def assembler(langue):
    """Toute la suite des blocs du manuel, dans une langue."""
    T = TEXTES[langue]
    n = sum(1 for _ in open(ICI / "preuve_pigeons.py", encoding="utf-8"))
    n = round(n, -2)
    d = date.today().isoformat()
    b = [("titre", T["titre"]), ("sous_titre", T["sous_titre"].format(d=d))]
    b += [("h1", T["h_lecteurs"])] + T["lecteurs"]
    b += [("h1", T["h_lancer"])] + T["lancer"]
    b += [("h1", T["h_guide"])] + blocs_guide(langue, T)
    b += [("h1", T["h_reglages"]), ("p", T["reglages_intro"])] + blocs_reglages(langue, T)
    b += [("h1", T["h_ia"]), ("h2", T["h_montre"]), ("p", T["montre_intro"]), ("code", T["montre_exemple"]),
          ("table", T["colonnes_montre"], [[f"`{o}`", t] for o, t in T["montre"]], [2.8, 4.2])]
    b += [("h2", T["h_formats"])] + T["formats"]
    b += [("h2", T["h_regles"])] + T["regles"]
    b += [("h2", T["h_coord"])] + T["coord"]
    b += [("h1", T["h_dedans"])] + [(g, *(x.format(n=n) if isinstance(x, str) else x for x in reste))
                                     for g, *reste in T["dedans"]]
    b += [("h1", T["h_fichiers"]), ("table", T["colonnes_fichiers"], [[f"`{f}`", r] for f, r in T["fichiers"]],
                                     [2.8, 4.2])]
    b += [("h1", T["h_pieges"])] + T["pieges"]
    b += [("h1", T["h_prive"])] + T["prive"]
    b += [("h1", T["h_suite"])] + T["suite"]
    return b


# ----------------------------------------------------------------- l'écriture : Markdown et Word

def en_markdown(blocs):
    lignes = []
    for g, *r in blocs:
        if g == "titre":
            lignes += [f"# {r[0]}", ""]
        elif g == "sous_titre":
            lignes += [f"*{r[0]}*", ""]
        elif g == "h1":
            lignes += [f"## {r[0]}", ""]
        elif g == "h2":
            lignes += [f"### {r[0]}", ""]
        elif g == "h3":
            lignes += [f"#### {r[0]}", ""]
        elif g == "p":
            lignes += [r[0], ""]
        elif g == "ul":
            lignes += [f"- {x}" for x in r[0]] + [""]
        elif g == "code":
            lignes += ["```", r[0], "```", ""]
        elif g == "table":
            entetes, rangs = r[0], r[1]
            lignes.append("| " + " | ".join(entetes) + " |")
            lignes.append("|" + "---|" * len(entetes))
            for rang in rangs:
                lignes.append("| " + " | ".join(str(c).replace("|", "\\|") for c in rang) + " |")
            lignes.append("")
    return "\n".join(lignes)


def en_word(blocs, chemin):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)       # le format Lettre, celui du Québec
    for cote in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, cote, Inches(0.75))
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Segoe UI", Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Segoe UI")

    def ombrer(element, couleur):
        proprietes = element.get_or_add_tcPr() if element.tag.endswith("tc") else element.get_or_add_pPr()
        ombre = OxmlElement("w:shd")
        ombre.set(qn("w:val"), "clear")
        ombre.set(qn("w:color"), "auto")
        ombre.set(qn("w:fill"), couleur)
        proprietes.append(ombre)

    def ecrire(paragraphe, texte, taille=None):
        """Le texte, avec le **gras** et le `code` du Markdown."""
        for morceau in re.split(r"(\*\*.+?\*\*|`[^`]+`)", texte):
            if not morceau:
                continue
            if morceau.startswith("**") and morceau.endswith("**"):
                interieur = morceau[2:-2]
                for sous in re.split(r"(`[^`]+`)", interieur):
                    if not sous:
                        continue
                    run = paragraphe.add_run(sous.strip("`"))
                    run.bold = True
                    if sous.startswith("`"):
                        run.font.name = "Consolas"
            elif morceau.startswith("`"):
                run = paragraphe.add_run(morceau[1:-1])
                run.font.name = "Consolas"
                run.font.size = Pt(9)
            else:
                run = paragraphe.add_run(morceau)
            if taille:
                run.font.size = Pt(taille)

    for g, *r in blocs:
        if g == "titre":
            doc.add_heading(r[0], level=0)
        elif g == "sous_titre":
            p = doc.add_paragraph()
            run = p.add_run(r[0])
            run.italic = True
            run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
        elif g in ("h1", "h2", "h3"):
            doc.add_heading(r[0], level={"h1": 1, "h2": 2, "h3": 3}[g])
        elif g == "p":
            ecrire(doc.add_paragraph(), r[0])
        elif g == "ul":
            for x in r[0]:
                ecrire(doc.add_paragraph(style="List Bullet"), x)
        elif g == "code":
            p = doc.add_paragraph()
            run = p.add_run(r[0])
            run.font.name, run.font.size = "Consolas", Pt(9)
            ombrer(p._p, "F2F2F2")
        elif g == "table":
            entetes, rangs, largeurs = r[0], r[1], r[2]
            t = doc.add_table(rows=1, cols=len(entetes))
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            for i, h in enumerate(entetes):
                cellule = t.rows[0].cells[i]
                cellule.text = ""
                run = cellule.paragraphs[0].add_run(h)
                run.bold = True
                run.font.size = Pt(9)
                ombrer(cellule._tc, "DCE6F2")
            for rang in rangs:
                cellules = t.add_row().cells
                for i, valeur in enumerate(rang):
                    cellules[i].text = ""
                    ecrire(cellules[i].paragraphs[0], str(valeur), taille=9)
            for rang in t.rows:
                for i, cellule in enumerate(rang.cells):
                    cellule.width = Inches(largeurs[i])
            doc.add_paragraph()
    doc.save(chemin)


def main():
    for langue, nom in (("fr", "MANUEL"), ("en", "MANUAL")):
        blocs = assembler(langue)
        (ICI / f"{nom}.md").write_text(en_markdown(blocs), encoding="utf-8")
        en_word(blocs, ICI / f"{nom}.docx")
        print(f"{nom}.md et {nom}.docx écrits")


if __name__ == "__main__":
    main()
