"""
preuve_pigeons.py : la preuve du « pigeon par session Claude ».

Ce qu'il fait : lit en direct les journaux des sessions Claude Code
(%USERPROFILE%\\.claude\\projects\\...\\*.jsonl), trouve le fichier que chaque
session touche, cherche l'icône de ce fichier sur le Bureau ou dans un dossier
ouvert de l'Explorateur, et y pose un pigeon (pour l'instant, un point de couleur).
Chaque sous-agent est un pigeonneau de la couleur de son parent.
Une session peut aussi demander à son pigeon de MONTRER un endroit à l'utilisateur
(montre.py) : le pigeon y vole, une flèche pointe l'endroit, une bulle dit quoi
faire, et une petite flèche près de la souris indique la direction.

Qui s'en sert : l'utilisateur, par « Lancer la preuve.bat ». Le programme lit les
journaux sans y toucher ; il n'écrit que dans son dossier (son journal d'erreurs,
les demandes de montre.py qu'il range quand elles sont finies).
Essai sans fenêtre (pour Claude) : python preuve_pigeons.py --texte

Où lire la suite : MANUEL.md (l'idée, les choix de l'utilisateur, le plan de la V1).
"""

import ctypes
import ctypes.wintypes as W

# Les pixels physiques partout : sans ça, Windows « agrandit » l'écran du bas
# (125 %) et les positions lues ne tombent plus sur les icônes.
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

import json
import logging
import math
import os
import re
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
DEMANDES = ICI / "demandes"          # les demandes de montre.py, une par session
FERMETURES = ICI / "fermetures"      # les sessions fermées (« Terminer », montre.py --termine), une par session
# La coordination des IA (l'utilisateur, 3 octobre 09h12 : « que les sessions et les IA voient qui travaille dans un dossier ou
# un fichier, pour éviter les conflits d'écriture ») : les annonces des autres IA (annonce.py), et le registre que les
# pigeons écrivent pour toutes (qui travaille où).
ANNONCES = ICI / "annonces"
ACTIVITE = ICI / "activite.json"
# La relance sûre (5 octobre 2026, 22h39 : l'affichage a gelé pendant la mise à jour de l'app Claude, Windows a fermé le
# programme, et personne ne l'a su). « Arrêter » laisse ce mot : montre.py et annonce.py ne relancent pas des pigeons
# que l'utilisateur a arrêtés lui-même. L'affichage réécrit _affichage.txt toutes les 2 s (son numéro de processus) : un
# fichier vieux dit qu'il est figé.
ARRET = ICI / "arret_volontaire.json"
AFFICHAGE = DEMANDES / "_affichage.txt"
AFFICHAGE_FIGE_S = 5          # l'affichage sans image depuis 5 s : sa pile va dans le journal (la vraie cause d'un gel)
OUTILS_ECRITURE = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
CONFLIT_S = 300               # deux IA qui écrivent le même fichier à moins de 5 min : conflit possible
PROJETS = Path.home() / ".claude" / "projects"
# Les fiches de session de l'app Claude (trouvées le 2 octobre à 13h03) : « isArchived » y dit qu'une session est
# archivée. Fichiers internes de l'app, non documentés : lus avec prudence.
FICHES_APP = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude-code-sessions"
BUREAU = os.path.normcase(str(Path.home() / "Desktop"))

SESSION_VIVANTE_S = 30 * 60   # journal touché depuis moins de 30 min : la session est là
SOUS_AGENT_VIVANT_S = 3 * 60  # un sous-agent muet depuis 3 min est parti
REPOS_S = 120                 # 2 min sans outil : le pigeon va dormir sur la barre des tâches
APPEL_MAX_S = 60              # au plus 60 s près de la souris ; la durée voulue est un réglage (duree_appel_s)
APPEL_RECALE_PX = 350         # ... et ne se déplace que si la souris s'éloigne de plus de 350 px
GUIDE_PX = 300                # au-delà de 300 px de l'endroit montré, une flèche près de la souris
LECTURE_INITIALE = 512 * 1024 # à la première lecture d'un journal, on ne lit que sa fin
TOUR_S = 1.0                  # le guetteur refait le tour chaque seconde
GUETTEUR_FIGE_S = 30          # sans tour depuis 30 s, le guetteur est figé : sa pile va dans le journal
GUETTEUR_RELANCE_S = 120      # mort, ou figé depuis 2 min : l'affichage relance un guetteur (au plus un par 5 min)
GARDE_ICONES_S = 4.0          # une liste d'icônes lue sert 4 s (relue tout de suite si la fenêtre bouge)
SURVOL_PX = 26                # la souris à moins de 26 px du pigeon : sa bulle s'ouvre
FERMEE_GRACE_S = 120          # une session fermée qui reprend un outil plus de 2 min après se rouvre
LIVRABLES_S = 24 * 3600       # les livrables d'une session qui s'est terminée elle-même restent 24 h, ou jusqu'à « Oublier »
TRACE_S = 0.25                # la ligne qui se dessine à son apparition : 250 ms

# Couleurs des sessions, données dans l'ordre d'arrivée ; la clé de transparence
# (CLE) n'est jamais une couleur de pigeon.
COULEURS = ["#3d8bfd", "#ff8c1a", "#2fbf71", "#e05cff", "#ffd23f", "#20c5d6", "#ff5a5f", "#b08cff"]
CLE = "#ff00fe"

# Les réglages de l'utilisateur (le bouton « Réglages » du panneau, demandé le 2 octobre à 11h13) ; gardés dans reglages.json.
REGLAGES = ICI / "reglages.json"
REGLAGES_DEFAUT = {
    "encadres": "toujours",   # autour des sessions qui t'attendent : toujours | approche | jamais
    "taille_fleche": 23,      # la petite flèche près de la souris, en pixels
    "fleche_attente": True,   # la petite flèche vers la session qui t'attend
    "appel_souris": False,    # le pigeon vient près de la souris quand une session t'attend (l'utilisateur, 12h47 : non,
                              # « les lignes pointillées restent ma préférence, moins fatigant visuellement »)
    "duree_appel_s": 20,      # ... pendant combien de secondes
    "bulles": "courte",       # courte : une ligne quand il montre ou appelle ; survol : seulement au survol
    # La bulle de consigne à côté de l'encadré de la cible (l'utilisateur, 3 octobre 2026, 23h36 : « il y a trop de fois où la
    # bulle cache la cible, et les alentours ») : non par défaut ; la consigne reste dans le panneau (« À faire pour toi »).
    "bulle_cible": False,
    # La balise (l'utilisateur, 5 octobre 2026, 22h57 : « une bulle qui mentionne où exactement », sur la ligne, avant la cible ;
    # elle ne la couvre jamais). Détail : « court » (l'app et l'élément) ou « complet » (avec l'onglet ou le dossier).
    "balise": True,
    "balise_detail": "complet",
    "balise_respire": False,  # le halo qui respire lentement (3 s), comme l'indicateur de Windows-MCP
    "pigeonneaux": True,      # montrer les sous-agents
    "guidage": "fleches",     # fleches : des flèches autour de la souris ; lignes : des pointillés souris -> but
    "fleche_creuse": True,    # les flèches près de la souris : juste le contour (l'utilisateur, 11h28)
    "taille_pigeon": 8,       # le rayon du corps du pigeon, en pixels (les pigeonneaux : 60 %)
    # L'apparence du panneau (l'utilisateur, 3 octobre 09h26 : « améliorer le visuel et l'esthétique, plus agréable, user
    # friendly et paramétrable », avec en exemple les réglages d'Antigravity : thème, contraste, couleurs).
    "theme": "systeme",          # systeme (suit Windows) | clair | sombre
    "theme_sombre": "defaut",    # defaut | nuit | ambre (celui d'Antigravity)
    "contraste": "normal",       # normal | fort
    "theme_perso": False,        # mes couleurs : le fond, le texte et l'accent ci-dessous
    "couleur_fond": "#16171b",
    "couleur_texte": "#e9e9ec",
    "couleur_accent": "#8ab4ff",
    "bulles_couleurs": "papier",  # papier (claires) | theme (aux couleurs du panneau) | sombre (toujours sombres)
    # Les pigeons eux-mêmes (l'utilisateur, 3 octobre 09h07 : « ça ajoute du bruit ; je reste avec les lignes de guidage et
    # les flèches en option ; maintenant que l'app et mes idées ont évolué, ils n'apportent rien ; on garde le nom ») :
    # cachés par défaut. Les lignes, les flèches, les encadrés, les étiquettes et la bulle de consigne restent.
    "afficher_pigeons": False,
    "pigeons_au_travail": True,  # montrer aussi les pigeons des sessions qui travaillent (sinon : ceux qui t'attendent)
    "opacite_bulles": 90,     # en pour cent
    "demarrage_windows": False,  # lancer les pigeons à l'ouverture de la session Windows
    "cible_cachee": "barre",     # quand une fenêtre cache l'icône où il travaille : perche (sur cette fenêtre, comme
                                 # à 09h10) | barre (sur la barre des tâches) | cache (invisible) ; l'utilisateur, 12h54 :
                                 # « visible par-dessus d'autres apps, comme le navigateur »
    "lignes_travail": "survol",  # la ligne du pigeon au travail vers l'endroit exact : survol | toujours | jamais
    "ancrer_claude": "non",      # non | droite | gauche : le panneau collé au bord de la fenêtre de Claude
    "panneau_geometrie": "",     # la place et la taille du panneau (« 600x440+100+200 »), gardées d'une fois à l'autre
    "langue": "en",              # en | fr : l'anglais par défaut (la version publique) ; l'utilisateur a le français
    # Les lignes pointillées (l'utilisateur, 11h40 : « grosseur, distance des pointillés, couleurs »)
    "lignes_style": "points",    # points | tirets
    "lignes_epaisseur": 4,       # le diamètre des points ou l'épaisseur des tirets, en pixels
    "lignes_espacement": 11,     # d'un point (ou d'un tiret) au suivant, en pixels
    "lignes_opacite": 80,        # en pour cent
    "lignes_couleur": "guide",   # guide : la couleur du guide (tâche ou importance) ; unique : une seule couleur
    "lignes_couleur_unique": "#ffffff",
    "report_clic_min": 15,       # un clic sur un pigeon le met en pause pour 15 min (0 : sans limite)
    # Combien de temps une session qui attend ta RÉPONSE (une fin de tour ou une question) garde sa ligne et sa flèche
    # vers sa zone de réponse : toujours (jusqu'à la réponse ou « Terminer ») | 15 | 5 | 1 (minutes) | jamais.
    # L'encadré et l'étiquette restent ; une permission à donner et un geste demandé (montre.py) sont toujours guidés ;
    # « Guider » ou Ctrl+Alt+P la montrent quand l'utilisateur décide de répondre. L'histoire : 2 octobre 16h04, « j'aimerais
    # que ça reste, ou une option pour le timer » ; 3 octobre 08h41, « le guidage est utile dans une tâche active ;
    # l'attente de réponse garde la ligne active et fait du bruit visuellement, jusqu'à ce que je décide de répondre ».
    "lignes_reponse": "jamais",
    # Plus d'infos à l'écran pour guider (l'utilisateur, 16h51) : discret (la ligne et l'encadré) | detaille (une étiquette
    # à côté de l'encadré : qui attend, quoi, depuis quand) | complet (et le geste à faire, avec son raccourci).
    "infos_ecran": "discret",    # coupé par défaut (l'utilisateur, 3 octobre 11h23 : l'étiquette survolait un bouton)
    # La forme et le mouvement des lignes (l'utilisateur, 13h18 : « des options de variété de ligne, des animations, des
    # lignes courbes, sinueuses »).
    "lignes_forme": "arc",       # droite | arc | sinueuse | vol (un arc et de petites vagues)
    "lignes_courbure": 35,       # de 0 (presque droite) à 100
    "lignes_trace": True,        # la ligne se dessine de la souris au but en 250 ms quand elle apparaît
    "lignes_animation": "aucune",  # aucune | defile (les points avancent vers le but) | onde (une onde court)
    "lignes_vitesse": 4,         # de 1 (lent) à 10 (vif)
    # Le fondu (l'utilisateur, 12h47 : « véritablement de 0 à 100 d'opacité et de distance ; décider où il commence à
    # disparaître ; même aux extrêmes, il était encore visible ») : l'opacité près de la souris, l'opacité près du
    # but, et entre quelles places du trajet (en %) on passe de l'une à l'autre.
    "lignes_opacite_depart": 90,   # près de la souris, en %
    "lignes_opacite_arrivee": 90,  # près du but, en %
    "lignes_fondu_debut": 0,       # le fondu commence à ce % du trajet (0 : à la souris)
    "lignes_fondu_fin": 100,       # ... et finit à ce % (100 : au but)
    "lignes_fondu": "aucun",       # ancien réglage, gardé pour les vieux fichiers ; plus utilisé
    "lignes_fondu_portee": 100,
    "lignes_fondu_min": 0,       # l'opacité au bout du fondu, en % (0 : la ligne s'efface tout à fait)  # sur quelle part de la ligne le fondu se fait, en % (l'utilisateur : « le niveau de fondu »)     # aucun | cible : s'estompe vers le but | souris : s'estompe vers la souris
    # Les encadrés (l'utilisateur, 11h52 : « actif ou non, largeur aussi »)
    "encadres_epaisseur": 1,     # l'épaisseur du trait, 1 à 4 px
    "encadres_marge": 0,         # la taille de l'encadré autour de la cible, en px (0 : au ras de son bord)
    "encadres_arrondi": 6,       # le rayon des coins, en px (0 : coins carrés)
    "encadres_style": "pointilles",  # pointilles | plein
    "encadres_montre": True,     # encadrer aussi l'endroit montré par une demande (montre.py)
    "encadres_travail": True,    # sans pigeons : encadrer où chaque IA travaille, avec son nom (l'utilisateur, 3 octobre, 18h3x)
    # Le code d'importance (même message : « code de couleur d'importance des tâches ? ») : le corps du pigeon
    # garde la couleur de sa tâche ; l'anneau, les flèches, les lignes et les encadrés prennent celle de l'importance.
    "couleur_guides": "tache",   # tache | importance
    "couleur_bloquee": "#ff2d55",  # une permission à donner (le crochet Notification de Claude Code)
    "couleur_haute": "#ff5a5f",  # un geste à faire (montre.py)
    "couleur_normale": "#ffb020",  # une question posée
    "couleur_basse": "#5aa0ff",  # une session qui a fini son tour et t'attend
}
# La langue (l'utilisateur, 12h13 : « anglais par défaut, mais laisse-moi le en français »). Le français reste écrit dans le
# code ; ANGLAIS donne la traduction de chaque texte affiché. Un texte absent de la table s'affiche en français.
LANGUE = "en"
ANGLAIS = {
    # le guetteur : où est le pigeon, ce qu'il montre
    "dans le dossier ouvert {x}": "in the open folder {x}", "{f} (sur {n})": "{f} (on {n})",
    "{f} (caché, perché sur la fenêtre)": "{f} (hidden, perched on the window)",
    "{f} (dans {d}, icône hors vue)": "{f} (in {d}, icon out of view)",
    "{f} ({n} caché, perché sur la fenêtre)": "{f} ({n} hidden, perched on the window)",
    "{f} (hors Bureau)": "{f} (outside the Desktop)", "c'est caché sous cette fenêtre": "it's hidden under this window",
    "je ne vois pas {f} à l'écran": "I can't see {f} on screen",
    "la fenêtre « {w} » n'est pas ouverte": "the window “{w}” is not open",
    "je ne trouve pas « {e} » dans « {w} »": "I can't find “{e}” in “{w}”",
    "d'abord : clique ici pour ramener « {w} » devant": "first: click here to bring “{w}” to the front",
    "la fenêtre « {w} » est derrière : ramène-la devant": "the window “{w}” is behind: bring it to the front",
    "Regarde ici": "Look here", "te montre : ": "shows you: ", "Permission à donner : ": "Permission needed: ",
    # la balise et le repérage précis (5 octobre 2026)
    "bouton « {e} »": "button “{e}”", "« {a} » est réduite": "“{a}” is minimized", "« {a} » est derrière": "“{a}” is behind",
    "je ne trouve pas l'onglet « {o} » dans « {w} »": "I can't find the tab “{o}” in “{w}”",
    "onglet « {o} »": "tab “{o}”", "ouvre l'onglet « {o} »": "open the tab “{o}”",
    "d'abord : ouvre l'onglet « {o} »": "first: open the tab “{o}”",
    "je ne trouve pas la page dans « {w} »": "I can't find the page in “{w}”",
    " ; les noms proches : {n}": "; close names: {n}",
    " ; si c'est dans un autre onglet, donne --onglet": "; if it is in another tab, give --onglet",
    "« {f} » est caché": "“{f}” is hidden", "Bureau": "Desktop", "écran principal": "main screen",
    "écran de gauche": "left screen", "écran de droite": "right screen", "écran du bas": "bottom screen",
    "écran du haut": "top screen", "bouton": "button", "onglet": "tab", "élément": "item",
    "menu": "menu", "case": "checkbox", "option": "option", "zone de texte": "text box", "liste": "list",
    "page": "page", "image": "image", "groupe": "group", "Explorateur": "File Explorer",
    "Invite de commandes": "Command Prompt", "Bloc-notes": "Notepad",
    "sous « {a} »": "under “{a}”", "fais défiler {d}": "scroll {d}", "dépose ici": "drop here",
    "La balise": "The beacon", "Ce que dit la balise": "What the beacon says",
    "Une balise sur la ligne : où est exactement la cible (l'app, l'onglet, ce qui la couvre)":
        "A beacon on the line: exactly where the target is (the app, the tab, what covers it)",
    "Tout le chemin": "The whole path", "L'app et l'élément": "The app and the item",
    "Le halo de la balise respire lentement": "The beacon's halo breathes slowly",
    "Claude a besoin de toi": "Claude needs you", "bloquée : attend ta permission": "blocked: needs your permission",
    "Je t'attends": "Waiting for you", "t'attend (vient te chercher)": "waiting (coming to get you)",
    "t'attend": "waiting for you", "au repos": "resting", "{o} (pas de fichier)": "{o} (no file)",
    # les bulles, les durées, l'importance
    "Merci !": "Thanks!", "te montre où aller": "shows you where to go", "en pause": "paused",
    "en pause encore ": "paused for another ",
    "{t} · en pause\n{b}\n(clique-moi pour reprendre)": "{t} · paused\n{b}\n(click me to resume)",
    "{t}\n{b}\n(clique-moi : plus tard)": "{t}\n{b}\n(click me: later)",
    "moins d'une minute": "less than a minute", "à l'instant": "just now", "depuis ": "for ",
    "permission à donner": "permission needed", "geste à faire": "action needed", "question": "question",
    "à toi quand tu veux": "whenever you're ready",
    # le panneau
    "Tout en pause": "Pause all", "Tout reprendre": "Resume all", "Masquer les guides": "Hide guides",
    "Montrer les guides": "Show guides", "Réglages": "Settings", "Arrêter": "Quit",
    "Ctrl+Alt+P : prochaine action": "Ctrl+Alt+P: next action",
    "Ctrl+Alt+P est déjà pris par un autre programme": "Ctrl+Alt+P is already used by another program",
    "À faire pour toi": "To do for you", "Au travail": "Working", "Au repos": "Resting",
    "Rien ne t'attend. Les pigeons veillent.": "Nothing is waiting for you. The pigeons are on watch.",
    "Aller": "Go", "Reprendre": "Resume", "Guider": "Guide", "C'est fait": "Done", "Plus tard ▾": "Later ▾",
    "Dans 5 min": "In 5 min", "Dans 15 min": "In 15 min", "Dans 1 h": "In 1 h", "Sans limite": "No limit",
    "lien": "link", "dossier": "folder", "fichier": "file", "Montrer": "Show", "Ouvrir": "Open", "Copier": "Copy",
    "texte": "text", "Oublier": "Dismiss", "Livrables des sessions finies": "Deliverables of finished sessions",
    "nouvelle séance": "new session", "Nouvelle séance": "New session",
    "« {e} » introuvable": "« {e} » not found", "introuvable": "not found", "proche : « {n} »": "close: « {n} »",
    "pas sur cette page": "not on this page", "{ia} a fini son tour : à toi de jouer": "{ia} finished its turn: your move",
    "attend": "waiting",
    "Copie l'invite et ouvre une nouvelle session dans son dossier, dans l'app Claude : il reste à coller (Ctrl+V).":
        "Copies the prompt and opens a new session in its folder, in the Claude app: then paste (Ctrl+V).",
    "Clique « Nouveau », choisis le dossier « {d} », puis colle l'invite (Ctrl+V)":
        "Click « New », pick the folder « {d} », then paste the prompt (Ctrl+V)",
    "Clique « Nouveau », puis colle l'invite (Ctrl+V)": "Click « New », then paste the prompt (Ctrl+V)",
    "Copie le texte du bloc (un prompt, une commande).": "Copies the block's text (a prompt, a command).",
    "Ces livrables s'en vont du panneau (la session reste terminée).": "These deliverables leave the panel (the session stays finished).",
    "terminée ": "finished ",
    " · guides masqués": " · guides hidden", "pigeonneau": "squab", "pigeonneaux": "squabs",
    # les réglages
    "Ligne vers l'endroit exact où il travaille": "Line to the exact spot it works on",
    "Au survol du pigeon": "When hovering the pigeon", "Toujours": "Always", "Jamais": "Never",
    "Le panneau": "The panel", "Libre (je le place moi-même)": "Free (I place it myself)",
    "Collé à droite de Claude": "Docked to the right of Claude", "Collé à gauche de Claude": "Docked to the left of Claude",
    "Pigeons · réglages": "Pigeons · settings",
    "Quand une fenêtre cache l'icône où il travaille": "When a window hides the icon it works on",
    "Il va sur la barre des tâches": "It goes to the taskbar", "Il se perche sur cette fenêtre": "It perches on that window",
    "Il se cache": "It hides",
    "Opacité près de ma souris (%)": "Opacity near my mouse (%)", "Opacité près du but (%)": "Opacity near the target (%)",
    "Le fondu commence à (% du trajet)": "The fade starts at (% of the way)",
    "Le fondu finit à (% du trajet)": "The fade ends at (% of the way)",
    "0 % du trajet : à ta souris ; 100 % : au but. Deux opacités égales : pas de fondu. Exemple : 90 puis 0, de 50 à 100 : la ligne est pleine jusqu'à mi-chemin et s'éteint en arrivant.":
        "0 % of the way: at your mouse; 100 %: at the target. Two equal opacities: no fade. Example: 90 then 0, "
        "from 50 to 100: the line is full until halfway and fades out on arrival.",
    "Taille autour de la cible (px)": "Size around the target (px)", "Coins arrondis (px)": "Rounded corners (px)",
    "Épaisseur du trait (px)": "Line thickness (px)",
    "À 0, l'encadré passe au ras du bord de la cible, sur sa bordure : il ne cache pas son contenu. Les lignes de la liste de Claude, qui se touchent, restent encadrées au ras ou en dedans.":
        "At 0, the frame runs right along the target's edge, on its border: it doesn't hide its content. "
        "The rows of Claude's list, which touch each other, stay framed at their edge or inside.",
    "Général": "General", "Guidage": "Guidance", "Lignes": "Lines", "Pigeons": "Pigeons",
    "Couleurs et bulles": "Colors and bubbles", "Fondu": "Fade", "Style": "Style", "Les flèches": "Arrows",
    "Couleur des lignes": "Line color", "Raccourci clavier": "Keyboard shortcut",
    "Ctrl+Alt+P : prochaine action (rappuyer dans les 6 s passe à la suivante).":
        "Ctrl+Alt+P: next action (press again within 6 s for the next one).",
    "Remettre par défaut": "Reset to defaults", "Remettre tous les réglages par défaut ?": "Reset all settings to defaults?", "Fermer": "Close", "Langue": "Language",
    "Guidage vers ce que tu as à faire": "Guidance to what you need to do",
    "Des flèches autour de ma souris": "Arrows around my mouse",
    "Des lignes pointillées de ma souris au but": "Dotted lines from my mouse to the target",
    "Guider vers les sessions qui m'attendent": "Guide me to the sessions waiting for me",
    "Flèches creuses (juste le contour)": "Hollow arrows (outline only)", "Taille des flèches (px)": "Arrow size (px)",
    "Encadrés": "Frames", "Actifs, toujours affichés": "On, always shown",
    "Actifs quand ma souris approche": "On when my mouse gets close", "Désactivés": "Off",
    "Encadrer aussi l'endroit montré par une demande": "Also frame the spot shown by a request",
    "Sans pigeons, encadrer où chaque IA travaille (avec son nom)": "Without pigeons, frame where each AI works (with its name)",
    "En pointillés": "Dotted", "En trait plein": "Solid", "Épaisseur (px)": "Thickness (px)",
    "Quand une session m'attend": "When a session is waiting for me",
    "Le pigeon vient près de ma souris": "The pigeon comes near my mouse", "Pendant (secondes)": "For (seconds)",
    "Clic sur un pigeon : plus tard (min, 0 = sans fin)": "Pigeon click: later (min, 0 = indefinitely)",
    "Les pigeons": "The pigeons", "Taille des pigeons": "Pigeon size",
    "Montrer aussi les pigeons au travail": "Also show working pigeons",
    "Montrer les pigeonneaux (sous-agents)": "Show squabs (sub-agents)", "Bulles": "Bubbles",
    "Une ligne courte quand il montre ou m'appelle": "A short line when it shows or calls me",
    "Seulement au survol": "Only on hover", "Opacité des bulles (%)": "Bubble opacity (%)", "Démarrage": "Startup",
    "Lancer les pigeons avec Windows": "Start the pigeons with Windows", "Lignes pointillées": "Dotted lines",
    "Des points": "Dots", "Des tirets": "Dashes", "Grosseur (px)": "Size (px)", "Espacement (px)": "Spacing (px)",
    "Opacité (%)": "Opacity (%)", "Sans fondu": "No fade", "Fondu vers le but": "Fade toward the target",
    "Fondu vers ma souris": "Fade toward my mouse", "Distance du fondu (%)": "Fade distance (%)",
    "Opacité au bout du fondu (%)": "Opacity at the end of the fade (%)", "De la couleur du guide": "In the guide's color",
    "D'une seule couleur :": "In a single color:", "la couleur unique des lignes": "the single line color",
    "Couleur des guides": "Guide color", "La couleur de la tâche": "The task's color",
    "Le code d'importance": "The importance code",
    "Le corps du pigeon garde toujours la couleur de sa tâche.": "The pigeon's body always keeps its task's color.",
    "Bloquée : une permission à donner": "Blocked: a permission to give", "Haute : un geste à faire": "High: an action to take",
    "Normale : une question posée": "Normal: a question asked", "Basse : à toi quand tu veux": "Low: whenever you're ready",
    # fermer une session finie, la forme des lignes (2 octobre, après-midi)
    "Terminer": "End", "« {t} » terminée": "“{t}” ended", "Annuler": "Undo",
    "Ctrl+Alt+P : prochaine action · Ctrl+Alt+T : c'est fait ou terminer":
        "Ctrl+Alt+P: next action · Ctrl+Alt+T: done or end",
    "Ligne vers une session qui attend ma réponse": "Line to a session waiting for my answer",
    "Jamais : Ctrl+Alt+P ou « Guider » la montrent": "Never: Ctrl+Alt+P or “Guide” shows it",
    "Une fin de tour. L'encadré et l'étiquette restent. Une question posée (son questionnaire), une permission à donner et un geste demandé sont toujours guidés.":
        "A finished turn. The frame and the label stay. A question asked (its questionnaire), a permission to give and "
        "a requested action are always guided.",
    "questionnaire : choisis une réponse": "questionnaire: pick an answer",
    "→ choisis une option, puis « Envoyer » (ou « Passer »)": "→ pick an option, then “Send” (or “Skip”)",
    # l'onglet Guide et les infos à l'écran
    "À faire": "To do", "Guide": "Guide", "Ouvrir le dossier": "Open the folder", "Infos à l'écran": "On-screen info",
    "Discrètes (la ligne et l'encadré)": "Discreet (the line and the frame)",
    "Détaillées (une étiquette : qui, quoi, depuis quand)": "Detailed (a label: who, what, since when)",
    "Complètes (et le geste à faire, avec son raccourci)": "Complete (plus the action to take, with its shortcut)",
    "→ clique ici pour lui répondre · Ctrl+Alt+P": "→ click here to answer it · Ctrl+Alt+P",
    "→ va donner la permission dans la session · Ctrl+Alt+P": "→ go give the permission in the session · Ctrl+Alt+P",
    "Étape {n} sur 2": "Step {n} of 2", "Clique l'endroit encadré · Ctrl+Alt+T : c'est fait":
        "Click the framed spot · Ctrl+Alt+T: done",
    # l'aide active et les repères du panneau (3 octobre)
    "Ouvrir le fichier": "Open the file", "Amener devant": "Bring to front", "fenêtre": "window", "Dossier": "Folder",
    "Ouvre le dossier tout de suite, sans le chercher.": "Opens the folder right away, without looking for it.",
    "Ouvre le fichier avec son programme.": "Opens the file with its program.",
    "Montre l'endroit dans l'Explorateur.": "Shows the spot in File Explorer.",
    "Ramène cette fenêtre devant les autres.": "Brings this window in front of the others.",
    "Ouvre le dossier où elle travaille, le fichier sélectionné.": "Opens the folder it works in, with the file selected.",
    "{k} k jetons": "{k} k tokens",
    "⚠ même dossier que « {t} » : attention aux conflits": "⚠ same folder as “{t}”: watch out for conflicts",
    "1 · prends ceci": "1 · take this", "2 · dépose ici": "2 · drop here", "ensuite ici": "then here",
    "écrit": "writing", "travaille": "working",
    "⚠ Conflit possible : « {a} » et « {b} » écrivent dans {f}": "⚠ Possible conflict: “{a}” and “{b}” are writing {f}",
    "Thème": "Theme", "Apparence": "Appearance", "Système": "System", "Clair": "Light", "Sombre": "Dark", "Thème sombre": "Dark theme",
    "Par défaut": "Default", "Nuit": "Night", "Ambre": "Amber", "Contraste": "Contrast", "Normal": "Normal",
    "Fort": "Strong", "Mes couleurs :": "My colors:", "Fond": "Background", "Texte": "Text", "Accent": "Accent",
    "Bulles et étiquettes": "Bubbles and labels", "Papier (claires)": "Paper (light)",
    "Aux couleurs du thème": "Theme colors", "Sombres": "Dark",
    "Une bulle près de la cible (sinon, la consigne reste dans le panneau)":
        "A bubble near the target (otherwise, the instruction stays in the panel)",
    "« Système » suit le thème clair ou sombre de Windows. « Ambre » reprend les couleurs d'Antigravity.":
        "“System” follows Windows' light or dark theme. “Amber” uses Antigravity's colors.",
    "Rechercher": "Search", "Le guidage": "Guidance", "L'app": "The app",
    "Résultats pour « {q} »": "Results for “{q}”", "Aucun réglage ne correspond.": "No setting matches.",
    # les infobulles des boutons (3 octobre)
    "Tous les pigeons attendent sur la barre des tâches.": "All pigeons wait on the taskbar.",
    "Cache les lignes, les flèches, les encadrés et les étiquettes ; le panneau reste.":
        "Hides the lines, arrows, frames and labels; the panel stays.",
    "Afficher les pigeons (sinon : les lignes, les flèches et les encadrés seulement)":
        "Show the pigeons (otherwise: only the lines, arrows and frames)",
    "Ouvre les réglages.": "Opens the settings.",
    "Arrête les pigeons. Le ✕ de la fenêtre, lui, la réduit seulement.":
        "Stops the pigeons. The window's ✕ only minimizes it.",
    "Ouvre cette session dans l'app Claude.": "Opens this session in the Claude app.",
    "Reprend le guidage mis en pause.": "Resumes the paused guidance.",
    "La ligne et le pigeon te montrent le chemin jusqu'à elle.": "The line and the pigeon show you the way to it.",
    "Le geste demandé est fait : la demande s'en va.": "The requested action is done: the request goes away.",
    "La session est finie : sa carte, sa ligne et son pigeon s'en vont. Elle revient si tu lui écris.":
        "The session is finished: its card, line and pigeon go away. It comes back if you write to it.",
    "Montre le fichier dans l'Explorateur.": "Shows the file in File Explorer.",
    "Ouvre le lien ou le fichier.": "Opens the link or the file.",
    "Copie l'adresse ou le chemin complet.": "Copies the full address or path.",
    "Le pigeon attend sur la barre des tâches, puis revient seul.":
        "The pigeon waits on the taskbar, then comes back by itself.",
    "Jusqu'à ma réponse (ou « Terminer »)": "Until I answer (or “End”)", "Pendant 15 min": "For 15 min",
    "Pendant 5 min": "For 5 min", "Pendant 1 min": "For 1 min",
    "Ctrl+Alt+T : « C'est fait » ou « Terminer » sur la première chose à faire. Clic droit sur un pigeon : terminer sa session.":
        "Ctrl+Alt+T: “Done” or “End” on the first thing to do. Right-click a pigeon: end its session.",
    "Forme et mouvement": "Shape and motion", "Forme": "Shape", "Droite": "Straight", "En arc": "Arc",
    "Sinueuse": "Wavy", "En vol": "Flight", "Courbure (%)": "Curvature (%)",
    "La ligne se dessine à son apparition": "The line draws itself when it appears",
    "Animation continue": "Continuous animation", "Aucune": "None", "Les points avancent": "Dots move forward",
    "Une onde": "A wave", "Vitesse de l'animation": "Animation speed",
    "« En vol » : un arc et de petites vagues, comme un pigeon. Une animation continue redessine les lignes 15 fois par seconde : un peu plus de processeur.":
        "“Flight”: an arc with small waves, like a pigeon. A continuous animation redraws the lines 15 times per "
        "second: a little more CPU.",
}


def tr(texte, **valeurs):
    """Le texte dans la langue réglée ; les {x} se remplissent avec les valeurs données."""
    if LANGUE == "en":
        texte = ANGLAIS.get(texte, texte)
    return texte.format(**valeurs) if valeurs else texte


IMPORTANCES = {"bloquee": "permission à donner", "haute": "geste à faire", "normale": "question",
               "basse": "à toi quand tu veux"}
RANG_IMPORTANCE = {"bloquee": 0, "haute": 1, "normale": 2, "basse": 3}


# Les palettes du panneau. Chaque clé a sa couleur propre (le panneau se repeint en changeant chaque couleur
# de l'ancienne palette pour la nouvelle).
PALETTES = {
    "defaut": {"FOND": "#16171b", "CARTE": "#22242b", "TEXTE": "#e9e9ec", "PALE": "#9a9ca6", "ACCENT": "#8ab4ff",
               "BOUTON": "#2b2e36", "BOUTON_ACTIF": "#3a3e48", "ACTIF_TEXTE": "#ffffff", "DANGER": "#3a2326",
               "DANGER_ACTIF": "#5a2b30", "TERNE": "#6b6d75"},
    "nuit": {"FOND": "#000000", "CARTE": "#121212", "TEXTE": "#ffffff", "PALE": "#c8c8c8", "ACCENT": "#ffd23f",
             "BOUTON": "#262626", "BOUTON_ACTIF": "#3a3a3a", "ACTIF_TEXTE": "#ffffe0", "DANGER": "#4a1010",
             "DANGER_ACTIF": "#6a1a1a", "TERNE": "#8a8a8a"},
    "ambre": {"FOND": "#191016", "CARTE": "#24171f", "TEXTE": "#ffd58a", "PALE": "#c9a77a", "ACCENT": "#007acc",
              "BOUTON": "#33212c", "BOUTON_ACTIF": "#45303c", "ACTIF_TEXTE": "#ffe9c2", "DANGER": "#4a1c22",
              "DANGER_ACTIF": "#66262e", "TERNE": "#7a6458"},
    "clair": {"FOND": "#f3f4f6", "CARTE": "#ffffff", "TEXTE": "#1d1f24", "PALE": "#5f6470", "ACCENT": "#2f6fd6",
              "BOUTON": "#e2e5ea", "BOUTON_ACTIF": "#d0d5dd", "ACTIF_TEXTE": "#000000", "DANGER": "#f7dede",
              "DANGER_ACTIF": "#efc4c4", "TERNE": "#a3a8b2"},
}


def melanger(c1, c2, t):
    """La couleur à t (0 à 1) du chemin entre c1 et c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def clarte(c):
    """De 0 (noir) à 1 (blanc), à l'œil."""
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def windows_en_clair():
    """Vrai si Windows est en thème clair pour les applications (mesuré à « sombre » chez l'utilisateur le 2 octobre)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return bool(winreg.QueryValueEx(k, "AppsUseLightTheme")[0])
    except OSError:
        return False


def palette(r):
    """La palette en vigueur, d'après les réglages : le thème (système, clair, sombre et sa variante), mes couleurs,
    le contraste, et les couleurs des bulles."""
    mode = r.get("theme", "systeme")
    if mode == "systeme":
        mode = "clair" if windows_en_clair() else "sombre"
    pal = dict(PALETTES["clair"] if mode == "clair" else PALETTES.get(r.get("theme_sombre"), PALETTES["defaut"]))
    if r.get("theme_perso"):
        f, t, a = r["couleur_fond"], r["couleur_texte"], r["couleur_accent"]
        pal.update(FOND=f, TEXTE=t, ACCENT=a, CARTE=melanger(f, t, 0.06), BOUTON=melanger(f, t, 0.12),
                   BOUTON_ACTIF=melanger(f, t, 0.2), ACTIF_TEXTE=melanger(t, f, 0.02) if t != f else t,
                   PALE=melanger(t, f, 0.35), TERNE=melanger(t, f, 0.6),
                   DANGER=melanger(f, "#c0392b", 0.25), DANGER_ACTIF=melanger(f, "#c0392b", 0.4))
    if r.get("contraste") == "fort":
        # Le texte pâle se rapproche du texte, les boutons se détachent du fond.
        pal.update(PALE=melanger(pal["PALE"], pal["TEXTE"], 0.7), BOUTON=melanger(pal["FOND"], pal["TEXTE"], 0.22),
                   BOUTON_ACTIF=melanger(pal["FOND"], pal["TEXTE"], 0.32))
    if r.get("bulles_couleurs") == "theme":
        pal.update(BULLE_FOND=pal["CARTE"], BULLE_TEXTE=pal["TEXTE"])
    elif r.get("bulles_couleurs") == "sombre":
        # Sombres quel que soit le thème du panneau (l'utilisateur, 3 octobre, 19h09:36 : « unifier l'esthétique des bulles, thème
        # sombre, fond sombre des bulles et de la couleur de police ») : le fond et le texte des cartes du thème sombre choisi.
        sombre = PALETTES.get(r.get("theme_sombre"), PALETTES["defaut"])
        pal.update(BULLE_FOND=sombre["CARTE"], BULLE_TEXTE=sombre["TEXTE"])
    else:
        pal.update(BULLE_FOND="#fffdf5", BULLE_TEXTE="#1b1b1b")
    return pal


def contenu_guide():
    """L'onglet « Guide » du panneau (l'utilisateur, 16h51 : « un onglet qui explique l'app, les fonctionnalités ») : des
    sections courtes, dans la langue réglée. « couleurs » : les pastilles des importances ; « dossier » : un bouton."""
    d = str(ICI)
    if LANGUE == "en":
        return [
            {"titre": "What the pigeons do", "texte": [
                "Each AI session (Claude Code, Cowork, another AI) has its own pigeon and color. When a session needs "
                "you, the pigeons show you what to do and where to click.",
                "Everything stays on your computer: the pigeons read Claude Code's logs and send nothing anywhere."]},
            {"titre": "On screen", "texte": [
                "• A dotted line goes from your mouse to what is waiting for you: a session, a button, a file.",
                "• A frame hugs the target. With more on-screen info, a label says who is waiting, for what, and since when.",
                "• The pigeons themselves are hidden by default (Settings, Pigeons card, to show them). When shown, "
                "the body has its session's color; a breathing ring: it is waiting for you; dotted: paused.",
                "• Two linked targets (drag a file into a folder, or click here then there): an arrowed line goes "
                "from the first to the second, their frames show 1 and 2, and labels say “take this” and “drop here”.",
                "• The beacon: on the line, just before the target, a small label says exactly where it is: the app, "
                "the tab, the button (“Chrome › tab “Gemini” › button “Send””). If another window covers the target, an "
                "amber chip says which one, and step 1 shows the app's taskbar button first; a hidden tab is shown "
                "first too. The beacon never covers the target: it moves back along the line, and fades out when your "
                "mouse is close (Settings, Guidance).",
                "• Squabs are a session's sub-agents."]},
            {"titre": "Importance colors", "couleurs": True, "texte": ["You can change these colors in Settings."]},
            {"titre": "The panel", "texte": [
                "To do for you: one card per session waiting for you, the most important first. Working: the sessions "
                "at work, their file and their rhythm. Resting: the ones asleep.",
                "• Go: opens the session in Claude.   • Guide: the line and the pigeon show you the way.",
                "• Done: the requested action is done.   • Later: 5 min, 15 min, 1 h or no limit.",
                "• End: the session is finished; it comes back if you write to it.",
                "• Copy, Open, Show: the links and files the session mentioned.",
                "• New session: when the session gives a prompt to paste into a fresh session, this button copies it "
                "and opens a new session in the right folder of the Claude app. Then paste (Ctrl+V) and send.",
                "• Active help: when a session asks you to go into a folder, open a file or a window, its card offers "
                "“Open the folder”, “Open the file” or “Bring to front”.",
                "• Working: “Folder” opens the place where the session works; the row shows how long its turn has "
                "lasted and its context size (a compaction comes near the limit); a warning if two sessions work in "
                "the same folder.",
                "Hover a button: it says what it does. The window's ✕ minimizes the panel; “Quit” stops the pigeons."]},
            {"titre": "With the mouse", "texte": [
                "• Click the spot shown: done, the pigeon says thanks.",
                "• If the pigeons are shown: click a pigeon for later (click again: resume); right-click: end its "
                "session.",
                "• Hover a pigeon: its full bubble."]},
            {"titre": "With the keyboard", "texte": [
                "• Ctrl+Alt+P: go to the most important thing; press again within 6 s for the next one.",
                "• Ctrl+Alt+T: “Done” or “End” on the first thing to do."]},
            {"titre": "Ending a finished session", "texte": [
                "End (card, right-click, Ctrl+Alt+T), archive the session in Claude, or the session itself at the end "
                "of its handoff (montre.py --termine). It comes back if you write to it."]},
            {"titre": "For AIs: montre.py", "texte": [
                "A session that needs an action runs: python montre.py --texte \"Click Accept\" --fenetre \"Chrome\" "
                "--element \"Accept\".",
                "Other targets: --fichier, --point X Y. A drag: --vers-… Two steps: --puis-… Also --importance, --fin, "
                "--termine. Another AI: --session name --titre \"Name\".",
                "Coordination: the pigeons keep activite.json up to date (who works where, every 2 s). Another AI "
                "announces itself with annonce.py --session name --fichier PATH --ecrit, and asks before writing: "
                "annonce.py --qui PATH (free, occupied). The panel warns when two AIs write the same file.",
                "The MCP server (pigeons_mcp.py): the same tools in each AI's own tool list (show, list, clear, end, "
                "who_works, announce, state), with no command line to remember. Claude Code, Codex, Antigravity and "
                "the Claude app (as “pigeons-cowork”) can plug it in. A Claude Code hook reminds every session of the "
                "pigeons at start, and another asks you before a session writes a file another AI wrote < 5 min ago."]},
            {"titre": "Settings", "texte": [
                "At the bottom of the panel: guidance (lines or arrows), on-screen info, line shape and motion, fade, "
                "frames, pigeons, colors, language. Everything is kept in reglages.json.",
                "The line to a session that finished its turn: never by default (Ctrl+Alt+P or “Guide” shows it), "
                "a few minutes, or until you answer. A question, a permission and a requested action are always "
                "guided; a question points to its questionnaire, down to the “Send” button. If "
                "Windows has turned off its animations, the lines stop moving too."]},
            {"titre": "Files", "dossier": True, "texte": [
                f"The folder: {d}. MANUAL.docx (or MANUAL.md) explains everything in detail; preuve_pigeons.log keeps the errors."]},
        ]
    return [
        {"titre": "Ce que font les pigeons", "texte": [
            "Chaque session d'IA (Claude Code, Cowork, une autre IA) a son pigeon et sa couleur. Quand une session a "
            "besoin de toi, les pigeons te montrent quoi faire et où cliquer.",
            "Tout reste sur ton ordinateur : les pigeons lisent les journaux de Claude Code et n'envoient rien."]},
        {"titre": "À l'écran", "texte": [
            "• Une ligne pointillée va de ta souris jusqu'à ce qui t'attend : une session, un bouton, un fichier.",
            "• Un encadré épouse la cible. Avec plus d'infos à l'écran, une étiquette dit qui t'attend, pour quoi, "
            "et depuis quand.",
            "• Les pigeons eux-mêmes sont cachés par défaut (Réglages, carte Pigeons, pour les afficher). Affichés, le "
            "corps a la couleur de sa session ; un anneau qui respire : elle t'attend ; en pointillé : en pause.",
            "• Deux cibles liées (glisser un fichier dans un dossier, ou cliquer ici puis là) : une ligne fléchée va de "
            "la première à la seconde, leurs encadrés portent 1 et 2, et des étiquettes disent « prends ceci » et "
            "« dépose ici ».",
            "• La balise : sur la ligne, juste avant la cible, une petite étiquette dit où elle est exactement : "
            "l'app, l'onglet, le bouton (« Chrome › onglet « Gemini » › bouton « Envoyer » »). Si une autre fenêtre "
            "couvre la cible, une puce ambre dit laquelle, et l'étape 1 montre d'abord le bouton de l'app dans la barre "
            "des tâches ; un onglet caché se montre d'abord aussi. La balise ne couvre jamais la cible : elle recule "
            "le long de la ligne, et s'efface quand ta souris est tout près (Réglages, Guidage).",
            "• Les pigeonneaux sont les sous-agents d'une session."]},
        {"titre": "Les couleurs d'importance", "couleurs": True, "texte": ["Ces couleurs se changent dans Réglages."]},
        {"titre": "Le panneau", "texte": [
            "À faire pour toi : une carte par session qui t'attend, la plus importante en haut. Au travail : les "
            "sessions qui travaillent, leur fichier et leur rythme. Au repos : celles qui dorment.",
            "• Aller : ouvre la session dans Claude.   • Guider : la ligne et le pigeon te montrent le chemin.",
            "• C'est fait : le geste demandé est fait.   • Plus tard : 5 min, 15 min, 1 h ou sans limite.",
            "• Terminer : la session est finie ; elle revient si tu lui écris.",
            "• Copier, Ouvrir, Montrer : les liens et les fichiers cités par la session.",
            "• Nouvelle séance : quand la session donne un prompt à coller dans une séance neuve, ce bouton le copie et "
            "ouvre une nouvelle session dans le bon dossier de l'app Claude. Il reste à coller (Ctrl+V) et à envoyer.",
            "• Aide active : quand une session te demande d'aller dans un dossier, d'ouvrir un fichier ou une fenêtre, "
            "sa carte offre « Ouvrir le dossier », « Ouvrir le fichier » ou « Amener devant ».",
            "• Au travail : « Dossier » ouvre l'endroit où la session travaille ; la ligne dit depuis quand dure son tour "
            "et la taille de son contexte (une compaction vient près de la limite) ; un avertissement si deux sessions "
            "travaillent dans le même dossier.",
            "Survole un bouton : il dit ce qu'il fait. Le ✕ de la fenêtre réduit le panneau ; « Arrêter » arrête les "
            "pigeons."]},
        {"titre": "Avec la souris", "texte": [
            "• Clique l'endroit montré : c'est fait, le pigeon dit merci.",
            "• Si les pigeons sont affichés : clique un pigeon pour plus tard (reclique : reprendre) ; clic droit : "
            "terminer sa session.",
            "• Survole un pigeon : sa bulle complète."]},
        {"titre": "Au clavier", "texte": [
            "• Ctrl+Alt+P : va à la chose la plus importante ; rappuie dans les 6 s pour la suivante.",
            "• Ctrl+Alt+T : « C'est fait » ou « Terminer » sur la première chose à faire."]},
        {"titre": "Fermer une session finie", "texte": [
            "« Terminer » (sur la carte, au clic droit, ou Ctrl+Alt+T), archiver la session dans Claude, ou la session "
            "elle-même à la fin de sa passation (montre.py --termine). Elle revient si tu lui écris."]},
        {"titre": "Pour les IA : montre.py", "texte": [
            "Une session qui a besoin d'un geste lance : python montre.py --texte \"Clique sur Accepter\" "
            "--fenetre \"Chrome\" --element \"Accepter\".",
            "Autres cibles : --fichier, --point X Y. Un glisser : --vers-… Deux étapes : --puis-… Et aussi "
            "--importance, --fin, --termine. Une autre IA : --session nom --titre \"Nom\".",
            "La coordination : les pigeons tiennent activite.json à jour (qui travaille où, toutes les 2 s). Une autre "
            "IA s'annonce par annonce.py --session nom --fichier CHEMIN --ecrit, et demande avant d'écrire : "
            "annonce.py --qui CHEMIN (libre, occupé). Le panneau avertit quand deux IA écrivent le même fichier.",
            "Le serveur MCP (pigeons_mcp.py) : les mêmes outils dans la liste d'outils de chaque IA (montrer, lister, "
            "effacer, terminer, qui_travaille, annoncer, etat), sans ligne de commande à retenir. Branché dans Claude "
            "Code, Codex, Antigravity et l'app Claude (sous le nom « pigeons-cowork »). Un crochet de Claude Code "
            "rappelle les pigeons à chaque session qui s'ouvre ; un autre te demande ton accord avant qu'une session "
            "écrive un fichier qu'une autre IA a écrit il y a moins de 5 min."]},
        {"titre": "Les réglages", "texte": [
            "En bas du panneau : le guidage (lignes ou flèches), les infos à l'écran, la forme et le mouvement des "
            "lignes, le fondu, les encadrés, les pigeons, les couleurs, la langue. Tout se garde dans reglages.json.",
            "La ligne vers une session qui a fini son tour : jamais par défaut (Ctrl+Alt+P ou « Guider » la "
            "montrent), quelques minutes, ou jusqu'à ta réponse. Une question posée, une permission et un geste "
            "demandé sont toujours guidés ; une question vise son questionnaire, jusqu'au bouton « Envoyer ». Si Windows a coupé ses animations, les lignes ne bougent plus non plus."]},
        {"titre": "Les fichiers", "dossier": True, "texte": [
            f"Le dossier : {d}. MANUEL.docx (ou MANUEL.md) explique tout en détail ; preuve_pigeons.log garde les erreurs."]},
    ]
# Les notifications de Claude Code qui veulent dire « la session est arrêtée tant que l'utilisateur n'a rien fait ».
BLOQUANTS = {"permission_prompt", "elicitation_dialog", "elicitation_url_dialog", "agent_needs_input"}
SIGNAUX = ICI / "signaux"            # déposés par crochet_notification.py


def duree_lisible(secondes):
    m = max(0, int(secondes)) // 60
    if m < 1:
        return tr("moins d'une minute")
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60:02d}"


def depuis_lisible(secondes):
    return tr("à l'instant") if secondes < 60 else tr("depuis ") + duree_lisible(secondes)


def charger_reglages():
    r = dict(REGLAGES_DEFAUT)
    try:
        r.update({k: v for k, v in json.loads(REGLAGES.read_text(encoding="utf-8")).items() if k in r})
    except (OSError, ValueError):
        pass
    return r


def sauver_reglages(r):
    try:
        REGLAGES.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:
        log.warning("réglages non sauvés : %s", e)


# Le journal tourne : au plus 1 Mo, puis preuve_pigeons.log.1, .2, .3 ; il ne grossit plus sans fin.
from logging.handlers import RotatingFileHandler
_journal = RotatingFileHandler(ICI / "preuve_pigeons.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_journal.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_journal])
log = logging.getLogger("pigeons")


# Un fil qui meurt sur une erreur l'écrit dans le journal. Sous pythonw, il n'y a pas de sortie d'erreur : sans ceci,
# le guetteur est mort sans un mot à l'ouverture de session du 5 octobre 2026 (19h11), et le registre activite.json
# est resté figé pendant que le panneau, lui, tournait (annonce.py et montre.py disaient « les pigeons ne tournent pas »).
def _fil_mort(a):
    log.error("le fil %s s'est arrêté sur une erreur", a.thread.name if a.thread else "?",
              exc_info=(a.exc_type, a.exc_value, a.exc_traceback))


threading.excepthook = _fil_mort

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
user32.WindowFromPoint.restype = W.HWND
user32.WindowFromPoint.argtypes = [W.POINT]
user32.GetAncestor.restype = W.HWND
user32.GetAncestor.argtypes = [W.HWND, ctypes.c_uint]
user32.FindWindowExW.restype = W.HWND
user32.FindWindowW.restype = W.HWND
user32.GetParent.restype = W.HWND
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80000, 0x20
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80, 0x8000000
DWMWA_EXTENDED_FRAME_BOUNDS = 9
SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x4, 0x10


# ---------------------------------------------------------------- les écrans

def lire_ecrans():
    """Rend la liste des écrans : (rect complet, rect sans la barre des tâches), en pixels physiques."""
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT), ("dwFlags", W.DWORD)]
    ecrans = []
    Rappel = ctypes.WINFUNCTYPE(ctypes.c_int, W.HMONITOR, W.HDC, ctypes.POINTER(W.RECT), W.LPARAM)

    def rappel(hmon, _dc, _r, _l):
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        m, t = mi.rcMonitor, mi.rcWork
        ecrans.append({"rect": (m.left, m.top, m.right, m.bottom),
                       "travail": (t.left, t.top, t.right, t.bottom),
                       "principal": bool(mi.dwFlags & 1)})
        return 1
    user32.EnumDisplayMonitors(0, 0, Rappel(rappel), 0)
    return ecrans


def ecran_de(ecrans, x, y):
    for e in ecrans:
        l, t, r, b = e["rect"]
        if l <= x < r and t <= y < b:
            return e
    return None


def cadre_visible(hwnd):
    """Le rectangle qu'on voit d'une fenêtre (sans ses bordures invisibles de Windows 11)."""
    r = W.RECT()
    if dwmapi.DwmGetWindowAttribute(W.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        user32.GetWindowRect(W.HWND(hwnd), ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def nom_de_classe(hwnd):
    b = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(W.HWND(hwnd), b, 64)
    return b.value


def titre_de(hwnd):
    n = user32.GetWindowTextLengthW(W.HWND(hwnd))
    b = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(W.HWND(hwnd), b, n + 1)
    return b.value


def fenetres_visibles():
    """Les fenêtres principales visibles, de la plus en avant à la plus en arrière."""
    sortie = []
    Rappel = ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)

    def rappel(h, _l):
        if user32.IsWindowVisible(h) and not user32.IsIconic(h) and user32.GetWindowTextLengthW(h) > 0:
            sortie.append(h)
        return True
    user32.EnumWindows(Rappel(rappel), 0)
    return sortie


def fenetres_reduites(titre):
    """Les fenêtres réduites dans la barre des tâches dont le titre contient ce texte (hors celles des pigeons)."""
    t, sortie, pid = titre.casefold(), [], ctypes.c_ulong()
    Rappel = ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)

    def rappel(h, _l):
        if user32.IsWindowVisible(h) and user32.IsIconic(h) and t in titre_de(h).casefold():
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value != os.getpid():
                sortie.append(h)
        return True
    user32.EnumWindows(Rappel(rappel), 0)
    return sortie


# Le nom qu'on dit à l'utilisateur pour un programme (la balise : « Chrome › onglet « Gemini » › bouton « Envoyer » »).
NOMS_D_APPS = {"chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "brave.exe": "Brave",
               "explorer.exe": "Explorateur", "claude.exe": "Claude", "code.exe": "VS Code", "cursor.exe": "Cursor",
               "antigravity.exe": "Antigravity", "windowsterminal.exe": "Terminal", "powershell.exe": "PowerShell",
               "cmd.exe": "Invite de commandes", "notepad.exe": "Bloc-notes", "winword.exe": "Word",
               "excel.exe": "Excel", "powerpnt.exe": "PowerPoint", "obsidian.exe": "Obsidian", "discord.exe": "Discord",
               "steam.exe": "Steam", "steamwebhelper.exe": "Steam", "godot.exe": "Godot"}
_APPS = {}


def app_de(hwnd):
    """(nom à dire, chemin de l'exécutable) du programme d'une fenêtre ; gardé par processus. Le nom vient d'une
    petite table, sinon de la description du fichier, sinon du nom de l'exécutable."""
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(W.HWND(hwnd), ctypes.byref(pid))
    if pid.value in _APPS:
        return _APPS[pid.value]
    exe = ""
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, pid.value)                     # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        b, n = ctypes.create_unicode_buffer(520), W.DWORD(520)
        if k32.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(n)):
            exe = b.value
        k32.CloseHandle(h)
    base = os.path.basename(exe).lower()
    if base == "applicationframehost.exe":
        return titre_de(hwnd) or "Windows", exe    # l'hôte des apps du Windows Store : son titre dit l'app (pas gardé)
    if base.startswith("godot"):
        base = "godot.exe"
    nom = NOMS_D_APPS.get(base)
    if not nom and exe:
        try:
            import win32api
            lang, page = win32api.GetFileVersionInfo(exe, "\\VarFileInfo\\Translation")[0]
            nom = win32api.GetFileVersionInfo(exe, f"\\StringFileInfo\\{lang:04x}{page:04x}\\FileDescription")
        except Exception:
            nom = None
    nom = tr(nom or os.path.splitext(os.path.basename(exe))[0] or "?")
    if len(_APPS) > 300:
        _APPS.clear()
    _APPS[pid.value] = (nom, exe)
    return nom, exe


def nom_ecran(ecrans, x, y):
    """« écran de gauche », « écran du bas »... par rapport à l'écran principal (pour la balise et montre.py)."""
    e = ecran_de(ecrans, x, y)
    p = next((e for e in ecrans if e["principal"]), None)
    if not e or not p or e is p:
        return tr("écran principal")
    (l, t, r, b), (pl, pt, pr, pb) = e["rect"], p["rect"]
    if r <= pl:
        return tr("écran de gauche")
    if l >= pr:
        return tr("écran de droite")
    return tr("écran du bas") if t >= pb else tr("écran du haut")


# Les genres de l'automatisation de Windows, en mots (la balise : « bouton « Envoyer » »).
GENRES = {50000: "bouton", 50031: "bouton", 50005: "lien", 50019: "onglet", 50007: "élément", 50024: "élément",
          50011: "menu", 50002: "case", 50013: "option", 50004: "zone de texte", 50003: "liste", 50020: "texte",
          50030: "page", 50006: "image", 50026: "groupe"}
CLIQUABLES = (50000, 50031, 50005, 50019, 50007, 50024, 50011, 50002, 50013, 50004, 50003)


# ------------------------------------------------------ les journaux de Claude

def heure_de(ligne):
    """L'heure d'une ligne de journal (« 2026-10-02T13:11:00.271Z ») en secondes."""
    t = ligne.get("timestamp")
    if not t:
        return None
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# Un chemin Windows (C:\... ou C:/...) ou à la façon de Git Bash (/c/...) dans une commande.
# La lettre du lecteur ne doit pas suivre une autre lettre : « https://... » contient « s:/ », qui n'est pas un chemin.
RE_CHEMIN = re.compile(r'(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?<![A-Za-z0-9:])/[a-zA-Z]/)[^"\'`\r\n|<>*?;]+')


def plus_long_existant(brut):
    """Dans « C:\\x\\y.md -Force », garde le plus long début qui existe sur le disque."""
    s = brut.strip()
    if re.match(r"^/[a-zA-Z]/", s):
        s = s[1].upper() + ":" + s[2:]
    s = s.replace("/", "\\")
    coupes = [i for i, ch in enumerate(s) if ch in " \\"] + [len(s)]
    for fin in sorted(set(coupes), reverse=True):
        essai = s[:fin].rstrip(" \\")
        if len(essai) > 3 and os.path.exists(essai):
            return os.path.normpath(essai)
    return None


def chemin_touche(outil, entree, dossier_courant):
    """Le fichier ou le dossier qu'un appel d'outil touche ; None si on ne sait pas."""
    for champ in ("file_path", "notebook_path", "path"):
        v = entree.get(champ)
        if isinstance(v, str) and v:
            if not os.path.isabs(v) and dossier_courant:
                v = os.path.join(dossier_courant, v)
            return os.path.normpath(v)
    if outil in ("Glob", "Grep"):
        return dossier_courant
    if outil in ("Bash", "PowerShell"):
        commande = entree.get("command") or ""
        if "montre.py" in commande:
            return None                    # un appel au pigeon lui-même ne dit pas où la session travaille
        # « cd dossier && ... fichier » : le chemin le plus profond dit le mieux où la session travaille.
        trouves = [plus_long_existant(m.group(0)) for m in RE_CHEMIN.finditer(commande)]
        trouves = [c for c in trouves if c]
        if trouves:
            return max(trouves, key=lambda c: c.count(os.sep))
    return None


RE_LIEN_MD = re.compile(r"\[([^\]\n]{1,80})\]\(([^)\s]+)\)")
RE_URL = re.compile(r"https?://[^\s)>\]\"'`]+")
RE_BLOC = re.compile(r"^[ \t]*```[^\n`]*\n(.*?)\n[ \t]*```", re.S | re.M)   # un bloc de code Markdown, son contenu seul
# Une invite à coller dans une nouvelle séance (6 octobre 2026) : le prompt de reprise d'un projet.
RE_INVITE = re.compile(r"PROMPT_PROCHAINE_SESSION|\bLis en entier\b|^Ma mission\s*:", re.I | re.M)
RE_SEANCE_DANS = re.compile(r"(?:séance|session)\s+(?:neuve\s+|fraîche\s+|nouvelle\s+)?dans\s+(?:`([^`\n]{3,80})`|([^\s`,;]+))",
                            re.I)


def dossier_de_l_invite(bloc, texte):
    """Le dossier où ouvrir la séance d'une invite : celui du premier fichier qu'elle cite (« Lis en entier
    C:\\...\\Mon projet\\PROMPT_PROCHAINE_SESSION.txt » : Mon projet), sinon « séance dans `Desktop\\X` » dans la
    réponse (relatif au dossier de l'utilisateur). None si on ne sait pas."""
    for m in RE_CHEMIN.finditer(bloc):
        c = plus_long_existant(m.group(0))
        if c:
            return c if os.path.isdir(c) else os.path.dirname(c)
    m = RE_SEANCE_DANS.search(texte or "")
    if m:
        brut = (m.group(1) or m.group(2)).strip().rstrip(".:").replace("/", os.sep)
        for c in (brut, os.path.join(str(Path.home()), brut), os.path.join(str(Path.home() / "Desktop"), brut)):
            if os.path.isabs(c) and os.path.isdir(c):
                return os.path.normpath(c)
    return None


def sorties_de(texte, dossier):
    """Les liens et les fichiers qu'une réponse de Claude cite (l'utilisateur, 12h07 : « je me demande où sont les
    output ; accélérer le workflow sans chercher dans mon ordi ou mes navigateurs »).
    Rend [{"genre": "lien" | "fichier" | "texte", "valeur": l'adresse, le chemin complet ou le texte, "nom": ce qu'on
    affiche}], sans doublon, 8 au plus. Les liens Markdown relatifs se lisent depuis le dossier de la session ;
    un « :42 » de numéro de ligne est retiré ; on ne garde que les fichiers qui existent.
    Les blocs de code (```...```) viennent en premier, 3 au plus (l'utilisateur, 3 octobre, 18h29 : « j'aurai aimé cliqué sur le
    bouton pour copier le prompt ») : un prompt ou une commande à coller se copie d'un clic."""
    from urllib.parse import unquote, urlparse
    items, vus = [], set()

    def ajouter(genre, valeur, nom, **plus):
        cle = valeur.casefold()
        if cle not in vus and len(items) < 8:
            vus.add(cle)
            items.append({"genre": genre, "valeur": valeur, "nom": nom, **plus})

    for bloc in RE_BLOC.findall(texte or "")[:3]:
        bloc = bloc.strip("\r\n")
        if len(bloc.strip()) >= 20:                 # un mot seul ne vaut pas un bouton
            premiere = next((l.strip() for l in bloc.splitlines() if l.strip()), "")
            if RE_INVITE.search(bloc):
                # Une invite de séance (l'utilisateur, 6 octobre 2026 : « ouvre une séance dans X et colle le prompt », le
                # geste le plus fréquent, n'était jamais montré) : Copier, et « Nouvelle séance ».
                ajouter("invite", bloc, premiere, dossier=dossier_de_l_invite(bloc, texte))
            else:
                ajouter("texte", bloc, premiere)

    for nom, cible in RE_LIEN_MD.findall(texte or ""):
        if cible.startswith(("http://", "https://")):
            ajouter("lien", cible, nom)
            continue
        chemin = re.sub(r":\d+(-\d+)?$", "", unquote(cible.split("#")[0]))
        if chemin.startswith("computer://"):
            chemin = chemin[len("computer://"):]
        if not os.path.isabs(chemin) and dossier:
            chemin = os.path.join(dossier, chemin)
        chemin = os.path.normpath(chemin)
        if os.path.exists(chemin):
            ajouter("fichier", chemin, nom)
    for url in RE_URL.findall(texte or ""):
        url = url.rstrip(".,;:!?")
        ajouter("lien", url, urlparse(url).netloc or url)
    for m in RE_CHEMIN.finditer(texte or ""):
        c = plus_long_existant(m.group(0))
        if c and len(c) > 12:
            ajouter("fichier", c, os.path.basename(c) or c)
    return items


# Codex et Antigravity (AG) suivis seuls (6 octobre 2026) : les bases où chacun range ses conversations, lues en
# lecture seule. Vérifié ce jour-là : AG, conversation_summaries (title, status CASCADE_RUN_STATUS_IDLE quand il a
# fini, last_modified_time, last_user_input_time) ; Codex, threads (title, cwd, updated_at_ms, archived, source).
BASE_AG = Path.home() / ".gemini" / "antigravity" / "conversation_summaries.db"
BASE_CODEX = Path.home() / ".codex" / "state_5.sqlite"
SUIVI_S = 30 * 60           # une conversation touchée depuis moins de 30 min : suivie
CODEX_FINI_S = 90           # un fil de Codex immobile depuis 90 s : il a fini son tour


def lire_base(chemin, requete):
    """Les lignes d'une base SQLite d'une autre IA, en lecture seule ; [] si elle dort depuis 30 min (on ne l'ouvre
    même pas) ou si elle est occupée."""
    import sqlite3
    try:
        touchee = max(p.stat().st_mtime for p in (chemin, chemin.with_name(chemin.name + "-wal")) if p.exists())
    except ValueError:
        return []
    if time.time() - touchee > SUIVI_S:
        return []
    c = sqlite3.connect(f"file:{chemin.as_posix()}?mode=ro", uri=True, timeout=0.5)
    try:
        return c.execute(requete).fetchall()
    finally:
        c.close()


def heure_iso(t):
    """« 2026-10-04 03:33:02.3094983+00:00 » (7 décimales, qu'ISO n'accepte pas) en secondes."""
    return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", str(t).replace(" ", "T"))).timestamp()


def conversations_ag(maintenant):
    """Les conversations d'AG vivantes : au travail, ou qui ont répondu après la dernière question de l'utilisateur."""
    from urllib.parse import unquote
    vues = []
    for cid, titre, statut, pas_fini, modif, entree, espaces, prof in lire_base(BASE_AG, (
            "select conversation_id, title, status, not_fully_idle, last_modified_time, last_user_input_time, "
            "workspace_uris, nesting_depth from conversation_summaries order by last_modified_time desc limit 5")):
        try:
            m, u = heure_iso(modif), (heure_iso(entree) if entree else 0)
        except ValueError:
            continue
        if prof or maintenant - m > SUIVI_S:
            continue
        travaille = ("IDLE" not in (statut or "")) or bool(pas_fini)
        if travaille and maintenant - m > 600:
            travaille = False                     # un état « en cours » resté collé
        uri = re.search(r"file:///([^\s\"',\]]+)", espaces or "")
        dossier = os.path.normpath(unquote(uri.group(1))) if uri else None
        v = {"session": f"ag-{cid[:8]}", "titre": f"AG · {court(titre or 'conversation', 40)}", "ia": "Antigravity",
             "app": "Antigravity", "dossier": dossier if dossier and os.path.isdir(dossier) else None, "heure": m}
        if not travaille:
            if m < u + 2:
                continue                          # c'est l'utilisateur qui a écrit en dernier : AG va travailler
            v["attend"] = m
        vues.append(v)
    return vues


def fils_codex(maintenant):
    """Les fils de Codex vivants (pas les sous-agents ni les archivés) : au travail, ou fini depuis 90 s."""
    vues = []
    for tid, titre, cwd, maj_ms, maj, archive, source in lire_base(BASE_CODEX, (
            "select id, title, cwd, updated_at_ms, updated_at, archived, source from threads "
            "order by coalesce(updated_at_ms, updated_at * 1000) desc limit 5")):
        m = (maj_ms or 0) / 1000 or float(maj or 0)
        if archive or str(source or "").startswith("{") or maintenant - m > SUIVI_S:
            continue
        dossier = re.sub(r"^\\\\\?\\", "", cwd or "")
        v = {"session": f"codex-{str(tid)[-8:]}", "titre": f"Codex · {court(titre or 'fil', 40)}", "ia": "Codex",
             "app": "Codex", "dossier": dossier if os.path.isdir(dossier) else None, "heure": m}
        if maintenant - m > CODEX_FINI_S:
            v["attend"] = m
        vues.append(v)
    return vues


def court(texte, n=160):
    """Une phrase courte pour une bulle : une seule ligne de blancs, coupée proprement."""
    t = " ".join((texte or "").split())
    t = re.sub(r"\*\*|`|^#+ ", "", t)      # le gras et les titres du Markdown n'ont rien à faire dans une bulle
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + " …"


def message_de_danny(d):
    """Vrai si une ligne « user » est un vrai message de l'utilisateur (pas un résultat d'outil, pas un rappel du système)."""
    if d.get("isMeta"):
        return False
    c = (d.get("message") or {}).get("content")
    if isinstance(c, str):
        return bool(c.strip())
    if isinstance(c, list):
        types = {b.get("type") for b in c if isinstance(b, dict)}
        return "text" in types and "tool_result" not in types
    return False


class Session:
    """Ce qu'on sait d'une session (ou d'un sous-agent) en lisant son journal."""

    def __init__(self, fichier, ident, parent=None, titre=None):
        self.fichier = fichier
        self.ident = ident
        self.parent = parent            # l'ident de la session mère, pour un sous-agent
        self.titre = titre or ident[:8]
        self.couleur = None
        self.rang = 0
        self.chemin = None              # le dernier fichier touché
        self.outil = ""
        self.dossier_courant = None
        self.dernier_geste = 0.0
        self.gestes = deque(maxlen=200) # les heures des derniers outils, pour le rythme
        self.attend_depuis = None       # fin de tour ou question posée à l'utilisateur
        self.dernier_texte = ""         # la dernière phrase de Claude, pour la bulle
        self.texte_attente = ""         # ce que la session attend de l'utilisateur
        self.dernier_message_danny = 0.0
        self.demande = None             # ce que montre.py demande au pigeon de montrer
        self.importance = "basse"       # de l'attente : normale (une question), basse (fin de tour)
        self.signal = None              # la dernière notification de Claude Code (crochet_notification.py)
        self.dernier_fichier = None     # le dernier FICHIER touché (pas un dossier) et son heure
        self.dernier_fichier_t = 0.0
        self.reponse_en_cours = []      # les textes de la réponse depuis le dernier message de l'utilisateur
        self.sorties = []               # les liens et fichiers cités par la dernière réponse (sorties_de)
        self.derniere_ligne = 0.0       # l'heure de la dernière ligne « assistant » ou « user » du journal
        self.fini = False               # sous-agent qui a rendu son travail
        self.dernier_outil = 0.0        # l'heure du dernier outil lancé (pas les résultats ni les messages)
        self.contexte = 0               # la taille du contexte à la dernière réponse, en jetons
        self.ecrits = deque(maxlen=50)  # (fichier, heure) des écritures (Edit, Write...) : pour les conflits
        self.annonce = None             # pour une autre IA : sa dernière annonce (annonce.py)
        self.fermee = None              # l'heure où elle a été fermée (« Terminer », montre.py --termine)
        self.fermee_par = None          # « danny » (Terminer) ou « session » (montre.py --termine)
        self.livrables_vus = False      # l'utilisateur a cliqué « Oublier » sur ses livrables (voir Guetteur.livrables)
        self.archivee = False           # archivée dans l'app Claude (sa fiche, voir lire_fiches_app)
        self.position = None            # où on en est dans le fichier
        self.reste = b""

    def lire_ligne(self, d):
        t = d.get("type")
        if t == "custom-title" and d.get("customTitle"):
            self.titre = d["customTitle"]
            return
        quand = heure_de(d)
        if t == "queue-operation" and d.get("operation") == "enqueue" and quand:
            # Un message que l'utilisateur envoie pendant que la session travaille : il entre dans la file d'attente.
            self.dernier_message_danny = quand
            return
        self.dossier_courant = d.get("cwd") or self.dossier_courant
        if t in ("assistant", "user") and quand:
            self.derniere_ligne = max(self.derniere_ligne, quand)   # une ligne après la permission : elle est réglée
        if t == "assistant":
            m = d.get("message") if isinstance(d.get("message"), dict) else {}
            u = m.get("usage") if isinstance(m.get("usage"), dict) else {}
            if u:
                # Ce que la session a relu pour répondre : la taille de son contexte en ce moment.
                self.contexte = sum(int(u.get(k) or 0) for k in
                                    ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            for bloc in m.get("content") or []:
                if not isinstance(bloc, dict):
                    continue
                if bloc.get("type") == "text" and bloc.get("text", "").strip():
                    self.dernier_texte = bloc["text"]
                    self.reponse_en_cours.append(bloc["text"])
                if bloc.get("type") == "tool_use":
                    self.outil = bloc.get("name") or ""
                    entree = bloc.get("input") or {}
                    if quand:
                        self.dernier_geste = quand
                        self.dernier_outil = quand
                        self.gestes.append(quand)
                    # Une question posée à l'utilisateur : le pigeon va le chercher, la question dans sa bulle.
                    if self.outil == "AskUserQuestion":
                        self.attend_depuis = quand
                        self.importance = "normale"         # une question posée
                        qs = entree.get("questions") or [{}]
                        self.texte_attente = qs[0].get("question", "") if isinstance(qs[0], dict) else ""
                    else:
                        self.attend_depuis = None
                    c = chemin_touche(self.outil, entree, self.dossier_courant)
                    if c and quand and self.outil in OUTILS_ECRITURE:
                        self.ecrits.append((c, quand))
                    if c:
                        self.chemin = c
                        if os.path.isfile(c):
                            self.dernier_fichier, self.dernier_fichier_t = c, quand or time.time()
            if m.get("stop_reason") == "end_turn":
                if self.parent:
                    self.fini = True
                else:
                    self.attend_depuis = quand
                    self.importance = "basse"               # elle a fini son tour : à toi quand tu veux
                    self.texte_attente = self.dernier_texte
                    self.sorties = sorties_de("\n".join(self.reponse_en_cours), self.dossier_courant)
                    self.dernier_geste = quand or self.dernier_geste
        elif t == "user":
            # l'utilisateur a répondu ou écrit : la session repart.
            self.attend_depuis = None
            if quand:
                self.dernier_geste = max(self.dernier_geste, quand)
                if message_de_danny(d):
                    self.reponse_en_cours = []          # une nouvelle demande de l'utilisateur : une nouvelle réponse
                    self.dernier_message_danny = quand

    def est_fermee(self):
        """Fermée par l'utilisateur (« Terminer », Ctrl+Alt+T, clic droit), par elle-même (montre.py --termine), ou
        archivée dans l'app Claude. Elle se rouvre si l'utilisateur lui écrit, si elle demande une permission ou un geste,
        ou si elle relance un outil plus de 2 min après (le temps d'écrire sa dernière réponse)."""
        if self.archivee:
            return True
        if not self.fermee:
            return False
        f = self.fermee
        rouverte = (self.dernier_message_danny > f + 2
                    or (self.signal is not None and self.signal.get("heure", 0) > f)
                    or (self.demande is not None and self.demande.get("heure", 0) > f)
                    or self.dernier_outil > f + FERMEE_GRACE_S)
        return not rouverte

    def lire_la_suite(self):
        """Lit ce qui s'est ajouté au journal depuis le dernier tour."""
        taille = self.fichier.stat().st_size
        if self.position is None:
            self.position = max(0, taille - LECTURE_INITIALE)
            premiere = self.position > 0
        else:
            premiere = False
        if taille <= self.position:
            return
        with open(self.fichier, "rb") as f:
            f.seek(self.position)
            neuf = f.read(taille - self.position)
        self.position = taille
        lignes = (self.reste + neuf).split(b"\n")
        self.reste = lignes.pop()          # une ligne pas encore finie attend le tour suivant
        if premiere and lignes:
            lignes.pop(0)                  # on est tombé au milieu d'une ligne
        for brute in lignes:
            try:
                self.lire_ligne(json.loads(brute))
            except (ValueError, UnicodeDecodeError):
                continue

    def rythme(self, maintenant):
        """Le nombre d'outils de la dernière minute : plus il est grand, plus le pigeon picosse vite."""
        return sum(1 for g in self.gestes if maintenant - g < 60)


# ----------------------------------------------------------- le guetteur

class Guetteur(threading.Thread):
    """Chaque seconde : lit les journaux et les demandes, trouve les icônes, calcule où va chaque pigeon."""

    def __init__(self, partage, verrou, ecrans):
        super().__init__(daemon=True)
        self.partage, self.verrou, self.ecrans = partage, verrou, ecrans
        self.sessions = {}
        self.couleurs_donnees = 0
        self.erreurs_vues = set()
        self.cache_icones = {}           # hwnd -> (heure de lecture, cadre de la fenêtre, icônes)
        self.cache_elements = {}         # (titre, élément) -> (heure, rect, hwnd)
        self.fenetres_retenues = {}      # titre demandé -> hwnd trouvé (le titre peut changer ensuite)
        self.infos_elements = {}         # (titre, élément, fenêtre) -> {genre, nom, hors} : pour la balise
        self.parc_info = None            # où ranger les pigeons qui attendent (voir trouver_parc)
        self.fiches_app = {}             # fiche de l'app Claude -> (heure de modification, session, archivée)
        self.archivees = set()           # les sessions archivées dans l'app Claude
        self.t_fiches = 0.0
        self.conflits = []               # [(fichier, [titres])] : deux IA qui écrivent le même fichier (le panneau)
        self.livrables = []              # les livrables des sessions qui se sont terminées elles-mêmes (le panneau)
        self.t_activite = 0.0
        self.t_suivi = 0.0               # le suivi de Codex et d'AG (suivre_les_autres_ia), toutes les 5 s
        self.suivis = {}                 # session -> l'annonce écrite pour elle la dernière fois
        self.tours = 0
        self.battement = time.time()     # la fin du dernier tour : l'affichage s'en sert pour voir s'il est figé
        self.actif = True                # faux quand l'affichage l'a remplacé par un autre guetteur
        self.signale = False             # sa pile est déjà dans le journal

    # -- Windows : l'automatisation (UIA) lit le nom et la place des icônes et des boutons
    def preparer_uia(self):
        import comtypes, comtypes.client
        comtypes.CoInitializeEx(comtypes.COINIT_APARTMENTTHREADED)
        import pythoncom
        pythoncom.CoInitialize()
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as U
        import win32com.client
        self.U = U
        self.uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
        self.cond_item = self.uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_ListItemControlTypeId)
        self.cache_req = self.uia.CreateCacheRequest()
        for p in (U.UIA_NamePropertyId, U.UIA_BoundingRectanglePropertyId, U.UIA_IsOffscreenPropertyId):
            self.cache_req.AddProperty(p)
        self.shell = win32com.client.Dispatch("Shell.Application")

    def run(self):
        # La préparation peut échouer à l'ouverture de session de Windows (5 octobre 2026, 19h11 : le guetteur est mort
        # là, sans un mot). On la refait toutes les 5 s, en l'écrivant dans le journal.
        while self.actif:
            try:
                self.preparer_uia()
                break
            except Exception:
                log.exception("préparation de l'automatisation de Windows (nouvel essai dans 5 s)")
                time.sleep(5)
        while self.actif:
            try:
                self.tour()
            except Exception:
                log.exception("tour du guetteur")
            self.battement = time.time()
            time.sleep(TOUR_S)

    # -- 1. les journaux et les demandes
    def trouver_journaux(self, maintenant):
        if not PROJETS.exists():
            return
        for projet in PROJETS.iterdir():
            if not projet.is_dir():
                continue
            for f in projet.glob("*.jsonl"):
                try:
                    vieux = maintenant - f.stat().st_mtime
                except OSError:
                    continue
                if vieux < SESSION_VIVANTE_S and f.stem not in self.sessions:
                    self.sessions[f.stem] = Session(f, f.stem)
                    self.donner_couleur(self.sessions[f.stem])
                if vieux < SESSION_VIVANTE_S:
                    self.trouver_sous_agents(projet / f.stem / "subagents", f.stem, maintenant)

    def trouver_sous_agents(self, dossier, parent, maintenant):
        if not dossier.is_dir():
            return
        for f in dossier.glob("agent-*.jsonl"):
            if f.stem in self.sessions:
                continue
            try:
                if maintenant - f.stat().st_mtime > SOUS_AGENT_VIVANT_S:
                    continue
            except OSError:
                continue
            titre = None
            meta = f.with_suffix(".meta.json")
            if meta.exists():
                try:
                    titre = json.loads(meta.read_text(encoding="utf-8")).get("description")
                except (ValueError, OSError):
                    pass
            self.sessions[f.stem] = Session(f, f.stem, parent=parent, titre=titre)

    def donner_couleur(self, s):
        """Une couleur par tâche, qui ne change pas d'une relance à l'autre (l'utilisateur repère ses sessions par elle) :
        elle est gardée dans couleurs.json ; une nouvelle session prend la première couleur libre."""
        s.rang = self.couleurs_donnees
        self.couleurs_donnees += 1
        f = ICI / "couleurs.json"
        try:
            gardees = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            gardees = {}
        if s.ident in gardees:
            s.couleur = gardees[s.ident]
            return
        prises = {x.couleur for x in self.sessions.values() if x.couleur and not x.parent}
        s.couleur = next((c for c in COULEURS if c not in prises), COULEURS[s.rang % len(COULEURS)])
        gardees[s.ident] = s.couleur
        try:
            f.write_text(json.dumps(dict(list(gardees.items())[-200:]), indent=0), encoding="utf-8")
        except OSError:
            pass

    def lire_demandes(self, maintenant):
        """Les demandes de montre.py : une par session ; finies au prochain message de l'utilisateur ou à l'échéance."""
        DEMANDES.mkdir(exist_ok=True)
        (DEMANDES / "_vivant.txt").write_text(str(maintenant), encoding="utf-8")   # montre.py sait qu'on vole
        for s in self.sessions.values():
            s.demande = None
        for f in DEMANDES.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            s = self.sessions.get(d.get("session"))
            if s is None and d.get("session"):
                # Une autre IA (Cowork, Gemini...) qui n'a pas de journal Claude Code : elle reçoit son propre
                # pigeon, qui vit tant que sa demande existe (l'utilisateur, 10h32 : « Claude Code, Cowork et autre IA »).
                s = Session(f, d["session"], titre=d.get("titre") or d["session"])
                s.dernier_geste = maintenant
                self.donner_couleur(s)
                self.sessions[s.ident] = s
            finie = maintenant - d.get("heure", 0) > d.get("duree_s", 900)
            if s and s.dernier_message_danny > d.get("heure", 0):
                finie = True                   # l'utilisateur a répondu à la session : le geste est fait
            if finie:
                try:
                    f.unlink()
                except OSError:
                    pass
            elif s:
                s.demande = d

    def lire_signaux(self, maintenant):
        """Les notifications de Claude Code (permission à donner, formulaire...), une par session ; on oublie
        celles de plus d'une heure."""
        if not SIGNAUX.is_dir():
            return
        for f in SIGNAUX.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if maintenant - d.get("heure", 0) > 3600:
                try:
                    f.unlink()
                except OSError:
                    pass
                continue
            s = self.sessions.get(d.get("session"))
            if s and s.derniere_ligne > d.get("heure", 0) + 1:
                # La session est repartie après la notification (la permission est donnée) : on range le signal
                # (idée d'AG, 2 octobre ; il ne comptait déjà plus, voir placer).
                try:
                    f.unlink()
                except OSError:
                    pass
                s.signal = None
                continue
            if s:
                s.signal = d

    def lire_annonces(self, maintenant):
        """Les annonces des autres IA (annonce.py) : AG, Cowork ou un script disent où ils travaillent. Chacune reçoit
        sa session (comme une demande de montre.py), qui vit tant que son annonce n'a pas expiré."""
        if not ANNONCES.is_dir():
            return
        for f in ANNONCES.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if maintenant - d.get("heure", 0) > d.get("duree_s", 600):
                f.unlink(missing_ok=True)          # l'annonce a expiré
                continue
            ident = d.get("session")
            if not ident:
                continue
            s = self.sessions.get(ident)
            if s is None:
                s = Session(f, ident, titre=d.get("titre") or ident)
                self.donner_couleur(s)
                self.sessions[ident] = s
            s.annonce = d
            s.titre = d.get("titre") or s.titre
            s.chemin = d.get("fichier") or d.get("dossier")
            s.dernier_geste = max(s.dernier_geste, d.get("heure", 0))
            s.outil = tr("écrit") if d.get("ecrit") else tr("travaille")
            if d.get("ecrit") and d.get("fichier") and (d["fichier"], d["heure"]) not in s.ecrits:
                s.ecrits.append((d["fichier"], d["heure"]))
            if d.get("attend"):
                # Codex ou AG a fini son tour (suivre_les_autres_ia) : sa carte « t'attend », sans ligne (basse).
                s.attend_depuis = d["attend"]
                s.importance = "basse"
                s.texte_attente = tr("{ia} a fini son tour : à toi de jouer", ia=d.get("ia") or ident)
                s.outil = tr("attend")
            else:
                s.attend_depuis = None

    def suivre_les_autres_ia(self, maintenant):
        """Codex et Antigravity (AG) suivis seuls, sans qu'ils appellent rien (l'utilisateur, 6 octobre 2026 : « des oublis
        d'utiliser l'app »). Toutes les 5 s, on lit en lecture seule la base où chacun range ses conversations, et on
        écrit pour eux une annonce (comme annonce.py) : au travail, ou « a fini son tour » (sa carte t'attend 30 min).
        Une IA qui s'annonce elle-même (le serveur MCP, annonce.py) passe avant : on ne réécrit pas son annonce."""
        if maintenant - self.t_suivi < 5:
            return
        self.t_suivi = maintenant
        try:
            vues = conversations_ag(maintenant) + fils_codex(maintenant)
        except Exception as ex:                  # une base illisible ne doit jamais arrêter le guetteur
            log.warning("suivi de Codex et d'AG : %s", ex)
            return
        ANNONCES.mkdir(exist_ok=True)
        for v in vues:
            f = ANNONCES / f"{v['session']}.json"
            propre = None
            for g in ANNONCES.glob("*.json"):
                try:
                    a = json.loads(g.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    continue
                if a.get("ia") == v["ia"] and not a.get("par_suivi") and maintenant - a.get("heure", 0) < 600:
                    propre = a                       # elle s'annonce déjà elle-même
            if propre:
                continue
            annonce = {"session": v["session"], "titre": v["titre"], "ia": v["ia"], "app": v["app"],
                       "fichier": None, "dossier": v.get("dossier"), "ecrit": False, "par_suivi": True,
                       "heure": v["heure"], "duree_s": 600 if not v.get("attend") else 1800,
                       **({"attend": v["attend"]} if v.get("attend") else {})}
            if self.suivis.get(v["session"]) == annonce:
                continue                             # rien de neuf : on n'écrit pas
            self.suivis[v["session"]] = annonce
            try:
                provisoire = f.with_suffix(".tmp")
                provisoire.write_text(json.dumps(annonce, ensure_ascii=False), encoding="utf-8")
                os.replace(provisoire, f)
            except OSError as ex:
                log.warning("annonce de %s : %s", v["session"], ex)

    def calculer_conflits(self, maintenant):
        """Deux sessions ou IA qui ont écrit le même fichier à moins de 5 min : un conflit possible. Les écritures
        d'un sous-agent comptent pour sa session mère."""
        par_fichier = {}
        for s in self.sessions.values():
            mere = self.sessions.get(s.parent) if s.parent else s
            if mere is None or mere.est_fermee():
                continue
            for chemin, quand in s.ecrits:
                if maintenant - quand < CONFLIT_S:
                    par_fichier.setdefault(os.path.normcase(chemin), {})[mere.ident] = (mere.titre, chemin)
        self.conflits = [(next(iter(qui.values()))[1], sorted(t for t, _c in qui.values()))
                         for qui in par_fichier.values() if len(qui) > 1]

    def ecrire_activite(self, maintenant, etats):
        """Le registre activite.json, toutes les 2 s : qui travaille où, pour toutes les IA (annonce.py --qui le lit).
        Écrit à côté puis renommé : jamais lu à moitié."""
        if maintenant - self.t_activite < 2:
            return
        self.t_activite = maintenant
        etat_lisible = {"montre": "montre un geste", "appel": "attend", "attend": "attend", "repos": "repos"}
        sessions = []
        for s in self.sessions.values():
            if s.parent or s.ident not in etats or s.est_fermee():
                continue
            ecrits = [{"fichier": c, "heure": datetime.fromtimestamp(q).isoformat(timespec="seconds")}
                      for c, q in s.ecrits if maintenant - q < 600]
            sessions.append({
                "session": s.ident, "titre": s.titre,
                "ia": (s.annonce or {}).get("ia") or ("Claude Code" if s.fichier.suffix == ".jsonl" else s.titre),
                "etat": etat_lisible.get(etats[s.ident]["mode"], "travaille"), "outil": s.outil,
                # Pour l'IA qui a fait une demande (montre.py) : sa cible est-elle trouvée à l'écran, et sinon pourquoi.
                "demande": ({"texte": (etats[s.ident].get("bulle") or "").split("\n")[0],
                             "trouvee": bool(etats[s.ident].get("trouvee")),
                             "precision": etats[s.ident].get("precision") or "",
                             # « cree » : l'heure de la demande (montre.py attend la réponse à SA demande) ; « ou » : ce
                             # que la balise dit à l'utilisateur (l'app, l'onglet, l'élément, ce qui le couvre, les noms proches).
                             "cree": (s.demande or {}).get("heure"),
                             "point": etats[s.ident].get("cible"),
                             "ou": {k: v for k, v in (etats[s.ident].get("ou") or {}).items() if k != "exe"}}
                            if etats[s.ident]["mode"] == "montre" else None),
                "fichier": s.chemin, "dossier": projet_de(s.chemin), "ecrits": ecrits,
                "dernier_geste": datetime.fromtimestamp(s.dernier_geste).isoformat(timespec="seconds")
                if s.dernier_geste else None})
        registre = {"maj": maintenant, "maj_lisible": datetime.fromtimestamp(maintenant).isoformat(timespec="seconds"),
                    "sessions": sessions,
                    "conflits": [{"fichier": f, "qui": q} for f, q in self.conflits]}
        try:
            provisoire = ACTIVITE.with_suffix(".tmp")
            provisoire.write_text(json.dumps(registre, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(provisoire, ACTIVITE)
        except OSError as e:
            log.warning("registre d'activité : %s", e)

    def lire_fermetures(self, maintenant):
        """Les sessions fermées (l'utilisateur, 13h02 : « la session est terminée et il y a encore un indicateur ») : par
        l'utilisateur (« Terminer », Ctrl+Alt+T, clic droit sur le pigeon) ou par elles-mêmes (montre.py --termine).
        Un fichier par session dans fermetures\\, oublié après 3 jours, ou dès que la session repart."""
        fermes = {}
        if FERMETURES.is_dir():
            for f in FERMETURES.glob("*.json"):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    continue
                if maintenant - d.get("heure", 0) > 3 * 86400:
                    f.unlink(missing_ok=True)
                    continue
                fermes[f.stem] = d
        for s in self.sessions.values():
            d = fermes.get(s.ident) or {}
            s.fermee = d.get("heure", 0) if d else None
            s.fermee_par = d.get("par")
            s.livrables_vus = bool(d.get("livrables_vus"))
            s.archivee = s.ident in self.archivees
            if s.fermee and not s.est_fermee():
                # Elle est repartie (l'utilisateur lui a écrit, ou elle travaille encore) : la fermeture est oubliée.
                (FERMETURES / f"{s.ident}.json").unlink(missing_ok=True)
                s.fermee = None
                log.info("session rouverte : %s", s.titre)

    def lire_fiches_app(self, maintenant):
        """Les fiches de session de l'app Claude (%APPDATA%\\Claude\\claude-code-sessions\\...\\local_<id>.json) :
        archiver une session dans Claude la ferme aussi. Relues toutes les 5 s, et seulement celles qui ont changé."""
        if maintenant - self.t_fiches < 5 or not FICHES_APP.is_dir():
            return
        self.t_fiches = maintenant
        vues = set()
        for f in FICHES_APP.rglob("local_*.json"):
            vues.add(f)
            try:
                mtime = f.stat().st_mtime
                if f in self.fiches_app and self.fiches_app[f][0] == mtime:
                    continue
                d = json.loads(f.read_text(encoding="utf-8"))
                self.fiches_app[f] = (mtime, d.get("cliSessionId"), bool(d.get("isArchived")))
            except (OSError, ValueError, AttributeError):
                continue
        for f in list(self.fiches_app):
            if f not in vues:
                del self.fiches_app[f]
        self.archivees = {cli for _m, cli, archivee in self.fiches_app.values() if cli and archivee}

    # -- 2. les fenêtres, les icônes, les boutons
    def liste_du_bureau(self):
        """La liste des icônes du Bureau (une SysListView32 cachée sous Progman ou un WorkerW)."""
        prog = user32.FindWindowW("Progman", None)
        vue = user32.FindWindowExW(prog, None, "SHELLDLL_DefView", None)
        w = None
        while not vue:
            w = user32.FindWindowExW(None, w, "WorkerW", None)
            if not w:
                return None
            vue = user32.FindWindowExW(w, None, "SHELLDLL_DefView", None)
        liste = user32.FindWindowExW(vue, None, "SysListView32", None)
        return liste if liste and user32.IsWindowVisible(liste) else None

    def fenetres_explorateur(self):
        """Les dossiers ouverts dans l'Explorateur : (hwnd, chemin), les réduits en moins."""
        sortie = []
        for w in self.shell.Windows():
            try:
                chemin, hwnd = w.Document.Folder.Self.Path, int(w.HWND)
            except Exception:
                continue
            if os.path.isdir(chemin) and not user32.IsIconic(W.HWND(hwnd)):
                sortie.append((hwnd, os.path.normpath(chemin)))
        return sortie

    def elements(self, hwnd, partout):
        """Les icônes d'une fenêtre : [(nom, rect, hors_ecran)].

        Lire les icônes coûte cher (mesuré : 0,18 s par fenêtre) ; on garde la lecture GARDE_ICONES_S
        secondes, sauf si la fenêtre a bougé ou changé de taille."""
        cadre = cadre_visible(hwnd)
        vieux = self.cache_icones.get(hwnd)
        if vieux and vieux[1] == cadre and time.time() - vieux[0] < GARDE_ICONES_S:
            return vieux[2]
        U = self.U
        sortie = []
        try:
            el = self.uia.ElementFromHandle(W.HWND(hwnd))
            portee = U.TreeScope_Descendants if partout else U.TreeScope_Children
            tab = el.FindAllBuildCache(portee, self.cond_item, self.cache_req)
            for i in range(tab.Length):
                it = tab.GetElement(i)
                r = it.CachedBoundingRectangle
                sortie.append((it.CachedName or "", (r.left, r.top, r.right, r.bottom), bool(it.CachedIsOffscreen)))
        except Exception as e:
            if str(e) not in self.erreurs_vues:
                self.erreurs_vues.add(str(e)); log.warning("lecture des icônes de %s : %s", hwnd, e)
        self.cache_icones[hwnd] = (time.time(), cadre, sortie)
        return sortie

    @staticmethod
    def meme_nom(affiche, vrai):
        """L'Explorateur cache souvent l'extension (et toujours .lnk) : on compare avec et sans."""
        a, v = affiche.casefold(), vrai.casefold()
        return a == v or a == os.path.splitext(v)[0]

    def chercher(self, hwnd, nom, partout):
        for n, rect, hors in self.elements(hwnd, partout):
            if self.meme_nom(n, nom):
                return rect, hors
        return None, None

    def trouver_fenetres(self, titre):
        """Les fenêtres dont le titre contient ce texte, de la plus en avant à la plus en arrière (sans celles des pigeons)."""
        t = titre.casefold()
        # On écarte les fenêtres de notre propre programme (panneau, pigeons, toiles), pas un titre : un Explorateur
        # ouvert sur le dossier « Pigeons » doit rester une cible possible.
        pid = ctypes.c_ulong()
        sortie = []
        for h in fenetres_visibles():
            user32.GetWindowThreadProcessId(W.HWND(h), ctypes.byref(pid))
            if pid.value != os.getpid() and t in titre_de(h).casefold():
                sortie.append(h)
        return sortie

    def trouver_element(self, titre, element, seulement=None):
        """Le bouton, le lien ou la case dont le nom contient « element », dans une fenêtre dont le titre
        contient « titre ». Plusieurs fenêtres peuvent porter le titre (« Mon projet » est aussi le nom
        d'une session) : on cherche dans chacune, la plus en avant d'abord, jusqu'à trouver.
        Une fenêtre trouvée une fois est retenue : son titre peut changer (l'Explorateur prend le nom du
        dossier qu'on ouvre) sans que le pigeon la perde. seulement : chercher dans cette fenêtre-là (celle de
        l'onglet demandé). Ce qu'on sait de l'élément (son genre, son nom, s'il faut défiler) va dans
        self.infos_elements, pour la balise."""
        cle = (titre, element, seulement)
        vieux = self.cache_elements.get(cle)
        if vieux and time.time() - vieux[0] < 2.0:
            return vieux[1], vieux[2]
        candidates = [seulement] if seulement else self.trouver_fenetres(titre)
        retenue = self.fenetres_retenues.get(titre)
        if not seulement and retenue and user32.IsWindow(W.HWND(retenue)) and retenue not in candidates:
            candidates.append(retenue)
        rect, hwnd = None, (candidates[0] if candidates else None)
        self.infos_elements[cle] = None
        if candidates and not element:
            rect = cadre_visible(hwnd)
        elif candidates:
            # 3 = la casse ignorée + une partie du nom suffit (Windows 10 1809 et plus)
            cond = self.uia.CreatePropertyConditionEx(self.U.UIA_NamePropertyId, element, 3)
            cherche = element.casefold().strip()
            for h in candidates:
                try:
                    tab = self.uia.ElementFromHandle(W.HWND(h)).FindAll(self.U.TreeScope_Descendants, cond)
                    # Le meilleur des noms qui contiennent « element » (5 octobre 2026 : « Envoyer » trouvait
                    # « Envoyer un commentaire » avant le vrai bouton) : le nom exact, puis celui qui commence ainsi,
                    # puis le plus court ; un élément visible avant un élément hors de la vue.
                    choix = []
                    for i in range(min(tab.Length, 40)):
                        el = tab.GetElement(i)
                        r = el.CurrentBoundingRectangle
                        if r.right <= r.left:
                            continue
                        nom = " ".join((el.CurrentName or "").split())
                        n = nom.casefold()
                        rang = (0 if n == cherche else 1 if n.startswith(cherche) else 2, bool(el.CurrentIsOffscreen), len(n), i)
                        choix.append((rang, el, nom, (r.left, r.top, r.right, r.bottom)))
                    if choix:
                        _rang, el, nom, rect = min(choix, key=lambda x: x[0])
                        hwnd = h
                        self.infos_elements[cle] = {"genre": GENRES.get(el.CurrentControlType, ""), "nom": nom or element,
                                                    "hors": bool(el.CurrentIsOffscreen)}
                        break
                except Exception as e:
                    log.warning("recherche de %r dans %r : %s", element, titre, e)
        if hwnd:
            self.fenetres_retenues[titre] = hwnd
        self.cache_elements[cle] = (time.time(), rect, hwnd)
        return rect, hwnd

    def trouver_onglet(self, titre, onglet):
        """L'onglet (d'un navigateur) dont le nom contient « onglet », dans une fenêtre dont le titre contient
        « titre » : (rect, affiché ?, fenêtre), ou None. L'automatisation de Windows ne voit que la page de l'onglet
        AFFICHÉ (essai du 5 octobre 2026, 23h : le bouton « Envoyer » de Gemini était introuvable, son onglet était
        caché) ; le guidage passe donc d'abord par l'onglet."""
        cle = ("onglet", titre, onglet)
        vieux = self.cache_elements.get(cle)
        if vieux and time.time() - vieux[0] < 1.0:
            return vieux[1]
        U, sortie = self.U, None
        cond = self.uia.CreateAndCondition(
            self.uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_TabItemControlTypeId),
            self.uia.CreatePropertyConditionEx(U.UIA_NamePropertyId, onglet, 3))
        for h in self.trouver_fenetres(titre) + fenetres_reduites(titre):
            try:
                el = self.uia.ElementFromHandle(W.HWND(h)).FindFirst(U.TreeScope_Descendants, cond)
                if el:
                    r = el.CurrentBoundingRectangle
                    motif = el.GetCurrentPattern(U.UIA_SelectionItemPatternId)
                    choisi = bool(motif and motif.QueryInterface(U.IUIAutomationSelectionItemPattern).CurrentIsSelected)
                    sortie = ((r.left, r.top, r.right, r.bottom), choisi, h)
                    break
            except Exception as e:
                log.warning("recherche de l'onglet %r dans %r : %s", onglet, titre, e)
        self.cache_elements[cle] = (time.time(), sortie)
        return sortie

    @staticmethod
    def zone_de_page(hwnd):
        """Le rectangle de la page dans un navigateur de la famille de Chrome (Chrome, Edge, l'app Claude) : sa fenêtre
        fille Chrome_RenderWidgetHostHWND visible la plus grande. Pour --page : les coordonnées de
        getBoundingClientRect y commencent."""
        zones = []
        Rappel = ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)

        def rappel(h, _l):
            if nom_de_classe(h) == "Chrome_RenderWidgetHostHWND" and user32.IsWindowVisible(h):
                r = W.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                zones.append((r.left, r.top, r.right, r.bottom))
            return True
        user32.EnumChildWindows(W.HWND(hwnd), Rappel(rappel), 0)
        return max(zones, key=lambda z: (z[2] - z[0]) * (z[3] - z[1]), default=None)

    def noms_proches(self, hwnd, element, n=6):
        """Quand « element » est introuvable : les noms des éléments cliquables visibles de la fenêtre qui lui
        ressemblent le plus (pour que l'IA vise juste au deuxième essai, sans deviner)."""
        import difflib
        cle = ("proches", hwnd, element)
        vieux = self.cache_elements.get(cle)
        if vieux and time.time() - vieux[0] < 5.0:
            return vieux[1]
        U, noms = self.U, []
        try:
            cond = None
            for g in CLIQUABLES:                     # « l'un de ces genres » : des OU deux à deux (sûr avec comtypes)
                c = self.uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, g)
                cond = c if cond is None else self.uia.CreateOrCondition(cond, c)
            tab = self.uia.ElementFromHandle(W.HWND(hwnd)).FindAllBuildCache(U.TreeScope_Descendants, cond, self.cache_req)
            for i in range(min(tab.Length, 600)):
                it = tab.GetElement(i)
                nom = " ".join((it.CachedName or "").split())
                if nom and not it.CachedIsOffscreen and nom not in noms:
                    noms.append(nom)
        except Exception as e:
            log.warning("noms proches de %r : %s", element, e)
        cherche = (element or "").casefold()
        proches = [x for x in noms if cherche and (cherche in x.casefold() or x.casefold() in cherche)]
        proches += [x for x in difflib.get_close_matches(element or "", noms, n=n, cutoff=0.62) if x not in proches]
        proches = [court(x, 40) for x in proches[:n]]
        self.cache_elements[cle] = (time.time(), proches)
        return proches

    def situer_session(self, titre, question=None):
        """Où répondre à une session qui attend, dans l'app Claude (l'utilisateur, 10h43 : une petite flèche près de la
        souris qui indique où aller) : la zone de saisie si la session est celle qu'on voit, sinon sa ligne dans
        la liste de gauche ; le bouton Claude de la barre des tâches si la fenêtre est cachée.
        Mesuré le 2 octobre : l'automatisation de Windows lit les titres de la liste (une ligne de 20 px de haut)
        et nomme le contenu ouvert du titre de sa session.
        question : le texte d'une question posée (AskUserQuestion). Si la session est ouverte, la cible devient son
        questionnaire, de la question au bouton « Envoyer » (l'utilisateur, 3 octobre 08h57 : « il faut que l'utilisateur
        choisisse de répondre au questionnaire »). Rend (point, zone, questionnaire) ; (None, None, False) sinon."""
        cle = ("__session__", titre, question)
        vieux = self.cache_elements.get(cle)
        if vieux and time.time() - vieux[0] < 2.0:
            return vieux[1], vieux[2], vieux[3]
        point = zone = None
        questionnaire = False
        h = user32.FindWindowW("Chrome_WidgetWin_1", "Claude")
        if h and user32.IsWindowVisible(h) and not user32.IsIconic(h) and titre:
            L, T, R, B = cadre_visible(h)
            try:
                racine = self.uia.ElementFromHandle(W.HWND(h))
                cond = self.uia.CreatePropertyConditionEx(self.U.UIA_NamePropertyId, titre[:20], 3)
                tab = racine.FindAll(self.U.TreeScope_Descendants, cond)
                ouverte, lignes = False, []
                for i in range(tab.Length):
                    z = tab.GetElement(i).CurrentBoundingRectangle
                    if z.right <= z.left:
                        continue
                    nom = tab.GetElement(i).CurrentName or ""
                    if z.right - z.left > (R - L) * 0.5:
                        ouverte = True                  # le contenu affiché porte le titre de la session
                    elif z.bottom - z.top < 80 and z.top > T + 40 and not nom.startswith("Plus d'options"):
                        # Pas le bouton « renommer » du haut de la fenêtre, ni les boutons « Plus d'options »
                        # (mesuré le 2 octobre : le titre d'une session apparaît à cinq endroits).
                        lignes.append((z.left, z.top, z.right, z.bottom))
                if ouverte:
                    cond_e = self.uia.CreatePropertyCondition(self.U.UIA_ControlTypePropertyId,
                                                              self.U.UIA_EditControlTypeId)
                    eds = racine.FindAll(self.U.TreeScope_Descendants, cond_e)
                    boites = []
                    for i in range(eds.Length):
                        z = eds.GetElement(i).CurrentBoundingRectangle
                        if z.right - z.left > (R - L) * 0.3:
                            boites.append((z.left, z.top, z.right, z.bottom))
                    if boites:
                        zone = max(boites, key=lambda z: z[1])       # la plus basse : la zone de saisie
                    q = self.trouver_questionnaire(racine, question, zone) if question else None
                    if q:
                        zone, questionnaire = q, True
                if zone is None and lignes:
                    zone = min(lignes, key=lambda z: z[0])           # la plus à gauche : la liste des sessions
            except Exception as e:
                log.warning("session %r dans Claude : %s", titre, e)
            if zone:
                point = (min(zone[0] + 60, (zone[0] + zone[2]) // 2), (zone[1] + zone[3]) // 2)
                ok, _cache = self.visible(point, h, False)
                if not ok:
                    bouton = self.bouton_barre(h)
                    point, zone = (bouton, None) if bouton else (point, zone)
        self.cache_elements[cle] = (time.time(), point, zone, questionnaire)
        return point, zone, questionnaire

    def trouver_questionnaire(self, racine, question, saisie):
        """Le questionnaire ouvert d'une question, dans l'app Claude : l'élément qui porte le texte de la question
        (le plus bas, au-dessus de la zone de saisie), jusqu'au bouton « Envoyer » (« Send »). Rend sa zone, ou None."""
        debut = " ".join(re.sub(r"[*`#]", "", question).split())[:28]
        if len(debut) < 6:
            return None
        cond = self.uia.CreatePropertyConditionEx(self.U.UIA_NamePropertyId, debut, 3)
        tab = racine.FindAll(self.U.TreeScope_Descendants, cond)
        haut_saisie = saisie[1] if saisie else 10 ** 6
        candidats = []
        for i in range(tab.Length):
            z = tab.GetElement(i).CurrentBoundingRectangle
            if z.right - z.left > 50 and z.bottom <= haut_saisie + 10:
                candidats.append((z.left, z.top, z.right, z.bottom))
        if not candidats:
            return None
        l, t, r, b = max(candidats, key=lambda z: z[1])
        cond_b = self.uia.CreatePropertyCondition(self.U.UIA_ControlTypePropertyId, self.U.UIA_ButtonControlTypeId)
        boutons = racine.FindAll(self.U.TreeScope_Descendants, cond_b)
        for i in range(boutons.Length):
            el = boutons.GetElement(i)
            if (el.CurrentName or "").strip().lower().startswith(("envoyer", "send", "submit")):
                z = el.CurrentBoundingRectangle
                if t < z.top < haut_saisie and z.top - t < 700:
                    r, b = max(r, z.right), max(b, z.bottom)
        return (l, t, r, b)

    def bouton_barre(self, hwnd):
        """Le bouton de la barre des tâches qui ramène cette fenêtre devant.

        La barre groupe les fenêtres par programme (« Explorateur de fichiers - 2 fenêtres en cours... ») :
        on prend le nom du programme à la fin du titre (« Mon projet : Explorateur de fichiers »,
        « Page - Google Chrome ») et on cherche le bouton qui commence par ce nom."""
        self.rect_bouton = None
        titre = titre_de(hwnd).replace("\xa0", " ")
        programme = re.split(r" [-:] ", titre)[-1].strip().casefold()
        if not programme:
            return None
        try:
            barre = self.uia.ElementFromHandle(W.HWND(user32.FindWindowW("Shell_TrayWnd", None)))
            cond = self.uia.CreatePropertyCondition(self.U.UIA_ControlTypePropertyId, self.U.UIA_ButtonControlTypeId)
            tab = barre.FindAll(self.U.TreeScope_Descendants, cond)
            for i in range(tab.Length):
                b = tab.GetElement(i)
                if (b.CurrentName or "").casefold().startswith(programme):
                    r = b.CurrentBoundingRectangle
                    self.rect_bouton = (r.left, r.top, r.right, r.bottom)
                    return ((r.left + r.right) // 2, (r.top + r.bottom) // 2)
        except Exception as e:
            log.warning("bouton de la barre des tâches : %s", e)
        return None

    # -- 3. où se pose le pigeon
    @staticmethod
    def point_sur_icone(rect):
        """Le pigeon se tient sur le haut de l'icône (ou au début de la ligne, en vue Détails)."""
        l, t, r, b = rect
        if (r - l) > 2.5 * (b - t):
            return l + 14, t + 4
        return (l + r) // 2, t + 6

    @staticmethod
    def centre_icone(rect):
        """L'endroit où cliquer : l'icône elle-même (le début de la ligne, en vue Détails)."""
        l, t, r, b = rect
        if (r - l) > 2.5 * (b - t):
            return l + 14, (t + b) // 2
        return (l + r) // 2, t + min(30, (b - t) // 2)

    def visible(self, point, racine_attendue, du_bureau):
        """Ce point est-il à l'écran ? Sinon, rend la fenêtre qui le cache."""
        h = user32.WindowFromPoint(W.POINT(int(point[0]), int(point[1])))
        racine = user32.GetAncestor(h, GA_ROOT) if h else None
        if not racine:
            return False, None
        if racine == racine_attendue or (du_bureau and nom_de_classe(racine) in ("Progman", "WorkerW")):
            return True, None
        return False, racine

    def perchoir(self, x, cache):
        """Sur le bord du haut de la fenêtre qui cache l'icône, sans sortir de l'écran."""
        l, t, r, b = cadre_visible(cache)
        x = min(max(x, l + 20), r - 20)
        e = ecran_de(self.ecrans, x, max(t, 0)) or ecran_de(self.ecrans, x, t + 30)
        if e:
            t = max(t, e["rect"][1] + 22)
        return x, t

    def situer_fichier(self, chemin_vrai, fenetres):
        """Où est l'icône d'un fichier : {mode, x, y (les pattes), centre (où cliquer), detail}."""
        chemin = os.path.normcase(chemin_vrai)
        fichier = os.path.basename(chemin_vrai)
        # a) un dossier ouvert qui contient le fichier (le plus précis gagne)
        for hwnd, dossier in sorted(fenetres, key=lambda f: -len(f[1])):
            dc = os.path.normcase(dossier)
            if chemin == dc or chemin.startswith(dc + os.sep):
                rel = os.path.relpath(chemin_vrai, dossier)
                l, t, r, b = cadre_visible(hwnd)
                if rel == ".":
                    return {"mode": "pose", "x": (l + r) // 2, "y": t + 24, "centre": ((l + r) // 2, t + 60),
                            "detail": tr("dans le dossier ouvert {x}", x=os.path.basename(dossier))}
                nom = rel.split(os.sep)[0]
                rect, hors = self.chercher(hwnd, nom, partout=True)
                if rect and not hors:
                    centre = self.centre_icone(rect)
                    ok, cache = self.visible(centre, hwnd, False)
                    x, y = self.point_sur_icone(rect)
                    if ok:
                        return {"mode": "pose", "x": x, "y": y, "centre": centre, "rect": rect, "detail": tr("{f} (sur {n})", f=fichier, n=nom)}
                    if cache:
                        x, y = self.perchoir(x, cache)
                        return {"mode": "perche", "x": x, "y": y, "centre": (x, y + 30), "rect": rect,
                                "reelle": centre, "detail": tr("{f} (caché, perché sur la fenêtre)", f=fichier)}
                # pas d'icône visible (défilée, autre onglet) : sur le haut de la fenêtre
                return {"mode": "perche", "x": (l + r) // 2, "y": t + 24, "centre": ((l + r) // 2, t + 60),
                        "detail": tr("{f} (dans {d}, icône hors vue)", f=fichier, d=os.path.basename(dossier))}
        # b) une icône du Bureau
        if chemin.startswith(BUREAU + os.sep):
            nom = os.path.relpath(chemin_vrai, str(Path.home() / "Desktop")).split(os.sep)[0]
            liste = self.liste_du_bureau()
            if liste:
                rect, hors = self.chercher(liste, nom, partout=False)
                if rect:
                    centre = self.centre_icone(rect)
                    ok, cache = self.visible(centre, user32.GetAncestor(liste, GA_ROOT), True)
                    x, y = self.point_sur_icone(rect)
                    if ok:
                        return {"mode": "pose", "x": x, "y": y, "centre": centre, "rect": rect, "detail": tr("{f} (sur {n})", f=fichier, n=nom)}
                    if cache:
                        x, y = self.perchoir(x, cache)
                        return {"mode": "perche", "x": x, "y": y, "centre": (x, y + 30), "rect": rect,
                                "reelle": centre, "detail": tr("{f} ({n} caché, perché sur la fenêtre)", f=fichier, n=nom)}
        # c) ailleurs (hors du Bureau, ou icône introuvable)
        return {"mode": "parc", "x": None, "y": None, "centre": None, "detail": tr("{f} (hors Bureau)", f=fichier)}

    def situer_cible(self, c, fenetres):
        """Un endroit demandé par montre.py : un fichier, un bouton dans une fenêtre (--element), un rectangle d'une
        page web (--page), ou un point de l'écran. Rend (point où pointer, précision pour la bulle, zone où un clic de
        l'utilisateur compte comme « fait », ou) ; (None, raison, None, ou) si on ne trouve pas.

        « ou » dit à l'utilisateur où est exactement la cible (la balise, son idée du 5 octobre 2026 à 22h57 : « c'est souvent
        à la bonne position de l'écran, mais il y a des fenêtres par-dessus ; quelques mots pour orienter : quelle
        couche, quelle app ») : {app, exe, lieu, element, etape1, obstacle, defiler, proches, ecran}. etape1 : la cible
        n'est pas encore cliquable, le point est une étape d'avant (le bouton de la barre des tâches, l'onglet)."""
        if not c:
            return None, "", None, {}
        if c.get("point"):
            return self.situer_point(c)
        if c.get("fichier"):
            return self.situer_icone(c, fenetres)
        if c.get("fenetre"):
            # Le panneau des pigeons : ses boutons sont dessinés par Tk, que l'automatisation de Windows ne voit pas ;
            # la volée publie leur place chaque seconde (essai d'AG, 3 octobre : « Réglages » introuvable).
            panneau = self.element_du_panneau(c["fenetre"], c.get("element"))
            if panneau:
                rect = panneau[0]
                return (((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2), "", rect,
                        {"app": "Pigeons", "element": tr("bouton « {e} »", e=c.get("element"))})
            return self.situer_dans_fenetre(c)
        return None, "", None, {}

    def ou_fenetre(self, hwnd):
        """Le début de « ou » pour une fenêtre : l'app et son exécutable."""
        app, exe = app_de(hwnd)
        return {"app": app, "exe": exe}

    def devant_dabord(self, hwnd, ou, point, zone, reduite=False):
        """La fenêtre de la cible est réduite, ou une autre la couvre : on montre d'abord son bouton dans la barre des
        tâches (étape 1), et la balise dit pourquoi (« Chrome est derrière », « sous l'Explorateur »)."""
        app = ou.get("app") or "?"
        ou["etape1"] = tr("« {a} » est réduite", a=app) if reduite else tr("« {a} » est derrière", a=app)
        bouton = self.bouton_barre(hwnd)
        if bouton:
            return bouton, tr("d'abord : clique ici pour ramener « {w} » devant", w=app), self.rect_bouton, ou
        return point, tr("la fenêtre « {w} » est derrière : ramène-la devant", w=app), zone, ou

    def situer_dans_fenetre(self, c):
        """--fenetre avec --element, --page ou rien (la barre de titre), et --onglet pour un navigateur."""
        titre, element, onglet = c["fenetre"], c.get("element"), c.get("onglet")
        seulement = None
        if onglet:
            o = self.trouver_onglet(titre, onglet)
            if not o:
                if not self.trouver_fenetres(titre) and not fenetres_reduites(titre):
                    return None, tr("la fenêtre « {w} » n'est pas ouverte", w=titre), None, {}
                return None, tr("je ne trouve pas l'onglet « {o} » dans « {w} »", o=onglet, w=titre), None, {}
            rect_o, choisi, seulement = o
            ou = {**self.ou_fenetre(seulement), "lieu": tr("onglet « {o} »", o=court(onglet, 30))}
            centre_o = ((rect_o[0] + rect_o[2]) // 2, (rect_o[1] + rect_o[3]) // 2)
            if user32.IsIconic(W.HWND(seulement)):
                return self.devant_dabord(seulement, ou, centre_o, rect_o, reduite=True)
            ok, cache = self.visible(centre_o, seulement, False)
            if not ok:
                if cache:
                    ou["obstacle"] = dict(zip(("app", "exe"), app_de(cache)))
                return self.devant_dabord(seulement, ou, centre_o, rect_o)
            if not choisi:
                # La page de la cible est dans un onglet caché : on montre l'onglet d'abord.
                ou["etape1"] = tr("ouvre l'onglet « {o} »", o=court(onglet, 30))
                ou["ecran"] = nom_ecran(self.ecrans, *centre_o)
                return centre_o, tr("d'abord : ouvre l'onglet « {o} »", o=onglet), rect_o, ou
        if c.get("page"):
            hwnd = seulement or next(iter(self.trouver_fenetres(titre)), None)
            vue = self.zone_de_page(hwnd) if hwnd else None
            rect = None
            if vue:
                x, y, lg, ht = c["page"]
                k = float(c.get("echelle") or 1.0)
                rect = (int(vue[0] + x * k), int(vue[1] + y * k), int(vue[0] + (x + lg) * k), int(vue[1] + (y + ht) * k))
            info = {"genre": "", "nom": c.get("element") or "",
                    "hors": bool(rect and vue and (rect[1] >= vue[3] or rect[3] <= vue[1]))}
        else:
            rect, hwnd = self.trouver_element(titre, element, seulement)
            info = self.infos_elements.get((titre, element, seulement)) or {}
        if not hwnd:
            reduites = fenetres_reduites(titre)
            if reduites:
                ou = self.ou_fenetre(reduites[0])
                return self.devant_dabord(reduites[0], ou, None, None, reduite=True)
            return None, tr("la fenêtre « {w} » n'est pas ouverte", w=titre), None, {}
        ou = {**self.ou_fenetre(hwnd), **({"lieu": tr("onglet « {o} »", o=court(onglet, 30))} if onglet else {})}
        if not ou.get("lieu"):
            t = titre_de(hwnd)
            debut = court(re.split(r" [-–] ", t)[0], 30)
            if re.search(r" - (Google Chrome|Microsoft.? Edge|Brave|Mozilla Firefox)", t):
                ou["lieu"] = tr("onglet « {o} »", o=debut)
            elif debut.casefold() != (ou.get("app") or "").casefold():
                ou["lieu"] = debut
        if not rect:
            if c.get("page"):
                return None, tr("je ne trouve pas la page dans « {w} »", w=titre), None, ou
            ou["proches"] = self.noms_proches(hwnd, element)
            raison = tr("je ne trouve pas « {e} » dans « {w} »", e=element, w=titre)
            if ou["proches"]:
                raison += tr(" ; les noms proches : {n}", n=", ".join(f"« {x} »" for x in ou["proches"]))
            elif not onglet and nom_de_classe(hwnd) == "Chrome_WidgetWin_1":
                raison += tr(" ; si c'est dans un autre onglet, donne --onglet")
            # La balise « introuvable » (démo du 6 octobre 2026, 08h29 : l'onglet ChatGPT montrait la page des forfaits,
            # sans « Nouveau chat », et la balise s'effaçait sans rien dire) : elle se pose en haut de la page de la
            # fenêtre et dit ce qui manque, avec les noms proches.
            if not user32.IsIconic(W.HWND(hwnd)):
                vue = self.zone_de_page(hwnd) or cadre_visible(hwnd)
                if vue:
                    ou["ancre"] = ((vue[0] + vue[2]) // 2, vue[1] + 70)
                    ou["introuvable"] = court(element or "", 30)
            return None, raison, None, ou
        nom = info.get("nom") or element or ""
        if nom:
            genre = info.get("genre") or ""
            ou["element"] = f"{tr(genre)} « {court(nom, 30)} »" if genre else f"« {court(nom, 30)} »"
        centre = ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
        zone = rect
        if not element and not c.get("page"):
            centre = ((rect[0] + rect[2]) // 2, rect[1] + 16)     # la barre de titre
            zone = None
        elif (rect[2] - rect[0]) > 2.5 * (rect[3] - rect[1]) and not c.get("page"):
            centre = (rect[0] + 40, centre[1])                     # une ligne de liste : vers le nom, à gauche
        if info.get("hors"):
            # Hors de la vue (il faut défiler) : on pointe le bord de la fenêtre de ce côté, et la balise le dit.
            l, t, r, b = self.zone_de_page(hwnd) or cadre_visible(hwnd)
            ou["defiler"] = "↓" if centre[1] >= b - 4 else ("↑" if centre[1] <= t + 4 else "")
            centre = (min(max(centre[0], l + 30), r - 30), min(max(centre[1], t + 30), b - 30))
            zone = None
        ok, cache = self.visible(centre, hwnd, False)
        ou["ecran"] = nom_ecran(self.ecrans, *centre)
        if ok:
            return centre, "", zone, ou
        if cache:
            ou["obstacle"] = dict(zip(("app", "exe"), app_de(cache)))
        # La fenêtre est derrière une autre : on montre d'abord son bouton dans la barre des tâches.
        return self.devant_dabord(hwnd, ou, centre, zone)

    def situer_point(self, c):
        """--point X Y : on pointe là. La balise dit quelle app est sous le point ; avec --dans « Chrome », si une autre
        fenêtre couvre le point, on ramène d'abord Chrome devant."""
        point = tuple(c["point"])
        h = user32.WindowFromPoint(W.POINT(int(point[0]), int(point[1])))
        racine = user32.GetAncestor(h, GA_ROOT) if h else None
        ou = {"ecran": nom_ecran(self.ecrans, *point)}
        if racine:
            ou.update(self.ou_fenetre(racine))
        dans = c.get("dans")
        if dans and racine:
            voulues = self.trouver_fenetres(dans)
            if racine not in voulues:
                if voulues:
                    ou_voulue = {**self.ou_fenetre(voulues[0]), "ecran": ou["ecran"],
                                 "obstacle": {"app": ou.get("app"), "exe": ou.get("exe")}}
                    return self.devant_dabord(voulues[0], ou_voulue, point, None)
                reduites = fenetres_reduites(dans)
                if reduites:
                    return self.devant_dabord(reduites[0], self.ou_fenetre(reduites[0]), point, None, reduite=True)
        return point, "", None, ou

    def situer_icone(self, c, fenetres):
        """--fichier : l'icône sur le Bureau ou dans un dossier ouvert de l'Explorateur."""
        s = self.situer_fichier(c["fichier"], fenetres)
        nom = os.path.basename(c["fichier"].rstrip("\\/"))
        dossier = os.path.basename(os.path.dirname(c["fichier"].rstrip("\\/")))
        rect = s.get("rect")
        ou = {"element": f"« {court(nom, 30)} »"}
        if rect:
            centre = ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
            ou["ecran"] = nom_ecran(self.ecrans, *centre)
            h = user32.WindowFromPoint(W.POINT(*centre))
            racine = user32.GetAncestor(h, GA_ROOT) if h else None
            if s["mode"] == "pose" and racine:
                if nom_de_classe(racine) in ("Progman", "WorkerW"):
                    ou.update({"app": tr("Bureau"),
                               "exe": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "explorer.exe")})
                else:
                    ou.update({**self.ou_fenetre(racine), "lieu": court(dossier, 30)})
            elif racine:
                ou["obstacle"] = dict(zip(("app", "exe"), app_de(racine)))
                ou["etape1"] = tr("« {f} » est caché", f=court(nom, 24))
        if s["mode"] == "pose":
            return s["centre"], "", rect, ou
        if s["mode"] == "perche":
            return (s["x"], s["y"] + 10), tr("c'est caché sous cette fenêtre"), None, ou
        return None, tr("je ne vois pas {f} à l'écran", f=nom), None, ou

    def element_du_panneau(self, fenetre, element):
        """Un bouton du panneau des pigeons (ou de sa fenêtre des réglages), d'après la place que la volée publie :
        rend (rect, hwnd) ou None."""
        boutons = getattr(self, "boutons_panneau", None)
        if not boutons or not element or "pigeons" not in (fenetre or "").lower():
            return None
        cherche = element.strip().lower()
        for texte, (rect, hwnd) in boutons.items():
            if cherche in texte:
                return rect, hwnd
        return None

    def placer(self, s, fenetres, maintenant, i_parc):
        """Décide le mode du pigeon et l'endroit où il va."""
        etat = {"ident": s.ident, "parent": s.parent, "titre": s.titre, "couleur": s.couleur,
                "rythme": s.rythme(maintenant), "x": None, "y": None, "parc": i_parc,
                "dernier_geste": s.dernier_geste, "bulle": "", "cible": None, "vers": None,
                "depuis": s.attend_depuis or 0,
                # Pour le panneau (3 octobre) : le contexte, le début du tour, le fichier et son dossier de projet.
                "contexte": s.contexte, "tour_depuis": s.dernier_message_danny, "chemin": s.chemin,
                "projet": projet_de(s.chemin)}
        # Montrer un endroit à l'utilisateur passe avant tout le reste.
        if s.demande:
            a, pa, za, oa = self.situer_cible(s.demande.get("cible"), fenetres)
            b, pb, zb, ob = self.situer_cible(s.demande.get("vers"), fenetres)
            c2, _p2, z2, o2 = self.situer_cible(s.demande.get("puis"), fenetres)     # l'étape 2, s'il y en a une
            texte = s.demande.get("texte") or tr("Regarde ici")
            precision = " · ".join(p for p in (pa, pb) if p)
            importance = s.demande.get("importance") if s.demande.get("importance") in IMPORTANCES else "haute"
            etat["demande"] = {k: s.demande.get(k) for k in ("cible", "vers", "puis")}     # pour l'aide active
            return {**etat, "mode": "montre", "importance": importance, "cible": a, "vers": b, "zone": za, "zone_vers": zb,
                    "puis": c2, "zone_puis": z2, "texte_puis": s.demande.get("texte_puis") or "",
                    "trouvee": a is not None, "precision": precision, "ou": oa, "ou_vers": ob, "ou_puis": o2,
                    "ancre": (oa or {}).get("ancre") if a is None else None,
                    "depuis": s.demande.get("heure", 0),
                    "bulle": texte + (f"\n({precision})" if precision else ""), "libelle": tr("te montre : ") + court(texte, 60)}
        # Une permission à donner (le crochet Notification) : la session est arrêtée tant que l'utilisateur n'a rien fait.
        sig = s.signal
        if not s.parent and sig and sig.get("type") in BLOQUANTS and s.derniere_ligne <= sig.get("heure", 0):
            question = s.texte_attente if (s.attend_depuis and s.importance == "normale") else None
            point, zone, questionnaire = self.situer_session(s.titre, question)
            message = court(sig.get("message"), 120)
            bulle = (tr("Permission à donner : ") + message) if sig["type"] == "permission_prompt" else (message or tr("Claude a besoin de toi"))
            mode = "appel" if maintenant - sig["heure"] < APPEL_MAX_S else "attend"
            return {**etat, "mode": mode, "importance": "bloquee", "depuis": sig["heure"], "bulle": bulle,
                    "reponse": point, "zone_reponse": zone, "questionnaire": questionnaire,
                    "libelle": tr("bloquée : attend ta permission")}
        fichier = os.path.basename(s.chemin) if s.chemin else ""
        if not s.parent and s.attend_depuis:
            bulle = court(s.texte_attente) or tr("Je t'attends")
            question = s.texte_attente if s.importance == "normale" else None
            point, zone, questionnaire = self.situer_session(s.titre, question)
            etat = {**etat, "reponse": point, "zone_reponse": zone, "importance": s.importance, "sorties": s.sorties,
                    "questionnaire": questionnaire}
            if maintenant - s.attend_depuis < APPEL_MAX_S:
                return {**etat, "mode": "appel", "bulle": bulle, "libelle": tr("t'attend (vient te chercher)")}
            return {**etat, "mode": "attend", "bulle": bulle, "libelle": tr("t'attend")}
        if maintenant - s.dernier_geste > REPOS_S:
            return {**etat, "mode": "repos", "libelle": tr("au repos")}
        if not s.chemin:
            return {**etat, "mode": "parc", "libelle": tr("{o} (pas de fichier)", o=s.outil)}
        chemin = s.chemin
        if (os.path.isdir(chemin) and s.dernier_fichier and maintenant - s.dernier_fichier_t < 600
                and os.path.normcase(s.dernier_fichier).startswith(os.path.normcase(chemin) + os.sep)):
            # Une commande dans un dossier ne dit pas sur quoi la session travaille : le dernier fichier qu'elle a
            # touché DANS ce dossier le dit mieux (sinon le pigeon restait en haut de la fenêtre).
            chemin = s.dernier_fichier
        lieu = self.situer_fichier(chemin, fenetres)
        return {**etat, "mode": lieu["mode"], "x": lieu["x"], "y": lieu["y"], "libelle": f"{s.outil} · {lieu['detail']}",
                "travail": lieu.get("reelle") or lieu.get("centre"), "zone_travail": lieu.get("rect"), "chemin": chemin}

    def trouver_parc(self):
        """Où ranger les pigeons qui attendent : DANS la barre des tâches, dans son plus grand espace vide,
        sur l'écran où est la fenêtre de Claude (c'est là que l'utilisateur répond aux sessions).

        l'utilisateur, 2 octobre, 10h39 : « sur la barre de tâche en bas et pas dessus, les pigeons cachent des
        infos et des boutons » (posés sur le haut de la barre, ils couvraient le bas de la fenêtre Claude).
        Mesuré ce jour-là : les barres sont alignées à gauche ; l'espace vide va de la dernière icône à la
        météo (environ 670 px sur l'écran de gauche)."""
        principal = next((e for e in self.ecrans if e["principal"]), self.ecrans[0])
        ecran = principal
        h = user32.FindWindowW("Chrome_WidgetWin_1", "Claude")
        if h and user32.IsWindowVisible(h) and not user32.IsIconic(h):
            l, t, r, b = cadre_visible(h)
            ecran = ecran_de(self.ecrans, (l + r) // 2, (t + b) // 2) or principal
        barre = None
        for classe in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
            w = None
            while True:
                w = user32.FindWindowExW(None, w, classe, None)
                if not w:
                    break
                l, t, r, b = cadre_visible(w)
                if ecran_de(self.ecrans, (l + r) // 2, (t + b) // 2) is ecran:
                    barre = w
        l, t, r, b = ecran["travail"]
        repli = {"x0": r - 420, "x1": r - 120, "pattes": b, "ecran": ecran}     # au-dessus de la barre, faute de mieux
        if not barre:
            return repli
        L, T, R, B = cadre_visible(barre)
        occupe = []
        try:
            tab = self.uia.ElementFromHandle(W.HWND(barre)).FindAll(self.U.TreeScope_Descendants,
                                                                   self.uia.CreateTrueCondition())
            for i in range(tab.Length):
                z = tab.GetElement(i).CurrentBoundingRectangle
                # Les boîtes qui couvrent la moitié de la barre sont des conteneurs, pas des boutons.
                if 0 < z.right - z.left < (R - L) * 0.5 and z.bottom > T and z.top < B:
                    occupe.append((max(z.left, L), min(z.right, R)))
        except Exception as e:
            log.warning("lecture de la barre des tâches : %s", e)
            return repli
        occupe.sort()
        vides, x = [], L
        for a, b2 in occupe:
            if a > x:
                vides.append((x, a))
            x = max(x, b2)
        if R > x:
            vides.append((x, R))
        if not vides:
            return repli
        x0, x1 = max(vides, key=lambda v: v[1] - v[0])
        if x1 - x0 < 60:
            return repli
        return {"x0": x0 + 24, "x1": x1 - 24, "pattes": T + (B - T) // 2 + 9, "ecran": ecran}

    def tour(self):
        maintenant = time.time()
        if self.tours % 3 == 0:
            self.parc_info = self.trouver_parc()
        self.tours += 1
        self.trouver_journaux(maintenant)
        for cle, s in list(self.sessions.items()):
            try:
                s.lire_la_suite()
                vieux = maintenant - s.fichier.stat().st_mtime
            except OSError:
                del self.sessions[cle]
                continue
            limite = SOUS_AGENT_VIVANT_S if s.parent else SESSION_VIVANTE_S
            if vieux > limite or s.fini:
                del self.sessions[cle]          # le pigeon s'envole pour de bon
        self.lire_demandes(maintenant)
        self.suivre_les_autres_ia(maintenant)
        self.lire_annonces(maintenant)
        self.lire_signaux(maintenant)
        self.lire_fiches_app(maintenant)
        self.lire_fermetures(maintenant)
        for s in self.sessions.values():
            if s.parent and s.parent in self.sessions:
                s.couleur = self.sessions[s.parent].couleur
        fenetres = self.fenetres_explorateur()
        etats = {}
        # Une session fermée n'a plus de pigeon, de carte ni de ligne ; ses pigeonneaux partent avec elle.
        meres = sorted((s for s in self.sessions.values() if not s.parent and not s.est_fermee()), key=lambda s: s.rang)
        # Ses livrables, eux, restent (l'utilisateur, 3 octobre, 18h29 : « j'aurai aimé cliqué sur le bouton pour copier le prompt ») :
        # une session qui se termine elle-même (montre.py --termine) le fait juste avant sa dernière réponse, dont les
        # liens, les fichiers et les blocs arrivent après. Ils restent dans le panneau 24 h, ou jusqu'à « Oublier ».
        # Une session que l'utilisateur a terminée lui-même (le bouton) ne laisse rien : il a choisi qu'elle s'en aille.
        self.livrables = [{"ident": s.ident, "titre": s.titre, "couleur": s.couleur, "sorties": list(s.sorties), "fermee": s.fermee}
                          for s in sorted(self.sessions.values(), key=lambda s: -(s.fermee or 0))
                          if not s.parent and s.fermee and s.fermee_par == "session" and s.est_fermee() and not s.archivee
                          and s.sorties and not s.livrables_vus and maintenant - s.fermee < LIVRABLES_S][:4]
        for i, s in enumerate(meres):
            etats[s.ident] = self.placer(s, fenetres, maintenant, i)
        for s in self.sessions.values():
            if s.parent and s.parent in etats and s.couleur:
                etats[s.ident] = self.placer(s, fenetres, maintenant, etats[s.parent]["parc"])
        # Deux sessions qui travaillent dans le même dossier de projet : un avertissement discret dans
        # le panneau, rien à l'écran (le risque de conflits ; la règle de l'utilisateur : jamais deux sessions dans un dossier).
        actives = [etats[s.ident] for s in meres if s.ident in etats and etats[s.ident].get("projet")
                   and maintenant - s.dernier_geste < 600]
        for e in actives:
            e["meme_dossier"] = [f["titre"] for f in actives if f is not e and f["projet"] == e["projet"]]
        self.calculer_conflits(maintenant)
        if not self.actif:
            return                              # remplacé pendant ce tour : l'autre guetteur écrit, pas lui
        self.ecrire_activite(maintenant, etats)
        self.ecarter(etats)
        with self.verrou:
            self.partage.clear()
            self.partage.update(etats)

    @staticmethod
    def ecarter(etats):
        """Deux pigeons sur la même icône se mettent côte à côte."""
        vus = {}
        for e in etats.values():
            if e["x"] is None:
                continue
            k = (round(e["x"] / 12), round(e["y"] / 12))
            n = vus.get(k, 0)
            vus[k] = n + 1
            e["x"] += ((n + 1) // 2) * 16 * (1 if n % 2 else -1)   # 0, +16, -16, +32, -32...


# ----------------------------------------------------------- l'affichage

def rendre_traversable(fen, clics_traversent=True):
    """Toujours devant, jamais active. Les clics passent au travers, sauf pour le pigeon qu'on peut cliquer
    (et même là, ses pixels transparents laissent passer les clics vers l'icône dessous)."""
    fen.update_idletasks()
    hwnd = user32.GetParent(fen.winfo_id())
    ex = user32.GetWindowLongW(W.HWND(hwnd), GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if clics_traversent:
        ex |= WS_EX_TRANSPARENT
    user32.SetWindowLongW(W.HWND(hwnd), GWL_EXSTYLE, ex)
    return hwnd


def deplacer(hwnd, x, y):
    user32.SetWindowPos(W.HWND(hwnd), None, int(x), int(y), 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


class Vignette:
    """Une petite fenêtre transparente qu'on déplace : la base du pigeon et des flèches.

    Pourquoi de petites fenêtres : une toile qui couvre l'écran se redessine en entier dès que deux
    pigeons sont loin l'un de l'autre (mesuré : 13 % d'un cœur) ; déplacer une petite fenêtre ne coûte presque rien."""

    def __init__(self, racine, lg, ht, clics_traversent=True):
        import tkinter as tk
        self.lg, self.ht = lg, ht
        self.fen = tk.Toplevel(racine)
        self.fen.overrideredirect(True)
        self.fen.geometry(f"{lg}x{ht}+-3000+-3000")
        self.fen.configure(bg=CLE)
        self.fen.attributes("-topmost", True)
        self.fen.attributes("-transparentcolor", CLE)
        self.toile = tk.Canvas(self.fen, width=lg, height=ht, bg=CLE, highlightthickness=0, bd=0)
        self.toile.pack()
        self.hwnd = rendre_traversable(self.fen, clics_traversent)
        self.xy = None
        self.dessin = None

    def placer_coin(self, x, y):
        if (int(x), int(y)) != self.xy:
            deplacer(self.hwnd, x, y)
            self.xy = (int(x), int(y))

    def contient(self, x, y):
        return self.xy is not None and self.xy[0] <= x < self.xy[0] + self.lg and self.xy[1] <= y < self.xy[1] + self.ht

    def detruire(self):
        self.fen.destroy()


class Oiseau(Vignette):
    """Un pigeon. Le point (x, y) qu'on lui donne est l'endroit où il pose les pattes. On peut le cliquer."""

    def __init__(self, racine, sous_agent, au_clic, taille=8, au_clic_droit=None):
        """taille : le rayon du corps (8 px par défaut, réglable) ; un pigeonneau fait 60 % de son parent.
        au_clic_droit : terminer la session (2 octobre, après-midi), pas pour un pigeonneau."""
        self.r = max(4, round(taille * 0.6)) if sous_agent else taille
        self.taille = taille
        self.T = max(44, 4 * self.r + 14)        # la place de l'anneau qui respire autour du corps
        self.PATTES = self.T - 6
        super().__init__(racine, self.T, self.T, clics_traversent=False)
        self.toile.configure(cursor="hand2")
        self.toile.bind("<Button-1>", lambda _e: au_clic())
        if au_clic_droit:
            self.toile.bind("<Button-3>", lambda _e: au_clic_droit())

    def placer(self, x, y):
        self.placer_coin(int(x) - self.T // 2, int(y) - self.PATTES)

    def dessiner(self, couleur, bec, anneau, pause=False, couleur_anneau=None):
        """Redessine seulement si quelque chose a changé (la couleur, le coup de bec, l'anneau, la pause).
        couleur : celle de la tâche (le corps) ; couleur_anneau : celle du guide (tâche ou importance)."""
        cle = (couleur, round(bec), None if anneau is None else round(anneau), pause, couleur_anneau)
        if cle == self.dessin:
            return
        self.dessin = cle
        t, r = self.toile, self.r
        t.delete("all")
        sx, haut = self.T // 2, self.PATTES - 2 * r + bec
        if anneau is not None:
            # Un anneau qui respire lentement : doux, jamais un clignotement.
            t.create_oval(sx - anneau, haut + r - anneau, sx + anneau, haut + r + anneau,
                          outline=couleur_anneau or couleur, width=2, dash=(3, 3) if pause else None)
        t.create_oval(sx - r, haut, sx + r, haut + 2 * r, fill=couleur, outline="#141414", width=2)
        t.create_oval(sx + r * 0.2, haut + r * 0.45, sx + r * 0.2 + 3, haut + r * 0.45 + 3, fill="white", outline="")
        t.create_polygon(sx + r - 1, haut + r * 0.7, sx + r + 5, haut + r * 0.95, sx + r - 1, haut + r * 1.2,
                         fill="#f2a516", outline="")


class Fleche(Vignette):
    """La flèche qui pointe, en sautillant, l'endroit exact où cliquer ; ou l'anneau qui marque où déposer."""

    def __init__(self, racine, couleur, anneau=False):
        super().__init__(racine, 40, 52)
        t = self.toile
        if anneau:
            t.create_oval(4, 4, 36, 36, outline="#141414", width=5)
            t.create_oval(4, 4, 36, 36, outline=couleur, width=3)
            self.pointe = (20, 20)
        else:
            t.create_polygon(15, 2, 25, 2, 25, 26, 35, 26, 20, 46, 5, 26, 15, 26,
                             fill=couleur, outline="#141414", width=2)
            self.pointe = (20, 47)

    def pointer(self, x, y, saut):
        self.placer_coin(int(x) - self.pointe[0], int(y) - self.pointe[1] - saut)


class Guide(Vignette):
    """La petite flèche près de la souris qui indique la direction de l'endroit montré, quand il est loin."""

    def __init__(self, racine):
        super().__init__(racine, 44, 44)

    def orienter(self, cx, cy, angle, couleur, creuse=True):
        cle = (round(math.degrees(angle) / 4), couleur, creuse)
        if cle != self.dessin:
            self.dessin = cle
            forme = [(-14, -4), (4, -4), (4, -10), (17, 0), (4, 10), (4, 4), (-14, 4)]
            ca, sa = math.cos(angle), math.sin(angle)
            pts = []
            for px, py in forme:
                pts += [22 + px * ca - py * sa, 22 + px * sa + py * ca]
            self.toile.delete("all")
            if creuse:
                self.toile.create_polygon(*pts, fill="", outline=couleur, width=2)
            else:
                self.toile.create_polygon(*pts, fill=couleur, outline="#141414", width=2)
        # Du côté où elle pointe, à 40 px de la souris (comme la petite flèche).
        self.placer_coin(cx + 40 * math.cos(angle) - 22, cy + 40 * math.sin(angle) - 22)


class PetitGuide(Vignette):
    """La petite flèche discrète près de la souris qui indique où répondre à la session qui t'attend
    (l'utilisateur, 10h43 : « petite flèche cute, discrète »). Une fléchette de 26 px, un peu transparente,
    qui avance et recule doucement vers où aller."""

    def __init__(self, racine, taille=23):
        """taille : la longueur de la fléchette en pixels (23 par défaut, l'utilisateur : « un peu plus grosse » ;
        réglable de 14 à 44 dans les réglages). La fenêtre fait une fois et demie la fléchette, pour qu'elle tourne."""
        self.taille = taille
        self.C = round(taille * 1.55)
        super().__init__(racine, self.C, self.C)
        self.fen.attributes("-alpha", 0.85)

    def orienter(self, cx, cy, angle, couleur, maintenant, rayon=32, creuse=True):
        cle = (round(math.degrees(angle) / 6), couleur, creuse)
        base = rayon
        if cle != self.dessin:
            self.dessin = cle
            k = self.taille / 23
            forme = [(-10 * k, -8 * k), (13 * k, 0), (-10 * k, 8 * k), (-4 * k, 0)]   # une fléchette, l'arrière creusé
            ca, sa = math.cos(angle), math.sin(angle)
            m = self.C / 2
            pts = []
            for px, py in forme:
                pts += [m + px * ca - py * sa, m + px * sa + py * ca]
            self.toile.delete("all")
            if creuse:      # juste le contour (l'utilisateur, 11h28 : « vides à l'intérieur »)
                self.toile.create_polygon(*pts, fill="", outline=couleur, width=2)
            else:
                self.toile.create_polygon(*pts, fill=couleur, outline="#141414", width=1.5)
        # Du côté où elle pointe (l'utilisateur, 10h46) : à 32 px de la souris (plus, si une autre flèche est déjà là),
        # dans la direction du but.
        rayon = base + 2.5 * math.sin(maintenant * 3.0)
        m = self.C / 2
        self.placer_coin(cx + rayon * math.cos(angle) - m, cy + rayon * math.sin(angle) - m)

    def cacher(self):
        self.placer_coin(-3000, -3000)


class Cadre(Vignette):
    """L'encadré léger autour de l'élément à cliquer ou à déplacer (l'utilisateur, 10h36) : un pointillé fin de la
    couleur du pigeon, l'intérieur reste transparent et les clics passent au travers."""

    def __init__(self, racine, couleur):
        super().__init__(racine, 10, 10)
        self.couleur = couleur
        self.rect = None

    def entourer(self, zone, marge=0, epaisseur=1, style="pointilles", numero=None, arrondi=6, rond=False):
        """Entoure une zone en épousant sa forme (l'utilisateur, 12h39 : « l'encadré en forme épousée de la cible ; je ne veux
        pas que ça cache le contenu ») :
        - marge : la taille de l'encadré autour de la zone, en pixels (0 : au ras de son bord, sur sa bordure, là où il
          n'y a pas de contenu ; négative : à l'intérieur ; positive : plus large) ;
        - arrondi : le rayon des coins, pour épouser les boutons et les lignes arrondies ;
        - rond : un cercle (pour une cible qui n'est qu'un point) ;
        - epaisseur et style : le trait (un pointillé d'un pixel par défaut, l'utilisateur, 10h53) ; numero : l'étape (1, 2)."""
        l, t, r, b = (int(v) for v in zone)
        e = max(1, int(epaisseur))
        L, T, R, B = l - marge - e, t - marge - e, r + marge + e, b + marge + e     # la place du trait comprise
        cle = ((L, T, R, B), epaisseur, style, numero, arrondi, rond)
        if cle == self.rect:
            return
        lg, ht = max(12, R - L), max(12, B - T)
        self.fen.geometry(f"{lg}x{ht}+{L}+{T}")
        self.toile.config(width=lg, height=ht)
        self.toile.delete("all")
        d = e / 2
        x0, y0, x1, y1 = d, d, lg - d - 1, ht - d - 1
        chemin = contour_arrondi(x0, y0, x1, y1, arrondi, rond)
        if style == "plein":
            self.toile.create_line(*[v for p in chemin for v in p], fill=self.couleur, width=e)
        else:
            # Les tirets le long du contour, à la main : sous Windows, Tk ne fait de vrais pointillés qu'en trait d'un pixel.
            tiret = vide = 3 + e
            dans_un_tiret, reste = True, tiret
            for (ax, ay), (bx, by) in zip(chemin, chemin[1:]):
                long = math.hypot(bx - ax, by - ay)
                if long <= 0:
                    continue
                ux, uy = (bx - ax) / long, (by - ay) / long
                s = 0.0
                while s < long:
                    pas = min(reste, long - s)
                    if dans_un_tiret:
                        self.toile.create_line(ax + ux * s, ay + uy * s, ax + ux * (s + pas), ay + uy * (s + pas),
                                               fill=self.couleur, width=e)
                    s += pas
                    reste -= pas
                    if reste <= 0:
                        dans_un_tiret = not dans_un_tiret
                        reste = tiret if dans_un_tiret else vide
        if numero:
            # Le numéro de l'étape, dans une pastille au coin du haut à gauche.
            self.toile.create_oval(1, 1, 15, 15, fill=self.couleur, outline="")
            self.toile.create_text(8, 8, text=str(numero), fill="#141414", font=("Segoe UI", 7, "bold"))
        self.rect, self.xy, self.lg, self.ht = cle, (L, T), lg, ht


def contour_arrondi(x0, y0, x1, y1, rayon, rond=False):
    """Les points d'un contour fermé : un rectangle aux coins arrondis (rayon en pixels), ou une ellipse (rond)."""
    if rond:
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        return [(cx + rx * math.cos(2 * math.pi * k / 48), cy + ry * math.sin(2 * math.pi * k / 48)) for k in range(49)]
    r = max(0.0, min(rayon, (x1 - x0) / 2, (y1 - y0) / 2))
    if r < 1:
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    points = []
    for (cx, cy, debut) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(7):                      # un quart de cercle en 6 morceaux par coin
            a = math.radians(debut + 15 * k)
            points.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    points.append(points[0])
    return points


gdi32 = ctypes.windll.gdi32
user32.GetDC.restype = W.HDC
user32.GetDC.argtypes = [W.HWND]
user32.ReleaseDC.argtypes = [W.HWND, W.HDC]
gdi32.CreateCompatibleDC.restype = W.HDC
gdi32.CreateCompatibleDC.argtypes = [W.HDC]
gdi32.CreateDIBSection.restype = W.HBITMAP
gdi32.CreateDIBSection.argtypes = [W.HDC, ctypes.c_void_p, W.UINT, ctypes.POINTER(ctypes.c_void_p), W.HANDLE, W.DWORD]
gdi32.SelectObject.restype = W.HGDIOBJ
gdi32.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
gdi32.DeleteObject.argtypes = [W.HGDIOBJ]
gdi32.DeleteDC.argtypes = [W.HDC]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_byte)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD),
                ("biBitCount", W.WORD), ("biCompression", W.DWORD), ("biSizeImage", W.DWORD),
                ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD),
                ("biClrImportant", W.DWORD)]


user32.UpdateLayeredWindow.argtypes = [W.HWND, W.HDC, ctypes.POINTER(W.POINT), ctypes.POINTER(W.SIZE), W.HDC,
                                       ctypes.POINTER(W.POINT), W.COLORREF, ctypes.POINTER(_BLENDFUNCTION), W.DWORD]


def couche_alpha(hwnd, image, x, y, opacite=255):
    """Envoie une image RGBA (couleurs déjà multipliées par l'alpha) à une fenêtre en couches, en (x, y) :
    chaque pixel garde sa propre transparence (UpdateLayeredWindow, ULW_ALPHA). opacite (0 à 255) : une transparence
    de plus pour toute l'image (le fondu de la balise, sans la redessiner)."""
    lg, ht = image.size
    ecran_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(ecran_dc)
    entete = _BITMAPINFOHEADER()
    entete.biSize, entete.biWidth, entete.biHeight = ctypes.sizeof(entete), lg, -ht   # de haut en bas
    entete.biPlanes, entete.biBitCount = 1, 32
    bits = ctypes.c_void_p()
    image_bmp = gdi32.CreateDIBSection(ecran_dc, ctypes.byref(entete), 0, ctypes.byref(bits), None, 0)
    try:
        donnees = image.tobytes("raw", "BGRA")
        ctypes.memmove(bits, donnees, len(donnees))
        ancien = gdi32.SelectObject(mem_dc, image_bmp)
        melange = _BLENDFUNCTION(0, 0, max(0, min(255, int(opacite))), 1)   # AC_SRC_OVER, alpha par pixel
        user32.UpdateLayeredWindow(W.HWND(hwnd), ecran_dc, ctypes.byref(W.POINT(x, y)), ctypes.byref(W.SIZE(lg, ht)),
                                   mem_dc, ctypes.byref(W.POINT(0, 0)), 0, ctypes.byref(melange), 2)
        gdi32.SelectObject(mem_dc, ancien)
    finally:
        gdi32.DeleteObject(image_bmp)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, ecran_dc)


class Voile:
    """La toile des lignes pointillées du guidage (réglage « lignes », l'utilisateur, 11h28), une par écran.

    Le fondu est une vraie transparence (l'utilisateur, 12h28 : « fondu en opacité bien sûr, de 0 à 100, et distance de
    fondu ») : une fenêtre en couches de Windows reçoit une image où chaque point a sa propre opacité
    (UpdateLayeredWindow ; les fenêtres à couleur clé des pigeons, elles, n'ont qu'une transparence d'ensemble).
    Pour rester léger, la fenêtre ne couvre que la boîte des lignes sur cet écran, et ne se redessine que si
    quelque chose a bougé (15 fois par seconde au plus, voir tracer_lignes)."""

    def __init__(self, racine, ecran):
        import tkinter as tk
        self.ecran = ecran["rect"]
        self.fen = tk.Toplevel(racine)
        self.fen.overrideredirect(True)
        self.fen.geometry("1x1+-3000+-3000")
        self.fen.attributes("-topmost", True)
        self.fen.update_idletasks()
        self.hwnd = user32.GetParent(self.fen.winfo_id())
        # Pas de -alpha ni de -transparentcolor ici : ils passent par SetLayeredWindowAttributes, qui empêche
        # UpdateLayeredWindow de fonctionner.
        ex = user32.GetWindowLongW(W.HWND(self.hwnd), GWL_EXSTYLE)
        user32.SetWindowLongW(W.HWND(self.hwnd), GWL_EXSTYLE,
                              ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        self.vide = True

    def contient(self, x, y):
        l, t, r, b = self.ecran
        return l <= x < r and t <= y < b

    def dessiner(self, morceaux, style="points", epaisseur=4, depart=90, arrivee=90, debut=0, fin=100):
        """morceaux : [(x, y, ux, uy, couleur, f, k)] en coordonnées de l'écran entier : le point, la direction de la
        ligne, sa place sur la ligne (f : 0 près de la souris, 1 près du but) et un facteur de taille (k : 0,7 pour la
        suite du trajet). opacite : celle de la ligne entière ; fondu : vers le but (« cible ») ou vers la souris ;
        portee : sur quelle part de la ligne se fait le fondu ; fondu_min : l'opacité au bout du fondu (0 : invisible)."""
        if not morceaux:
            if not self.vide:
                user32.SetWindowPos(W.HWND(self.hwnd), None, -3000, -3000, 1, 1, SWP_NOZORDER | SWP_NOACTIVATE)
                self.vide = True
            return
        from PIL import Image, ImageDraw
        marge = int(epaisseur * 3) + 14                  # la place d'une pointe de flèche
        l = max(self.ecran[0], int(min(m[0] for m in morceaux)) - marge)
        t = max(self.ecran[1], int(min(m[1] for m in morceaux)) - marge)
        r = min(self.ecran[2], int(max(m[0] for m in morceaux)) + marge)
        b = min(self.ecran[3], int(max(m[1] for m in morceaux)) + marge)
        if r <= l or b <= t:
            return
        image = Image.new("RGBA", (r - l, b - t), (0, 0, 0, 0))
        dessin = ImageDraw.Draw(image)
        o_dep, o_arr = max(0.0, min(1.0, depart / 100)), max(0.0, min(1.0, arrivee / 100))
        p_deb, p_fin = sorted((max(0.0, min(1.0, debut / 100)), max(0.0, min(1.0, fin / 100))))
        for x, y, ux, uy, couleur, f, *reste in morceaux:
            # L'opacité voulue à cette place du trajet : celle du départ avant le début du fondu, celle de l'arrivée
            # après sa fin, et entre les deux une courbe douce (smoothstep), sans cassure visible.
            if f <= p_deb:
                o = o_dep
            elif f >= p_fin:
                o = o_arr
            else:
                u = (f - p_deb) / max(1e-6, p_fin - p_deb)
                o = o_dep + (o_arr - o_dep) * u * u * (3 - 2 * u)
            # « À l'œil » : un petit alpha se voit encore bien sur un fond sombre ; la puissance 1,6 fait qu'à 10 %
            # demandés il ne reste que 2,5 % d'alpha, et à 0 % plus rien.
            a = int(255 * o ** 1.6)
            if a <= 0:
                continue
            rr, gg, bb = int(couleur[1:3], 16), int(couleur[3:5], 16), int(couleur[5:7], 16)
            teinte = (rr * a // 255, gg * a // 255, bb * a // 255, a)     # couleur multipliée par l'alpha
            taille = epaisseur * (reste[0] if reste else 1)
            sx, sy = x - l, y - t
            if len(reste) > 1 and reste[1] == "pointe":
                # La pointe du lien entre deux cibles : un triangle dans le sens de la ligne.
                g = max(5.0, taille * 2.2)
                dessin.polygon([(sx + ux * g, sy + uy * g),
                                (sx - ux * g * 0.6 - uy * g * 0.8, sy - uy * g * 0.6 + ux * g * 0.8),
                                (sx - ux * g * 0.6 + uy * g * 0.8, sy - uy * g * 0.6 - ux * g * 0.8)], fill=teinte)
                continue
            if style == "tirets":
                d = taille * 1.6
                dessin.line((sx - ux * d, sy - uy * d, sx + ux * d, sy + uy * d), fill=teinte, width=max(1, int(taille * 0.6)))
            else:
                rayon = taille / 2
                dessin.ellipse((sx - rayon, sy - rayon, sx + rayon, sy + rayon), fill=teinte)
        try:
            couche_alpha(self.hwnd, image, l, t)
            self.vide = False
        except Exception as e:
            log.warning("lignes : %s", e)

    def detruire(self):
        self.fen.destroy()


def chemin(x0, y0, x1, y1, forme="droite", courbure=35):
    """Le trajet d'une ligne de guidage, en fonction de t (0 à la souris, 1 au but). l'utilisateur, 2 octobre : « des
    lignes différentes, courbes, sinueuses ». Les formes :
    - droite ;
    - arc : une courbe qui monte, comme un vol ;
    - sinueuse : des vagues, une tous les 240 px environ, qui s'éteignent à la souris et au but ;
    - vol : un arc et de petites vagues.
    courbure : de 0 (presque droite) à 100."""
    dx, dy = x1 - x0, y1 - y0
    longueur = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / longueur, dx / longueur           # la perpendiculaire à la ligne droite
    if ny > 0 or (ny == 0 and nx < 0):
        nx, ny = -nx, -ny                            # tournée vers le haut de l'écran : l'arc monte
    k = max(0, min(100, courbure)) / 100
    hauteur = longueur * 0.30 * k                    # la hauteur de l'arc, au milieu du trajet
    amplitude = min(longueur * 0.08, 6 + 30 * k)     # la hauteur des vagues
    if forme == "vol":
        amplitude *= 0.5
    vagues = max(1.0, longueur / 240)

    def point(t):
        ecart = 0.0
        if forme in ("arc", "vol"):
            ecart += 4 * hauteur * t * (1 - t)       # une parabole : 0 aux deux bouts, la hauteur au milieu
        if forme in ("sinueuse", "vol"):
            ecart += amplitude * math.sin(2 * math.pi * vagues * t) * math.sin(math.pi * t)
        return x0 + dx * t + nx * ecart, y0 + dy * t + ny * ecart
    return point


def points_de_ligne(x1, y1, x2, y2, depart=26, fin=6, pas=11, forme="droite", courbure=35, decalage=0.0):
    """Les points d'un pointillé de (x1, y1) à (x2, y2), tous les « pas » pixels mesurés SUR le trajet (droit ou
    courbe), en laissant un peu d'air autour de la souris et du but. decalage (de 0 à 1 pas) fait avancer les
    points (l'animation « les points avancent »). Chaque point : (x, y, direction x, direction y, place 0 à 1)."""
    pas = max(4, int(pas))
    droite = math.hypot(x2 - x1, y2 - y1)
    if forme == "droite" or droite < 40:
        p = [(x1, y1), (x2, y2)]
    else:
        f = chemin(x1, y1, x2, y2, forme, courbure)
        n = max(8, int(droite / 6))                  # le trajet découpé en petits segments de 6 px environ
        p = [f(i / n) for i in range(n + 1)]
    cumul = [0.0]
    for i in range(1, len(p)):
        cumul.append(cumul[-1] + math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]))
    longueur = cumul[-1]
    depart = min(depart, max(6, int(longueur * 0.3)))     # tout près du but, on garde quelques points
    if longueur < depart + fin + pas:
        return []
    points, j, d = [], 1, depart + (decalage % 1.0) * pas
    while d < longueur - fin:
        while j < len(p) - 1 and cumul[j] < d:
            j += 1
        seg = (cumul[j] - cumul[j - 1]) or 1.0
        u = (d - cumul[j - 1]) / seg
        ux, uy = (p[j][0] - p[j - 1][0]) / seg, (p[j][1] - p[j - 1][1]) / seg
        points.append((p[j - 1][0] + (p[j][0] - p[j - 1][0]) * u, p[j - 1][1] + (p[j][1] - p[j - 1][1]) * u,
                       ux, uy, d / longueur))
        d += pas
    return points


def projet_de(chemin):
    """Le dossier de projet d'un chemin : le premier dossier sous le Bureau (« Pigeons », « Mon projet »), sinon le
    dossier du fichier ; rien pour un fichier posé sur le Bureau même."""
    if not chemin:
        return None
    c = os.path.normcase(os.path.abspath(chemin))
    if c.startswith(BUREAU + os.sep):
        morceaux = c[len(BUREAU) + 1:].split(os.sep)
        return os.path.join(BUREAU, morceaux[0]) if len(morceaux) > 1 or os.path.isdir(c) else None
    return os.path.dirname(c)


def zone_ou_carre(zone, point, demi=20):
    """La zone de l'élément si on la connaît ; sinon un petit carré autour du point montré."""
    if zone:
        return zone
    return (point[0] - demi, point[1] - demi, point[0] + demi, point[1] + demi)


class Bulle:
    """La bulle du pigeon : ce que la session attend de l'utilisateur, ou ce qu'elle lui montre."""

    def __init__(self, racine):
        import tkinter as tk
        self.fen = tk.Toplevel(racine)
        self.fen.overrideredirect(True)
        self.fen.attributes("-topmost", True)
        self.fen.attributes("-alpha", 0.9)
        # Petite et discrète (l'utilisateur, 10h33 : « la bulle prend beaucoup de place, c'est un distrayeur ») :
        # une ligne courte par défaut, le texte entier seulement au survol.
        self.texte = tk.Label(self.fen, bg=Panneau.BULLE_FOND, fg=Panneau.BULLE_TEXTE, font=("Segoe UI", 9), justify="left",
                              wraplength=280, padx=7, pady=2, bd=0, highlightthickness=2)
        self.texte.pack()
        self.hwnd = rendre_traversable(self.fen)
        self.fen.withdraw()
        self.contenu = None
        self.taille = (0, 0)
        self.xy = None

    def montrer(self, x, y, texte, couleur, ecrans, zone=None, opacite=90, eviter=()):
        """Ouvre la bulle près du pigeon (x, y), ou à côté de l'encadré quand il montre une zone ; jamais hors de
        l'écran. eviter : d'autres zones à ne pas couvrir (l'autre cible d'une demande, une bulle voisine) ; la bulle
        essaie alors à droite, au-dessus, en dessous, puis à gauche (essai d'AG, 3 octobre 10h14 : « les bulles
        cachent la cible », l'étiquette de l'étape 2 tombait sur l'onglet de l'étape 1)."""
        if opacite != getattr(self, "opacite", None):
            self.fen.attributes("-alpha", max(0.3, min(1.0, opacite / 100)))
            self.opacite = opacite
        if self.contenu != (texte, couleur):
            self.texte.config(text=texte, highlightbackground=couleur, highlightcolor=couleur)
            self.fen.update_idletasks()
            self.taille = (self.fen.winfo_reqwidth(), self.fen.winfo_reqheight())
            if self.contenu is None:
                self.fen.deiconify()
            self.contenu = (texte, couleur)
        lg, ht = self.taille
        # En haut à droite du pigeon : jamais sur la flèche ni sur l'élément montré, qui sont à sa gauche.
        bx, by = int(x) + 14, int(y) - 22 - ht
        e = ecran_de(ecrans, int(x), int(y))
        if zone and e:
            l, t, r, b = (int(v) for v in zone)
            places = [(r + 10, (t + b) // 2 - ht // 2), (l, t - ht - 8), (l, b + 8), (l - lg - 10, (t + b) // 2 - ht // 2)]
            L, T, Rr, Bb = e["travail"]

            def tient(px, py):
                return L + 4 <= px and px + lg <= Rr - 4 and T + 4 <= py and py + ht <= Bb - 4

            def libre(px, py):
                return not any(px < z[2] + 4 and px + lg > z[0] - 4 and py < z[3] + 4 and py + ht > z[1] - 4
                               for z in eviter if z)
            bx, by = next((pl for pl in places if tient(*pl) and libre(*pl)),
                          next((pl for pl in places if tient(*pl)), places[0]))
        if e:
            l, t, r, b = e["travail"]
            bx = min(max(bx, l + 4), r - lg - 4)
            if by < t + 4:
                by = int(y) + 14          # pas de place au-dessus : la bulle passe dessous
        if (bx, by) != self.xy:
            deplacer(self.hwnd, bx, by)
            self.xy = (bx, by)

    def rect(self):
        """La place de la bulle à l'écran, si elle est ouverte (pour que les étiquettes voisines l'évitent)."""
        if self.contenu is None or self.xy is None:
            return None
        return (self.xy[0], self.xy[1], self.xy[0] + self.taille[0], self.xy[1] + self.taille[1])

    def peindre(self):
        """Après un changement d'apparence : les couleurs de la bulle (papier, ou aux couleurs du thème)."""
        self.texte.config(bg=Panneau.BULLE_FOND, fg=Panneau.BULLE_TEXTE)

    def cacher(self):
        if self.contenu is not None:
            self.fen.withdraw()
            self.contenu = None

    def detruire(self):
        self.fen.destroy()


# ---------------------------------------------------------------- la balise (5 octobre 2026)
# L'idée de l'utilisateur (5 octobre 2026, 22h57) : « quand la ligne de guidage va jusqu'à la cible, une bulle qui mentionne où
# exactement ; c'est souvent à la bonne position de l'écran mais il y a des fenêtres ouvertes par-dessus ; quelques mots
# pour orienter : quelle couche, quelle app ; esthétique, en harmonie avec la ligne, des effets d'animation ».
# Les maquettes : maquettes\maquette_balise.gif ; le plan : PLAN_BALISES_ET_FLUIDITE.md.
# Le halo doux autour de la pastille reprend l'idée de Windows-MCP (github.com/CursorTouch/Windows-MCP, licence MIT,
# control_overlay_art.py : la forme floutée, moins la forme) ; le code ici est écrit pour les pigeons.

BALISE_K = 2                  # dessinée à 2x puis réduite : des bords lisses
BALISE_MARGE = 28             # la balise laisse toujours libres la cible et 28 px autour
BALISE_ENTREE_S = 0.20        # fondu et glissé de 10 px le long de la ligne, après le tracé de la ligne (250 ms)
BALISE_SORTIE_S = 0.15
ONDE_S = 0.45                 # l'onde qui part de l'encadré à l'arrivée, une seule fois
AMBRE = (255, 176, 46)
_POLICES, _ICONES = {}, {}


def rvb(couleur):
    couleur = couleur.lstrip("#")
    return tuple(int(couleur[i:i + 2], 16) for i in (0, 2, 4))


def police_balise(taille, gras=False):
    """Segoe UI Variable (la police de Windows 11), en demi-gras pour le nom de l'app ; Segoe UI sinon."""
    cle = (taille, gras)
    if cle not in _POLICES:
        from PIL import ImageFont
        polices = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        try:
            f = ImageFont.truetype(str(polices / "SegUIVar.ttf"), taille)
            try:
                f.set_variation_by_name(b"Semibold Text" if gras else b"Regular")
            except Exception:
                pass
        except OSError:
            try:
                f = ImageFont.truetype(str(polices / ("segoeuib.ttf" if gras else "segoeui.ttf")), taille)
            except OSError:
                f = ImageFont.load_default()
        _POLICES[cle] = f
    return _POLICES[cle]


def icone_app(exe, taille):
    """L'icône d'un programme en RGBA (ExtractIconEx, puis dessinée dans un bitmap 32 bits) ; None si on ne peut pas
    (les apps du Windows Store refusent parfois). Gardée par programme."""
    cle = (exe, taille)
    if cle in _ICONES:
        return _ICONES[cle]
    im = None
    if exe:
        try:
            import win32con
            import win32gui
            import win32ui
            from PIL import Image
            grandes, petites = win32gui.ExtractIconEx(exe, 0, 1)
            if grandes or petites:
                h = (grandes or petites)[0]
                dc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                mem = dc.CreateCompatibleDC()
                bmp = win32ui.CreateBitmap()
                bmp.CreateCompatibleBitmap(dc, 32, 32)
                mem.SelectObject(bmp)
                mem.FillSolidRect((0, 0, 32, 32), 0)
                win32gui.DrawIconEx(mem.GetSafeHdc(), 0, 0, h, 32, 32, 0, None, win32con.DI_NORMAL)
                im = Image.frombuffer("RGBA", (32, 32), bmp.GetBitmapBits(True), "raw", "BGRA", 0, 1).copy()
                if im.getextrema()[3][1] == 0:
                    im.putalpha(255)            # une vieille icône sans transparence
                im = im.resize((taille, taille), Image.LANCZOS)
                win32gui.DeleteObject(bmp.GetHandle())
                mem.DeleteDC()
                dc.DeleteDC()
                for x in grandes + petites:
                    win32gui.DestroyIcon(x)
        except Exception as e:
            log.info("icône de %s : %s", exe, e)
            im = None
    _ICONES[cle] = im
    return im


def image_de_balise(morceaux, puces, couleur, etape, fond, texte):
    """La pastille : [numéro] [icône] App › endroit › élément [puces]. morceaux : [(exe, texte, gras)] ;
    puces : [(exe, texte, genre)] où genre « alerte » (ambre : ce qui couvre la cible) ou « info ». Rend (image RGBA
    aux couleurs déjà multipliées par l'alpha, demi-largeur du halo), en pixels de l'écran."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    K = BALISE_K
    terne = tuple(int(a + (b - a) * 0.45) for a, b in zip(texte, fond))      # entre le texte et le fond
    f, fg, fp = police_balise(12 * K), police_balise(12 * K, True), police_balise(11 * K)
    mesure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    px, ht = 10 * K, 28 * K
    elems, x = [], px
    if etape:
        elems.append(("etape", x, str(etape)))
        x += 21 * K
    for i, (exe, t, gras) in enumerate(morceaux):
        if i:
            elems.append(("sep", x, None))
            x += int(mesure.textlength(" › ", font=f))
        ic = icone_app(exe, 18 * K) if exe else None
        if ic is not None:
            elems.append(("ic", x, ic))
            x += ic.width + 5 * K
        fo = fg if gras else f
        elems.append(("txt", x, (t, fo)))
        x += int(mesure.textlength(t, font=fo))
    for exe, t, genre in puces:
        x += 7 * K
        ic = icone_app(exe, 14 * K) if exe else None
        lg = int(mesure.textlength(t, font=fp)) + (ic.width + 4 * K if ic is not None else 0) + 14 * K
        elems.append(("puce", x, (ic, t, lg, genre)))
        x += lg
    lg = x + px
    halo = 14 * K
    taille = (lg + 2 * halo, ht + 2 * halo)
    forme = Image.new("L", taille, 0)
    ImageDraw.Draw(forme).rounded_rectangle((halo, halo, halo + lg, halo + ht), radius=ht // 2, fill=255)
    # Le halo : la forme floutée, moins la forme (comme Windows-MCP) ; de la couleur de la ligne.
    aura = ImageChops.subtract(forme.filter(ImageFilter.GaussianBlur(7 * K)), forme).point(lambda a: min(255, int(a * 1.5)))
    im = Image.new("RGBA", taille, couleur + (0,))
    im.putalpha(aura)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((halo, halo, halo + lg, halo + ht), radius=ht // 2, fill=fond + (240,),
                        outline=couleur + (255,), width=int(1.5 * K))
    cy = halo + ht // 2
    for genre, ex, val in elems:
        ex += halo
        if genre == "etape":
            d.ellipse((ex, cy - 8 * K, ex + 16 * K, cy + 8 * K), fill=couleur + (255,))
            d.text((ex + 8 * K, cy), val, font=police_balise(10 * K, True), fill=(255, 255, 255), anchor="mm")
        elif genre == "sep":
            d.text((ex + 3 * K, cy), "›", font=f, fill=terne, anchor="lm")
        elif genre == "ic":
            im.alpha_composite(val, (ex, cy - val.height // 2))
        elif genre == "txt":
            t, fo = val
            d.text((ex, cy), t, font=fo, fill=texte, anchor="lm")
        else:
            ic, t, lgp, g = val
            teinte = AMBRE if g == "alerte" else couleur
            # Des teintes opaques (le dessin remplace les pixels, il ne les mélange pas : une teinte transparente
            # laissait voir le fond de l'écran à travers la puce).
            d.rounded_rectangle((ex, cy - 10 * K, ex + lgp, cy + 10 * K), radius=10 * K,
                                fill=tuple(int(f + (t - f) * 0.2) for f, t in zip(fond, teinte)) + (245,),
                                outline=tuple(int(f + (t - f) * 0.85) for f, t in zip(fond, teinte)) + (255,), width=K)
            xx = ex + 7 * K
            if ic is not None:
                im.alpha_composite(ic, (xx, cy - ic.height // 2))
                xx += ic.width + 4 * K
            clair = sum(fond) > 380
            d.text((xx, cy), t, font=fp, anchor="lm",
                   fill=(teinte if not clair else tuple(int(c * 0.55) for c in teinte)) if g != "alerte"
                   else ((150, 85, 0) if clair else (255, 214, 150)))
    im = im.resize((taille[0] // K, taille[1] // K), Image.LANCZOS)
    # Les couleurs multipliées par l'alpha, comme le veut UpdateLayeredWindow.
    im = Image.frombytes("RGBA", im.size, im.convert("RGBa").tobytes())
    return im, halo // K


def image_d_onde(zone, couleur, u, arrondi=8):
    """L'onde d'arrivée : un anneau qui part de l'encadré, s'élargit de 16 px et s'efface (u de 0 à 1)."""
    from PIL import Image, ImageDraw
    K, pad = 2, 22
    l, t, r, b = zone
    lg, ht = int(r - l) + 2 * pad, int(b - t) + 2 * pad
    im = Image.new("RGBA", (lg * K, ht * K), couleur + (0,))
    d = ImageDraw.Draw(im)
    m = 2 + 16 * (1 - (1 - u) ** 3)
    a = int(190 * (1 - u))
    d.rounded_rectangle(((pad - m) * K, (pad - m) * K, (lg - pad + m) * K, (ht - pad + m) * K),
                        radius=int((arrondi + m) * K), outline=couleur + (a,), width=2 * K)
    im = im.resize((lg, ht), Image.LANCZOS)
    return Image.frombytes("RGBA", im.size, im.convert("RGBa").tobytes()), (int(l) - pad, int(t) - pad)


def place_sur_ligne(lg, ht, de, a, zone, eviter, ecrans):
    """Le centre de la balise SUR la ligne de « de » (la souris, ou l'étape 1) à « a » (la cible) : on part de la
    cible et on recule de 4 px en 4 px jusqu'à ce qu'elle ne touche ni la cible et ses alentours (BALISE_MARGE), ni les
    zones à éviter (l'autre cible), et qu'elle tienne dans un écran, hors de la barre des tâches. L'idée vient de
    « flip / shift / hide » de Floating UI (licence MIT), mais le long de la ligne. None : pas de place (la souris est
    déjà tout près, ou la ligne est trop courte) ; la balise s'efface."""
    (x0, y0), (x1, y1) = de, a
    long = math.hypot(x1 - x0, y1 - y0)
    if long < 1:
        return None
    ux, uy = (x1 - x0) / long, (y1 - y0) / long
    m = BALISE_MARGE
    zones = [(zone[0] - m, zone[1] - m, zone[2] + m, zone[3] + m)] + [z for z in eviter if z]
    for recul in range(40, int(long) - 40, 4):
        cx, cy = x1 - ux * recul, y1 - uy * recul
        r = (cx - lg / 2, cy - ht / 2, cx + lg / 2, cy + ht / 2)
        if any(r[0] < z[2] and r[2] > z[0] and r[1] < z[3] and r[3] > z[1] for z in zones):
            continue
        e = ecran_de(ecrans, int(cx), int(cy))
        if e and e["travail"][0] + 4 <= r[0] and r[2] <= e["travail"][2] - 4 and e["travail"][1] + 4 <= r[1] \
                and r[3] <= e["travail"][3] - 4:
            return cx, cy
    return None


class Balise:
    """Une balise à l'écran : une fenêtre en couches (comme les lignes), qui traverse les clics. Elle entre en
    fondu en glissant de 10 px le long de la ligne vers la cible, après le tracé de la ligne ; l'encadré lance une
    onde, une fois ; puis plus rien ne bouge. Elle sort
    en fondu (150 ms). Animations de Windows coupées : un fondu seulement."""

    def __init__(self, racine):
        import tkinter as tk
        self.fens = []
        for _ in range(2):                    # la pastille, et l'onde autour de l'encadré
            f = tk.Toplevel(racine)
            f.overrideredirect(True)
            f.geometry("1x1+-3000+-3000")
            f.attributes("-topmost", True)
            f.update_idletasks()
            h = user32.GetParent(f.winfo_id())
            ex = user32.GetWindowLongW(W.HWND(h), GWL_EXSTYLE)
            user32.SetWindowLongW(W.HWND(h), GWL_EXSTYLE,
                                  ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
            self.fens.append((f, h))
        self.hwnd, self.hwnd_onde = self.fens[0][1], self.fens[1][1]
        self.contenu, self.image, self.halo = None, None, 0
        self.nee, self.partie = None, None
        self.xy, self.vise, self.dir = None, None, (1.0, 0.0)
        self.dernier = None                   # (x, y, opacité) envoyés : on ne renvoie que si ça change
        self.onde_finie = False

    def taille(self):
        """La taille de la pastille sans son halo (pour la placer)."""
        lg, ht = self.image.size
        return lg - 2 * self.halo, ht - 2 * self.halo

    def peindre(self, contenu, couleur, fond, texte):
        """Redessine la pastille si ce qu'elle dit, sa couleur ou le thème ont changé (sinon rien : elle est gardée)."""
        cle = (contenu, couleur, fond, texte)
        if cle != self.contenu:
            morceaux, puces, etape = contenu
            self.image, self.halo = image_de_balise(morceaux, puces, couleur, etape, fond, texte)
            self.contenu, self.dernier = cle, None

    def rect(self):
        """La place de la pastille (sans halo) à son arrivée : les points de la ligne s'arrêtent là."""
        if not self.vise or not self.image:
            return None
        lg, ht = self.taille()
        return (self.vise[0] - lg / 2, self.vise[1] - ht / 2, self.vise[0] + lg / 2, self.vise[1] + ht / 2)

    def poser(self, centre, direction, maintenant, depart, bouge, zone_onde=None, couleur=None, respire=False):
        """centre : où elle doit être (sur la ligne) ; direction : celle de la ligne vers la cible ; depart : l'heure où
        la ligne est apparue (la balise entre après son tracé)."""
        if self.partie is not None:
            self.partie = None                # elle revient avant d'être partie
        if self.nee is None:
            self.nee = max(maintenant, depart + (TRACE_S if bouge else 0))
        self.vise, self.dir = centre, direction
        if self.xy is None:
            self.xy = list(centre)
        else:                                 # elle suit la ligne en douceur quand la souris bouge
            k = 0.35
            self.xy[0] += (centre[0] - self.xy[0]) * k
            self.xy[1] += (centre[1] - self.xy[1]) * k
        u = (maintenant - self.nee) / BALISE_ENTREE_S
        if u <= 0:
            self.envoyer(0, 0, 0)
            return
        u = min(1.0, u)
        douce = 1 - (1 - u) ** 3
        recul = 10 * (1 - douce) if bouge else 0          # le glissé : de 10 px en arrière jusqu'à sa place
        x, y = self.xy[0] - direction[0] * recul, self.xy[1] - direction[1] * recul
        opacite = 255 * douce
        if respire and u >= 1 and bouge:
            opacite *= 0.86 + 0.14 * (1 + math.cos(2 * math.pi * (maintenant - self.nee) / 3.0)) / 2
        self.envoyer(x, y, opacite)
        # L'onde d'arrivée, une fois, autour de l'encadré de la cible.
        if zone_onde and bouge and not self.onde_finie:
            v = (maintenant - self.nee) / ONDE_S
            if 0 <= v < 1:
                im, (ox, oy) = image_d_onde(zone_onde, couleur, v)
                couche_alpha(self.hwnd_onde, im, ox, oy)
            elif v >= 1:
                self.onde_finie = True
                user32.SetWindowPos(W.HWND(self.hwnd_onde), None, -3000, -3000, 1, 1, SWP_NOZORDER | SWP_NOACTIVATE)

    def envoyer(self, x, y, opacite):
        lg, ht = self.image.size
        pos = (int(x - lg / 2), int(y - ht / 2), int(opacite))
        if pos != self.dernier:
            couche_alpha(self.hwnd, self.image, pos[0], pos[1], pos[2])
            self.dernier = pos

    def partir(self, maintenant):
        """Le geste est fait, ou la balise n'a plus de place : elle s'efface en 150 ms. Rend vrai quand c'est fini."""
        if self.image is None or self.nee is None or self.xy is None:
            return True
        if self.partie is None:
            self.partie = maintenant
            self.depart_opacite = (self.dernier or (0, 0, 0))[2]
        u = (maintenant - self.partie) / BALISE_SORTIE_S
        if u >= 1:
            self.envoyer(-3000, -3000, 0)
            self.nee, self.xy, self.onde_finie = None, None, False
            return True
        self.envoyer(self.xy[0], self.xy[1], self.depart_opacite * (1 - u))
        return False

    def detruire(self):
        for f, _h in self.fens:
            f.destroy()


def dans_zone(x, y, zone, point, rayon=30):
    """Un clic tombe-t-il sur l'endroit montré ? Dans sa zone (un peu élargie), ou près du point."""
    if zone and zone[0] - 6 <= x <= zone[2] + 6 and zone[1] - 6 <= y <= zone[3] + 6:
        return True
    return point is not None and math.hypot(x - point[0], y - point[1]) < rayon


user32.GetForegroundWindow.restype = W.HWND


def amener_devant(hwnd):
    """Ramène une fenêtre devant. Windows refuse SetForegroundWindow à un programme qui n'est pas au premier plan :
    on attache un instant notre fil à celui de la fenêtre active (la méthode habituelle), puis on détache."""
    if user32.IsIconic(W.HWND(hwnd)):
        user32.ShowWindow(W.HWND(hwnd), 9)                  # SW_RESTORE
    avant = user32.GetForegroundWindow()
    fil_avant = user32.GetWindowThreadProcessId(avant, None)
    fil_ici = ctypes.windll.kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(fil_ici, fil_avant, True)
    user32.BringWindowToTop(W.HWND(hwnd))
    user32.SetForegroundWindow(W.HWND(hwnd))
    user32.AttachThreadInput(fil_ici, fil_avant, False)


def activer_element(uia, U, el):
    """Active un élément sans toucher la souris : Invoke, sinon Select, sinon l'action par défaut ; sur l'élément
    puis sur ses parents (le nom est souvent sur un texte, le geste sur la ligne qui le contient)."""
    marcheur = uia.ControlViewWalker
    for _ in range(4):
        if not el:
            return False
        for pid, interface, geste in ((U.UIA_InvokePatternId, U.IUIAutomationInvokePattern, "Invoke"),
                                      (U.UIA_SelectionItemPatternId, U.IUIAutomationSelectionItemPattern, "Select"),
                                      (U.UIA_LegacyIAccessiblePatternId, U.IUIAutomationLegacyIAccessiblePattern,
                                       "DoDefaultAction")):
            try:
                motif = el.GetCurrentPattern(pid)
                if motif:
                    getattr(motif.QueryInterface(interface), geste)()
                    return True
            except Exception:
                continue
        el = marcheur.GetParentElement(el)
    return False


def cliquer(x, y):
    """Un clic gauche en (x, y), puis la souris revient où elle était (dernier recours d'« Aller à la session »)."""
    pt = W.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(0x2, 0, 0, 0, 0)
    user32.mouse_event(0x4, 0, 0, 0, 0)
    user32.SetCursorPos(pt.x, pt.y)


class Vigie(threading.Thread):
    """Le garde-fou de l'affichage (5 octobre 2026, 22h39 : le fil de Tk a gelé pendant la mise à jour de l'app Claude,
    Windows a fermé le programme, et le journal n'en a rien dit). Un fil à part regarde l'heure de la dernière image :
    sans image depuis 5 s, la pile de l'affichage va dans le journal (où il bloque), et encore à 30 s ; quand il repart,
    le journal dit combien de temps il a gelé. Elle ne relance rien : montre.py et annonce.py le font, de l'extérieur."""

    def __init__(self, volee):
        super().__init__(daemon=True, name="vigie")
        self.volee = volee

    def run(self):
        import traceback
        debut, piles = None, 0
        while True:
            time.sleep(1.0)
            fige = time.time() - self.volee.t_prec
            if fige > AFFICHAGE_FIGE_S and (piles == 0 or (piles == 1 and fige > 30)):
                debut = debut or self.volee.t_prec
                piles += 1
                cadre = sys._current_frames().get(threading.main_thread().ident)
                pile = "".join(traceback.format_stack(cadre)) if cadre else "(pile introuvable)"
                log.error("l'affichage est figé depuis %d s ; il en est là :\n%s", fige, pile)
            elif fige < 1 and debut:
                log.warning("l'affichage repart après %d s de gel", time.time() - debut)
                debut, piles = None, 0


class Raccourci(threading.Thread):
    """Le raccourci clavier global Ctrl+Alt+P (« prochaine action »). Windows envoie WM_HOTKEY à ce fil-ci ;
    il le passe à l'affichage par une file (la boucle de Tk ne lit pas les messages adressés aux fils)."""

    def __init__(self, file):
        super().__init__(daemon=True)
        self.file, self.ok, self.ok_terminer = file, None, None

    def run(self):
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
        self.ok = bool(user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("P")))
        # Ctrl+Alt+T, pour « Terminer » : « C'est fait » ou « Terminer » sur la première chose à faire. L'idée d'AG
        # était Ctrl+Alt+Espace, déjà pris par un autre programme chez l'utilisateur (2 octobre, 13h30).
        self.ok_terminer = bool(user32.RegisterHotKey(None, 2, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("T")))
        if not self.ok:
            log.warning("Ctrl+Alt+P est déjà pris par un autre programme")
        if not self.ok_terminer:
            log.warning("Ctrl+Alt+T est déjà pris par un autre programme")
        if not (self.ok or self.ok_terminer):
            return
        msg = W.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:                       # WM_HOTKEY : wParam dit lequel (1 ou 2)
                self.file.put("prochaine" if msg.wParam == 1 else "terminer")


def barre_de_titre_sombre(fen):
    """La barre de titre de Windows aux couleurs du panneau : sombre sur un fond sombre, claire sur un fond clair
    (DWMWA_USE_IMMERSIVE_DARK_MODE = 20) ; et des coins arrondis sous Windows 11 (DWMWA_WINDOW_CORNER_PREFERENCE = 33)."""
    try:
        fen.update_idletasks()
        hwnd = user32.GetParent(fen.winfo_id())
        sombre = ctypes.c_int(1 if clarte(Panneau.FOND) < 0.5 else 0)
        dwmapi.DwmSetWindowAttribute(W.HWND(hwnd), 20, ctypes.byref(sombre), ctypes.sizeof(sombre))
        arrondi = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(W.HWND(hwnd), 33, ctypes.byref(arrondi), ctypes.sizeof(arrondi))
    except Exception as e:
        log.warning("barre de titre : %s", e)


def regler_demarrage(actif):
    """Le réglage « Lancer les pigeons avec Windows » : un raccourci dans le dossier Démarrage de Windows,
    posé ou retiré quand l'utilisateur coche ou décoche la case (rien d'autre n'est touché)."""
    lien = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Pigeons.lnk"
    try:
        if actif:
            import win32com.client
            r = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(lien))
            r.TargetPath = str(Path(sys.executable).with_name("pythonw.exe"))
            r.Arguments = f'"{Path(__file__).resolve()}"'
            r.WorkingDirectory = str(ICI)
            r.Description = "Pigeons : où travaillent les Claude"
            r.Save()
        else:
            lien.unlink(missing_ok=True)
        log.info("démarrage avec Windows : %s", actif)
    except Exception as e:
        log.warning("démarrage avec Windows : %s", e)


class Infobulle:
    """Ce que fait un bouton, dit au survol (3 octobre, en complément de l'onglet « Guide » : l'explication là où on
    en a besoin). Elle s'ouvre après 0,6 s, pour ne pas clignoter sous la souris, et se ferme dès qu'on part ou qu'on clique."""

    def __init__(self, widget, texte, dessus=False):
        self.widget, self.texte, self.dessus = widget, texte, dessus
        self.fen, self.attente = None, None
        widget.bind("<Enter>", self.prevoir, add="+")
        widget.bind("<Leave>", self.cacher, add="+")
        widget.bind("<ButtonPress>", self.cacher, add="+")

    def prevoir(self, _e=None):
        self.cacher()
        self.attente = self.widget.after(600, self.montrer)

    def montrer(self):
        import tkinter as tk
        self.attente = None
        if self.fen is not None or not self.widget.winfo_exists():
            return
        self.fen = tk.Toplevel(self.widget)
        self.fen.overrideredirect(True)
        self.fen.attributes("-topmost", True)
        tk.Label(self.fen, text=tr(self.texte), bg=Panneau.BOUTON, fg=Panneau.TEXTE, font=("Segoe UI", 8), padx=6, pady=3,
                 justify="left", wraplength=320).pack()
        self.fen.update_idletasks()
        x = self.widget.winfo_rootx()
        y = (self.widget.winfo_rooty() - self.fen.winfo_reqheight() - 4 if self.dessus
             else self.widget.winfo_rooty() + self.widget.winfo_height() + 4)
        self.fen.geometry(f"+{x}+{y}")

    def cacher(self, _e=None):
        if self.attente:
            try:
                self.widget.after_cancel(self.attente)
            except Exception:
                pass
            self.attente = None
        if self.fen is not None:
            self.fen.destroy()
            self.fen = None


class Panneau:
    """Le panneau des pigeons (l'utilisateur, 11h29
 : « plus beau, plus complet en options ») :
    - en haut, le compte des sessions ;
    - « À faire pour toi » : une carte par session qui t'attend ou te montre quelque chose, avec ses boutons
      (Guider, Plus tard, C'est fait, Reprendre) ;
    - « Au travail » et « Au repos » : une ligne par session, son fichier, son rythme, ses pigeonneaux ;
    - en bas : Tout en pause, Masquer les pigeons, Réglages, Arrêter.
    Il ne se reconstruit que si son contenu a changé (sinon il clignoterait chaque seconde)."""

    # Les couleurs : celles de la palette en vigueur (appliquer_palette) ; au départ, la palette sombre.
    FOND, CARTE, TEXTE, PALE, ACCENT = "#16171b", "#22242b", "#e9e9ec", "#9a9ca6", "#8ab4ff"
    BOUTON, BOUTON_ACTIF, ACTIF_TEXTE, DANGER, DANGER_ACTIF, TERNE = ("#2b2e36", "#3a3e48", "#ffffff", "#3a2326",
                                                                     "#5a2b30", "#6b6d75")
    BULLE_FOND, BULLE_TEXTE = "#fffdf5", "#1b1b1b"
    STYLE_CASE = {"bg": "#16171b", "fg": "#e9e9ec", "selectcolor": "#2b2e36", "activebackground": "#16171b",
                  "activeforeground": "#ffffff", "font": ("Segoe UI", 9), "anchor": "w", "bd": 0,
                  "highlightthickness": 0}

    @classmethod
    def appliquer_palette(cls, pal):
        """Les couleurs du panneau, de ses cartes, de ses boutons et de la fenêtre des réglages."""
        for cle, valeur in pal.items():
            setattr(cls, cle, valeur)
        cls.STYLE_CASE = dict(cls.STYLE_CASE, bg=pal["FOND"], fg=pal["TEXTE"], selectcolor=pal["BOUTON"],
                              activebackground=pal["FOND"], activeforeground=pal["ACTIF_TEXTE"])

    def styler_barre(self):
        self.style.configure("Pigeons.Vertical.TScrollbar", background=self.BOUTON, troughcolor=self.FOND,
                             bordercolor=self.FOND, arrowcolor=self.PALE, lightcolor=self.BOUTON, darkcolor=self.BOUTON)

    def peindre(self):
        """Après un changement d'apparence : les parties fixes du panneau prennent les nouvelles couleurs, et les
        cartes se refont."""
        F, T, P = self.FOND, self.TEXTE, self.PALE
        self.racine.configure(bg=F)
        for w in (self.tete, self.barre_onglets, self.pied, self.cadre, self.zone, self.corps):
            w.configure(bg=F)
        self.l_titre.configure(bg=F, fg=T)
        self.resume.configure(bg=F, fg=P)
        self.aide.configure(bg=F, fg=P)
        self.separateur.configure(bg=self.BOUTON)
        for b in self.b_onglets.values():
            b.configure(bg=F, activebackground=F)
        self.styler_onglets()
        for b in (self.b_pause, self.b_masquer, self.b_reglages):
            b.configure(bg=self.BOUTON, fg=T, activebackground=self.BOUTON_ACTIF, activeforeground=self.ACTIF_TEXTE)
        self.b_arreter.configure(bg=self.DANGER, fg=T, activebackground=self.DANGER_ACTIF,
                                 activeforeground=self.ACTIF_TEXTE)
        self.styler_barre()
        self.barre.configure(style="Pigeons.Vertical.TScrollbar")     # sinon son fond garde l'ancienne couleur
        barre_de_titre_sombre(self.racine)
        self.signature = None
        self.rafraichir()

    def __init__(self, volee):
        import tkinter as tk
        self.tk, self.v = tk, volee
        r = self.racine = volee.racine
        r.title("Pigeons")
        r.configure(bg=self.FOND)
        # Le ✕ de la fenêtre la réduit dans la barre des tâches : les pigeons continuent. Seul « Arrêter » les arrête
        # (le 2 octobre à 15h59, ils s'étaient arrêtés sans erreur, sans doute par ce ✕).
        r.protocol("WM_DELETE_WINDOW", r.iconify)
        # Redimensionnable (l'utilisateur, 12h23) : Windows offre alors ses ancrages (glisser au bord, Win+flèches,
        # dispositions au survol du bouton « agrandir »), comme pour les autres applications.
        r.resizable(True, True)
        r.minsize(440, 240)
        barre_de_titre_sombre(r)
        tete = self.tete = tk.Frame(r, bg=self.FOND)
        tete.pack(fill="x", padx=16, pady=(12, 2))
        self.l_titre = tk.Label(tete, text="Pigeons", bg=self.FOND, fg=self.TEXTE, font=("Segoe UI Semibold", 14))
        self.l_titre.pack(side="left")
        self.resume = tk.Label(tete, text="", bg=self.FOND, fg=self.PALE, font=("Segoe UI", 9))
        self.resume.pack(side="right", pady=(6, 0))
        # Deux onglets : ce qui t'attend, et le guide de l'app (l'utilisateur, 16h51 : « un onglet qui explique l'app »).
        barre_onglets = self.barre_onglets = tk.Frame(r, bg=self.FOND)
        barre_onglets.pack(fill="x", padx=12, pady=(4, 0))
        self.onglet, self.b_onglets = "a_faire", {}
        for cle, texte in (("a_faire", "À faire"), ("guide", "Guide")):
            b = tk.Button(barre_onglets, text=tr(texte), relief="flat", bd=0, cursor="hand2", bg=self.FOND,
                          activebackground=self.FOND, padx=8, pady=2, command=lambda c=cle: self.choisir_onglet(c))
            b.pack(side="left")
            self.b_onglets[cle] = b
        self.styler_onglets()
        self.separateur = tk.Frame(r, bg=self.BOUTON, height=1)
        self.separateur.pack(fill="x", padx=16, pady=(2, 4))
        # D'abord ce qui reste en bas (l'aide, les boutons), puis le corps qui prend toute la place restante.
        self.aide = tk.Label(r, text=tr("Ctrl+Alt+P : prochaine action · Ctrl+Alt+T : c'est fait ou terminer"),
                             bg=self.FOND, fg=self.PALE, font=("Segoe UI", 8))
        self.aide.pack(side="bottom", anchor="w", padx=18, pady=(0, 6))
        pied = self.pied = tk.Frame(r, bg=self.FOND)
        pied.pack(side="bottom", fill="x", padx=12, pady=(8, 4))
        # Le corps défile à la molette quand le panneau est petit ou que les cartes sont nombreuses.
        from tkinter import ttk
        self.style = ttk.Style(r)
        self.style.theme_use("clam")
        self.styler_barre()
        cadre = self.cadre = tk.Frame(r, bg=self.FOND)
        cadre.pack(fill="both", expand=True, padx=(12, 4))
        self.zone = tk.Canvas(cadre, bg=self.FOND, highlightthickness=0, bd=0)
        self.barre = ttk.Scrollbar(cadre, orient="vertical", command=self.zone.yview, style="Pigeons.Vertical.TScrollbar")
        self.zone.configure(yscrollcommand=self.barre.set)
        self.barre.pack(side="right", fill="y")
        self.zone.pack(side="left", fill="both", expand=True)
        self.corps = tk.Frame(self.zone, bg=self.FOND)
        self.id_corps = self.zone.create_window((0, 0), window=self.corps, anchor="nw")
        self.corps.bind("<Configure>", lambda _e: self.zone.configure(scrollregion=self.zone.bbox("all")))
        self.zone.bind("<Configure>", self.redimensionne)
        self.zone.bind("<Enter>", lambda _e: self.zone.bind_all("<MouseWheel>", self.molette))
        self.zone.bind("<Leave>", lambda _e: self.zone.unbind_all("<MouseWheel>"))
        self.largeur = 560
        self.b_pause = self.bouton(pied, "Tout en pause", volee.tout_en_pause,
                                   aide="Tous les pigeons attendent sur la barre des tâches.", dessus=True)
        self.b_masquer = self.bouton(pied, "Masquer les guides", self.masquer,
                                     aide="Cache les lignes, les flèches, les encadrés et les étiquettes ; le panneau reste.", dessus=True)
        self.b_reglages = self.bouton(pied, "Réglages", volee.ouvrir_reglages, aide="Ouvre les réglages.", dessus=True)
        self.b_arreter = self.bouton(pied, "Arrêter", volee.arreter, danger=True, cote="right",
                                     aide="Arrête les pigeons. Le ✕ de la fenêtre, lui, la réduit seulement.", dessus=True)
        self.signature = None
        self.place = False
        self.geo_apres = None
        self.dernier_ancrage = None
        r.bind("<Configure>", self.retenir_geometrie)
        r.after(10, self.placer)
        r.after(300, self.suivre_claude)

    @staticmethod
    def bouton(parent, texte, commande, danger=False, petit=False, cote="left", aide=None, dessus=False):
        """Un bouton du panneau ; aide : ce qu'il fait, dit au survol (Infobulle)."""
        import tkinter as tk
        P = Panneau
        b = tk.Button(parent, text=tr(texte), command=commande, relief="flat", bd=0, cursor="hand2",
                      bg=P.DANGER if danger else P.BOUTON, fg=P.TEXTE,
                      activebackground=P.DANGER_ACTIF if danger else P.BOUTON_ACTIF, activeforeground=P.ACTIF_TEXTE,
                      font=("Segoe UI", 8 if petit else 9), padx=8 if petit else 12, pady=1 if petit else 4)
        b.pack(side=cote, padx=3)
        if aide:
            Infobulle(b, aide, dessus)
        return b

    def styler_onglets(self):
        """L'onglet choisi en clair et souligné, l'autre en pâle."""
        for cle, b in self.b_onglets.items():
            actif = cle == self.onglet
            b.config(fg=self.TEXTE if actif else self.PALE, activeforeground=self.TEXTE,
                     font=("Segoe UI Semibold", 10, "underline") if actif else ("Segoe UI", 10))

    def choisir_onglet(self, cle):
        self.onglet = cle
        self.styler_onglets()
        self.signature = None
        self.zone.yview_moveto(0)
        self.rafraichir()

    def montrer_guide(self):
        """L'onglet « Guide » : ce que fait l'app et comment s'en servir, en cartes (contenu_guide)."""
        tk, v = self.tk, self.v
        for w in self.corps.winfo_children():
            w.destroy()
        largeur = max(240, self.largeur - 70)
        for section in contenu_guide():
            c = tk.Frame(self.corps, bg=self.CARTE, padx=12, pady=8)
            c.pack(fill="x", padx=4, pady=4)
            tk.Label(c, text=section["titre"].upper(), bg=self.CARTE, fg=self.ACCENT, font=("Segoe UI Semibold", 8),
                     anchor="w").pack(fill="x", pady=(0, 4))
            if section.get("couleurs"):
                for imp in ("bloquee", "haute", "normale", "basse"):
                    ligne = tk.Frame(c, bg=self.CARTE)
                    ligne.pack(fill="x", pady=1)
                    tk.Label(ligne, text="      ", bg=v.reglages["couleur_" + imp], bd=0).pack(side="left", padx=(0, 8))
                    nom = {"bloquee": "Bloquée : une permission à donner", "haute": "Haute : un geste à faire",
                           "normale": "Normale : une question posée", "basse": "Basse : à toi quand tu veux"}[imp]
                    tk.Label(ligne, text=tr(nom), bg=self.CARTE, fg=self.TEXTE, font=("Segoe UI", 9),
                             anchor="w").pack(side="left")
            for texte in section["texte"]:
                tk.Label(c, text=texte, bg=self.CARTE, fg=self.TEXTE if not texte.startswith("•") else self.PALE,
                         font=("Segoe UI", 9), anchor="w", justify="left", wraplength=largeur).pack(fill="x", pady=1)
            if section.get("dossier"):
                bas = tk.Frame(c, bg=self.CARTE)
                bas.pack(fill="x", pady=(4, 0))
                self.bouton(bas, "Ouvrir le dossier", lambda: os.startfile(str(ICI)), petit=True)

    def retraduire(self):
        """Après un changement de langue : les boutons du pied, l'aide, et le corps refait au prochain tour."""
        for cle, texte in (("a_faire", "À faire"), ("guide", "Guide")):
            self.b_onglets[cle].config(text=tr(texte))
        self.b_reglages.config(text=tr("Réglages"))
        self.b_arreter.config(text=tr("Arrêter"))
        self.signature = None
        self.rafraichir()

    def masquer(self):
        self.v.masques = not self.v.masques
        self.b_masquer.config(text=tr("Montrer les guides") if self.v.masques else tr("Masquer les guides"))

    def placer(self):
        """Au lancement : la place et la taille gardées (si elles tombent encore sur un écran) ; sinon, en bas à
        droite de l'écran du bas (l'écran d'essai), 600 × 440."""
        geo = self.v.reglages.get("panneau_geometrie") or ""
        m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", geo)
        if m and ecran_de(self.v.ecrans, int(m.group(3)) + 40, int(m.group(4)) + 20):
            self.racine.geometry(geo)
        else:
            bas = max(self.v.ecrans, key=lambda e: (e["rect"][1], e["rect"][0]))
            l, t, r, b = bas["travail"]
            self.racine.geometry(f"600x440+{r - 624}+{b - 488}")
        self.place = True

    def redimensionne(self, e):
        """Le corps prend la largeur du panneau ; s'il a assez changé, les cartes se refont (leurs textes se replient)."""
        self.zone.itemconfigure(self.id_corps, width=e.width)
        if abs(e.width - self.largeur) > 24:
            self.largeur = e.width
            self.signature = None
            self.racine.after_idle(self.rafraichir)

    def molette(self, e):
        self.zone.yview_scroll(int(-e.delta / 120), "units")

    def retenir_geometrie(self, e=None):
        """Garde la place et la taille du panneau dans les réglages, 0,8 s après le dernier mouvement."""
        if e is not None and e.widget is not self.racine:
            return
        if self.geo_apres:
            self.racine.after_cancel(self.geo_apres)
        self.geo_apres = self.racine.after(800, self.sauver_geometrie)

    def sauver_geometrie(self):
        self.geo_apres = None
        if self.racine.state() == "normal" and self.place:
            self.v.reglages["panneau_geometrie"] = self.racine.geometry()
            sauver_reglages(self.v.reglages)

    def suivre_claude(self):
        """Réglage « Collé à droite (ou à gauche) de Claude » : le panneau se colle au bord de la fenêtre de Claude,
        à sa hauteur, et la suit quand elle bouge, comme une barre latérale. S'il n'y a pas la place de ce côté de
        l'écran, il passe de l'autre ; si Claude est agrandie (plein écran), il reste où il est."""
        sens = self.v.reglages.get("ancrer_claude", "non")
        try:
            if sens != "non" and self.racine.state() == "normal":
                h = user32.FindWindowW("Chrome_WidgetWin_1", "Claude")
                if h and user32.IsWindowVisible(h) and not user32.IsIconic(h) and not user32.IsZoomed(h):
                    L, T, R, B = cadre_visible(h)
                    moi = user32.GetParent(self.racine.winfo_id())
                    vl, vt, vr, vb = cadre_visible(moi)                  # ce qu'on voit du panneau
                    rr = W.RECT()
                    user32.GetWindowRect(W.HWND(moi), ctypes.byref(rr))  # avec ses bordures invisibles
                    g, d, hh, bb = vl - rr.left, rr.right - vr, vt - rr.top, rr.bottom - vb
                    lg = vr - vl
                    ecran = ecran_de(self.v.ecrans, (L + R) // 2, (T + B) // 2)
                    xs = [R, L - lg] if sens == "droite" else [L - lg, R]
                    x = next((x for x in xs if not ecran or (x >= ecran["travail"][0] and x + lg <= ecran["travail"][2])), None)
                    if x is not None:
                        cible = (x - g, T - hh, lg + g + d, (B - T) + hh + bb)
                        if cible != self.dernier_ancrage:
                            user32.SetWindowPos(W.HWND(moi), None, *cible, SWP_NOZORDER | SWP_NOACTIVATE)
                            self.dernier_ancrage = cible
            else:
                self.dernier_ancrage = None
        except Exception as ex:
            log.warning("panneau collé à Claude : %s", ex)
        self.racine.after(300, self.suivre_claude)

    def rafraichir(self):
        v = self.v
        if not hasattr(v, "etats"):
            return                  # au tout début, le panneau se met en page avant que la volée soit prête
        etats = [e for e in v.etats.values() if e.get("eff")]
        meres = [e for e in etats if not e["parent"]]
        a_faire = sorted((e for e in meres if e["eff"] in ("montre", "appel", "attend", "pause")),
                         key=lambda e: (RANG_IMPORTANCE.get(e.get("importance"), 2), e["depuis"]))
        repos = [e for e in meres if e["eff"] == "repos"]
        travail = [e for e in meres if e not in a_faire and e not in repos]
        enfants = {m["ident"]: sum(1 for e in etats if e["parent"] == m["ident"]) for m in meres}
        n_attente = sum(1 for e in a_faire if e["eff"] != "pause")
        if LANGUE == "en":
            resume = f"{len(meres)} session{'s' if len(meres) > 1 else ''} · {n_attente} waiting"
        else:
            resume = (f"{len(meres)} session{'s' if len(meres) > 1 else ''} · "
                      f"{n_attente} t'attend{'ent' if n_attente > 1 else ''}")
        self.resume.config(text=resume + (tr(" · guides masqués") if v.masques else ""))
        self.aide.config(text=tr("Ctrl+Alt+P est déjà pris par un autre programme") if v.raccourci.ok is False
                         else tr("Ctrl+Alt+P : prochaine action · Ctrl+Alt+T : c'est fait ou terminer"))
        self.b_masquer.config(text=tr("Montrer les guides") if v.masques else tr("Masquer les guides"))
        tous_en_pause = a_faire and all(e["eff"] == "pause" for e in a_faire)
        self.b_pause.config(text=tr("Tout reprendre") if tous_en_pause else tr("Tout en pause"))
        maintenant = time.time()
        if self.onglet == "guide":
            if self.signature != "guide":           # le guide se fait une fois (et à chaque changement de largeur)
                self.signature = "guide"
                self.montrer_guide()
            return
        # « Session terminée · Annuler » : 5 s en haut du panneau.
        annulable = getattr(v, "annulable", None)
        annulable = annulable if annulable and maintenant - annulable[2] < 5 else None
        conflits = list(getattr(v.guetteur, "conflits", []))[:3]
        livrables = list(getattr(v.guetteur, "livrables", []))
        signature = (annulable and annulable[0], tuple((f, tuple(q)) for f, q in conflits),
                     tuple((l["ident"], tuple(x["valeur"] for x in l["sorties"])) for l in livrables),
                     tuple((e["ident"], e["eff"], e["titre"], court(e["bulle"], 90), e["couleur"], e.get("importance"),
                            v.couleur_guide(e), int((maintenant - e["depuis"]) // 60) if e["depuis"] else 0,
                            int(((v.en_pause.get(e["ident"]) or maintenant) - maintenant) // 60),
                            tuple(x["valeur"] for x in (e.get("sorties") or []))) for e in a_faire),
                     tuple((e["ident"], e["titre"], e["libelle"], min(5, e["rythme"] // 6), enfants[e["ident"]],
                            e["couleur"], int((maintenant - e["tour_depuis"]) // 60) if e.get("tour_depuis") else 0,
                            (e.get("contexte") or 0) // 10000, tuple(e.get("meme_dossier") or ()), bool(e.get("chemin")))
                           for e in travail),
                     tuple((e["ident"], e["titre"]) for e in repos))
        if signature == self.signature:
            return
        self.signature = signature
        for w in self.corps.winfo_children():
            w.destroy()
        tk = self.tk
        if annulable:
            bandeau = tk.Frame(self.corps, bg=self.BOUTON)
            bandeau.pack(fill="x", padx=4, pady=(4, 0))
            tk.Label(bandeau, text=tr("« {t} » terminée", t=annulable[1][:40]), bg=self.BOUTON, fg=self.TEXTE,
                     font=("Segoe UI", 9), anchor="w").pack(side="left", padx=10, pady=4)
            b = self.bouton(bandeau, "Annuler", v.annuler_fermeture, petit=True, cote="right")
            b.pack_configure(padx=8)
        for fichier, qui in conflits:
            # Deux IA écrivent le même fichier (la coordination, 3 octobre) : un bandeau, rien à l'écran.
            tk.Label(self.corps, text=tr("⚠ Conflit possible : « {a} » et « {b} » écrivent dans {f}",
                                         a=court(qui[0], 26), b=court(qui[1], 26), f=os.path.basename(fichier)),
                     bg=self.BOUTON, fg=v.reglages["couleur_normale"], font=("Segoe UI", 9), anchor="w", justify="left",
                     wraplength=max(240, self.largeur - 40)).pack(fill="x", padx=4, pady=(4, 0), ipady=3)
        self.titre_section("À faire pour toi", len(a_faire))
        if not a_faire:
            tk.Label(self.corps, text=tr("Rien ne t'attend. Les pigeons veillent."), bg=self.FOND, fg=self.PALE,
                     font=("Segoe UI", 9, "italic"), anchor="w").pack(fill="x", padx=6, pady=(0, 6))
        for e in a_faire:
            self.carte(e)
        if livrables:
            self.titre_section("Livrables des sessions finies", len(livrables))
            for l in livrables:
                self.carte_livrables(l)
        if travail:
            self.titre_section("Au travail", len(travail))
            for e in travail:
                self.ligne(e, enfants[e["ident"]])
        if repos:
            self.titre_section("Au repos", len(repos))
            for e in repos:
                self.ligne(e, enfants[e["ident"]], terne=True)

    def titre_section(self, texte, n):
        self.tk.Label(self.corps, text=f"{tr(texte).upper()}  {n}", bg=self.FOND, fg=self.ACCENT,
                      font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x", padx=6, pady=(10, 4))

    def carte(self, e):
        """Une session qui t'attend : sa couleur à gauche, son nom, ce qu'elle veut, ses boutons."""
        tk, v, i = self.tk, self.v, e["ident"]
        c = tk.Frame(self.corps, bg=self.CARTE)
        c.pack(fill="x", padx=4, pady=3)
        tk.Frame(c, bg=e["couleur"] or "#888888", width=4).pack(side="left", fill="y")
        texte = tk.Frame(c, bg=self.CARTE)
        texte.pack(side="left", fill="x", expand=True, padx=10, pady=6)
        etat = tr({"montre": "te montre où aller", "appel": "t'attend", "attend": "t'attend", "pause": "en pause"}[e["eff"]])
        maintenant = time.time()
        if e["eff"] == "pause" and v.en_pause.get(i):
            etat = tr("en pause encore ") + duree_lisible(v.en_pause[i] - maintenant)
        if e["depuis"]:
            etat += " · " + depuis_lisible(maintenant - e["depuis"])
        haut = tk.Frame(texte, bg=self.CARTE)
        haut.pack(fill="x")
        tk.Label(haut, text=e["titre"][:46], bg=self.CARTE, fg=self.TEXTE, font=("Segoe UI Semibold", 10),
                 anchor="w").pack(side="left")
        if e.get("importance") in IMPORTANCES:
            # Le badge d'importance, de la couleur choisie dans les réglages (rouge, ambre, bleu par défaut).
            tk.Label(haut, text=tr(IMPORTANCES[e["importance"]]), bg=self.CARTE,
                     fg=v.reglages["couleur_" + e["importance"]], font=("Segoe UI Semibold", 8)).pack(side="left", padx=8)
        for item in (e.get("sorties") or [])[:5]:
            self.sortie(texte, item)
        if e["mode"] == "montre":
            self.actions_contextuelles(texte, e.get("demande"))
        tk.Label(texte, text=f"{etat} · {court(e['bulle'], 110) or '…'}", bg=self.CARTE, fg=self.PALE,
                 font=("Segoe UI", 9), anchor="w", justify="left", wraplength=max(220, self.largeur - 60)).pack(fill="x")
        # Les boutons sous le texte, sur toute la largeur : à droite du texte, ils débordaient d'un panneau étroit
        # (vu le 2 octobre à 13h26, « Terminer » coupé). « Terminer » à part, au bout de la ligne.
        boutons = tk.Frame(texte, bg=self.CARTE)
        boutons.pack(fill="x", pady=(5, 0))
        if e["mode"] != "montre":
            self.bouton(boutons, "Aller", lambda: v.aller_a_la_session(i), petit=True,
                        aide="Ouvre cette session dans l'app Claude.")
        if e["eff"] == "pause":
            self.bouton(boutons, "Reprendre", lambda: v.guider_session(i), petit=True,
                        aide="Reprend le guidage mis en pause.")
        else:
            self.bouton(boutons, "Guider", lambda: v.guider_session(i), petit=True,
                        aide="La ligne et le pigeon te montrent le chemin jusqu'à elle.")
            if e["eff"] == "montre":
                self.bouton(boutons, "C'est fait", lambda: v.fini(i), petit=True,
                            aide="Le geste demandé est fait : la demande s'en va.")
            self.plus_tard(boutons, i)
        # Sur chaque carte : la session est finie, elle s'en va (elle revient si on lui écrit).
        self.bouton(boutons, "Terminer", lambda: v.terminer(i), petit=True, cote="right",
                    aide="La session est finie : sa carte, sa ligne et son pigeon s'en vont. Elle revient si tu lui écris.")

    def carte_livrables(self, l):
        """Ce qu'une session terminée a laissé (sa dernière réponse) : ses liens, ses fichiers et ses blocs, avec Copier,
        Ouvrir, Montrer ; « Oublier » les retire du panneau. Ni pigeon, ni ligne, ni guidage : la session est finie."""
        tk, v = self.tk, self.v
        c = tk.Frame(self.corps, bg=self.CARTE)
        c.pack(fill="x", padx=4, pady=3)
        tk.Frame(c, bg=l["couleur"] or "#888888", width=4).pack(side="left", fill="y")
        texte = tk.Frame(c, bg=self.CARTE)
        texte.pack(side="left", fill="x", expand=True, padx=10, pady=6)
        haut = tk.Frame(texte, bg=self.CARTE)
        haut.pack(fill="x")
        tk.Label(haut, text=l["titre"][:40], bg=self.CARTE, fg=self.TEXTE, font=("Segoe UI Semibold", 10),
                 anchor="w").pack(side="left")
        tk.Label(haut, text=tr("terminée ") + depuis_lisible(time.time() - l["fermee"]), bg=self.CARTE, fg=self.PALE,
                 font=("Segoe UI", 8)).pack(side="left", padx=8)
        self.bouton(haut, "Oublier", lambda i=l["ident"]: v.oublier_livrables(i), petit=True, cote="right",
                    aide="Ces livrables s'en vont du panneau (la session reste terminée).")
        for item in l["sorties"][:6]:
            self.sortie(texte, item)

    def sortie(self, parent, item):
        """Un lien, un fichier ou un bloc de texte cité par la session : son nom, et Copier, Ouvrir, Montrer (dans
        l'Explorateur). Copier met l'adresse, le chemin complet ou le texte entier du bloc dans le presse-papiers,
        d'un clic de l'utilisateur ; un bloc n'a que Copier."""
        tk = self.tk
        l = tk.Frame(parent, bg=self.CARTE)
        l.pack(fill="x", pady=(2, 0))
        if item["genre"] == "invite":
            dossier = item.get("dossier")
            item = {**item, "nom": os.path.basename(dossier.rstrip("\\/")) if dossier else item["nom"]}
            icone = tr("nouvelle séance")
        elif item["genre"] == "texte":
            icone = tr("texte")
        else:
            icone = tr("lien" if item["genre"] == "lien" else ("dossier" if os.path.isdir(item["valeur"]) else "fichier"))
        tk.Label(l, text=f"{icone} · {court(item['nom'], 38)}", bg=self.CARTE, fg=self.ACCENT, font=("Segoe UI", 8),
                 anchor="w").pack(side="left")

        def copier(valeur=item["valeur"]):
            self.racine.clipboard_clear()
            self.racine.clipboard_append(valeur)
            self.v.infos["__copie__"] = time.time()
            log.info("copié dans le presse-papiers : %s", valeur[:80])

        def ouvrir(valeur=item["valeur"]):
            try:
                os.startfile(valeur)
            except OSError as ex:
                log.warning("ouvrir %s : %s", valeur, ex)

        def montrer(valeur=item["valeur"]):
            import subprocess
            subprocess.Popen(["explorer", "/select,", valeur])

        if item["genre"] == "invite":
            self.bouton(l, "Nouvelle séance", lambda it=item: self.v.nouvelle_seance(it), petit=True, cote="right",
                        aide="Copie l'invite et ouvre une nouvelle session dans son dossier, dans l'app Claude : il reste à coller (Ctrl+V).")
            self.bouton(l, "Copier", copier, petit=True, cote="right", aide="Copie le texte du bloc (un prompt, une commande).")
            return
        if item["genre"] == "texte":
            self.bouton(l, "Copier", copier, petit=True, cote="right", aide="Copie le texte du bloc (un prompt, une commande).")
            return
        if item["genre"] == "fichier":
            self.bouton(l, "Montrer", montrer, petit=True, cote="right", aide="Montre le fichier dans l'Explorateur.")
        self.bouton(l, "Ouvrir", ouvrir, petit=True, cote="right", aide="Ouvre le lien ou le fichier.")
        self.bouton(l, "Copier", copier, petit=True, cote="right", aide="Copie l'adresse ou le chemin complet.")

    def actions_contextuelles(self, parent, demande):
        """L'aide active (l'utilisateur, 3 octobre : « si j'ai besoin d'aller dans un dossier, un bouton apparaît : aller
        directement dans le dossier ») : selon ce que la session demande, un bouton fait le chemin à ta place.
        Un dossier ou un fichier : l'ouvrir, ou le montrer dans l'Explorateur ; une fenêtre : l'amener devant."""
        import subprocess
        tk = self.tk
        for cle in ("cible", "puis", "vers"):
            c = (demande or {}).get(cle)
            if not isinstance(c, dict):
                continue
            ligne = tk.Frame(parent, bg=self.CARTE)
            if c.get("fichier") and os.path.exists(c["fichier"]):
                chemin = c["fichier"]
                dossier = os.path.isdir(chemin)
                ligne.pack(fill="x", pady=(2, 0))
                nom = os.path.basename(chemin.rstrip("\\/")) or chemin
                tk.Label(ligne, text=f"{tr('dossier' if dossier else 'fichier')} · {court(nom, 36)}", bg=self.CARTE,
                         fg=self.ACCENT, font=("Segoe UI", 8), anchor="w").pack(side="left")
                self.bouton(ligne, "Montrer", lambda p=chemin: subprocess.Popen(["explorer", "/select,", p]), petit=True,
                            cote="right", aide="Montre l'endroit dans l'Explorateur.")
                self.bouton(ligne, "Ouvrir le dossier" if dossier else "Ouvrir le fichier",
                            lambda p=chemin: os.startfile(p), petit=True, cote="right",
                            aide="Ouvre le dossier tout de suite, sans le chercher." if dossier
                            else "Ouvre le fichier avec son programme.")
            elif c.get("fenetre"):
                ligne.pack(fill="x", pady=(2, 0))
                tk.Label(ligne, text=f"{tr('fenêtre')} · {court(c['fenetre'], 36)}", bg=self.CARTE, fg=self.ACCENT,
                         font=("Segoe UI", 8), anchor="w").pack(side="left")
                self.bouton(ligne, "Amener devant", lambda t=c["fenetre"]: self.v.amener_fenetre(t), petit=True,
                            cote="right", aide="Ramène cette fenêtre devant les autres.")

    def plus_tard(self, parent, i):
        """« Plus tard ▾ » : 5 min, 15 min, 1 h ou sans limite ; le pigeon revient seul à la fin du report."""
        tk, v = self.tk, self.v
        b = tk.Menubutton(parent, text=tr("Plus tard ▾"), relief="flat", bd=0, cursor="hand2", bg=self.BOUTON,
                          fg=self.TEXTE, activebackground=self.BOUTON_ACTIF, activeforeground=self.ACTIF_TEXTE,
                          font=("Segoe UI", 8), padx=8, pady=1)
        menu = tk.Menu(b, tearoff=0, bg=self.CARTE, fg=self.TEXTE, activebackground=self.BOUTON_ACTIF,
                       activeforeground=self.ACTIF_TEXTE)
        for texte, minutes in (("Dans 5 min", 5), ("Dans 15 min", 15), ("Dans 1 h", 60), ("Sans limite", None)):
            menu.add_command(label=tr(texte), command=lambda m=minutes: v.mettre_en_pause(i, m))
        b.config(menu=menu)
        b.pack(side="left", padx=3)
        Infobulle(b, "Le pigeon attend sur la barre des tâches, puis revient seul.")

    def ligne(self, e, n_enfants, terne=False):
        """Une session au travail : un point de sa couleur, son nom, ce qu'elle touche, son rythme, ses pigeonneaux."""
        tk = self.tk
        l = tk.Frame(self.corps, bg=self.FOND)
        l.pack(fill="x", padx=6, pady=1)
        point = tk.Canvas(l, width=10, height=10, bg=self.FOND, highlightthickness=0)
        point.create_oval(1, 1, 9, 9, fill=self.TERNE if terne else (e["couleur"] or "#888888"), outline="")
        point.pack(side="left", padx=(0, 8))
        tk.Label(l, text=e["titre"][:26], bg=self.FOND, fg=self.PALE if terne else self.TEXTE,
                 font=("Segoe UI", 9), anchor="w", width=22).pack(side="left")
        if not terne:
            # Le rythme : 0 à 5 petites barres (un outil par tranche de 6 dans la dernière minute).
            rythme = tk.Canvas(l, width=34, height=10, bg=self.FOND, highlightthickness=0)
            for k in range(5):
                plein = k < min(5, e["rythme"] // 6 + (1 if e["rythme"] else 0))
                rythme.create_rectangle(k * 7, 2, k * 7 + 5, 9, outline="",
                                        fill=(e["couleur"] or "#888888") if plein else "#2b2e36")
            rythme.pack(side="left", padx=(0, 8))
        # L'aide active : « Dossier » ouvre l'endroit où la session travaille, le fichier sélectionné (posé avant le
        # texte, pour qu'il reste visible quand le panneau est étroit).
        if not terne and e.get("chemin") and os.path.exists(e["chemin"]):
            import subprocess
            self.bouton(l, "Dossier", lambda p=e["chemin"]: subprocess.Popen(["explorer", "/select,", p]), petit=True,
                        cote="right", aide="Ouvre le dossier où elle travaille, le fichier sélectionné.")
        libelle = e["libelle"]
        if not self.v.reglages["afficher_pigeons"]:
            libelle = re.sub(r" \([^()]*\)$", "", libelle)     # « (caché, perché sur la fenêtre) » parle du pigeon
        detail = court(libelle, 46) + (f" · {n_enfants} {tr('pigeonneaux' if n_enfants > 1 else 'pigeonneau')}"
                                            if n_enfants else "")
        # Les repères du travail avec l'IA : la durée du tour, la taille du contexte. À droite,
        # à côté du bouton : ils restent visibles ; c'est le détail du fichier qui se coupe si la place manque (vu le
        # 3 octobre à 08h53, « contexte » coupé en bout de ligne).
        reperes = []
        if not terne and e.get("tour_depuis"):
            reperes.append(duree_lisible(time.time() - e["tour_depuis"]))
        if e.get("contexte"):
            reperes.append(tr("{k} k jetons", k=e["contexte"] // 1000))
        if reperes:
            tk.Label(l, text=" · ".join(reperes), bg=self.FOND, fg=self.PALE, font=("Segoe UI", 8)).pack(side="right",
                                                                                                         padx=(6, 2))
        tk.Label(l, text=detail, bg=self.FOND, fg=self.PALE, font=("Segoe UI", 8), anchor="w").pack(side="left", fill="x")
        if not terne and e.get("meme_dossier"):
            tk.Label(self.corps, text=tr("⚠ même dossier que « {t} » : attention aux conflits",
                                         t=court(e["meme_dossier"][0], 30)),
                     bg=self.FOND, fg=self.v.reglages["couleur_normale"], font=("Segoe UI", 8),
                     anchor="w").pack(fill="x", padx=(24, 6))


class Volee:
    """Fait voler et picosser les pigeons, 30 images par seconde ; tient le petit panneau de contrôle.

    Ce que l'utilisateur peut faire avec la souris (2 octobre, 10h30) :
    - cliquer l'endroit montré : la demande est faite, le pigeon dit merci et repart ;
    - cliquer un pigeon qui montre ou qui l'appelle : il va attendre sur la barre des tâches (en pause) ;
    - recliquer un pigeon en pause ou qui attend : le guidage reprend."""

    def __init__(self):
        import tkinter as tk
        self.tk = tk
        self.ecrans = lire_ecrans()
        self.ecran_parc = next((e for e in self.ecrans if e["principal"]), self.ecrans[0])
        self.partage, self.verrou = {}, threading.Lock()
        self.racine = tk.Tk()
        # Une erreur dans un rappel de Tk va au journal (sous pythonw, Tk l'écrirait dans une sortie qui n'existe pas).
        self.racine.report_callback_exception = lambda *e: log.error("rappel de Tk", exc_info=e)
        self.reglages = charger_reglages()
        self._palette = palette(self.reglages)
        Panneau.appliquer_palette(self._palette)
        global LANGUE
        LANGUE = self.reglages["langue"]
        self.masques = False        # le bouton « Masquer les pigeons »
        self.lignes, self.lignes_cle, self.lignes_t, self.voiles = [], None, 0.0, []
        self.panneau = Panneau(self)
        self.guide = Guide(self.racine)
        self.petits_guides = {}     # ident -> PetitGuide : une petite flèche par session qui attend
        self.cadres_reponse = {}    # ident -> Cadre autour de la ligne de la session qui attend
        self.etiquettes = {}        # ident -> Bulle à côté de cet encadré (réglage « infos à l'écran »)
        self.etiquettes_lien = {}   # ident -> [Bulle] : « 1 · prends ceci », « 2 · dépose ici » (deux cibles liées)
        self.cadres_travail = {}    # ident -> Cadre autour du fichier exact où travaille la session
        self.cadres_seuls = {}      # ident -> (Cadre, Bulle) : où elle travaille, quand les pigeons sont cachés
        self.balises = {}           # (ident, "a" ou "b") -> Balise : où est exactement la cible (5 octobre 2026)
        self.trous = []             # les places des balises : les points des lignes s'arrêtent là
        self.guetteur = Guetteur(self.partage, self.verrou, self.ecrans)
        self.guetteur.start()
        self.oiseaux, self.bulles, self.fleches = {}, {}, {}   # ident -> Oiseau, Bulle, (Fleche, Fleche|None)
        self.pos = {}           # ident -> [x, y] : où le pigeon est en ce moment
        self.ancres = {}        # ident -> (x, y) : où le pigeon s'est posé près de la souris
        self.etats = {}         # ident -> le dernier état reçu du guetteur
        self.en_pause = {}      # ident -> heure de fin de la pause (None : sans limite)
        self.etapes = {}        # ident -> 2 quand l'étape 1 d'une demande en deux étapes est faite
        self.cycle = (0.0, -1)  # le raccourci « prochaine action » : (heure du dernier appui, rang montré)
        self._uia = None        # l'automatisation de Windows du fil de l'affichage (« Aller à la session »)
        import queue
        self.file_clavier = queue.Queue()
        self.raccourci = Raccourci(self.file_clavier)
        self.raccourci.start()
        self.rappels = {}       # ident -> heure où l'utilisateur a recliqué un pigeon qui attendait
        self.merci = {}         # ident -> heure où l'utilisateur a fait le geste demandé
        self.infos = {}         # ident -> heure jusqu'à laquelle la bulle reste ouverte après un clic
        self.fermees_recentes = {}  # ident -> heure de « Terminer » (cachée tout de suite, sans attendre le guetteur)
        self.annulable = None   # (ident, titre, heure) : la dernière fermeture, qu'on peut annuler 5 s
        self.lignes_nees = {}   # une ligne -> l'heure où elle est apparue (pour la dessiner en 250 ms)
        self.lignes_tracees = set()  # les lignes déjà dessinées en entier au moins une fois
        self.bouton_avant = False
        self.appui_sur_a = set()
        self.t_prec = time.time()
        self.t_relance_guetteur = 0.0
        self.t_battement = 0.0
        ARRET.unlink(missing_ok=True)       # lancés : l'utilisateur (ou une relance sûre) les veut en marche
        Vigie(self).start()
        self.racine.after(33, self.image)
        self.racine.after(1000, self.rafraichir_panneau)
        self.racine.after(10000, self.veiller_guetteur)

    def parc(self, i, sous_agent):
        """Les places DANS la barre des tâches, sous la fenêtre de Claude, dans son espace vide (trouver_parc) :
        les pigeons s'y rangent côte à côte, 30 px chacun, les pigeonneaux un peu décalés."""
        info = self.guetteur.parc_info
        if not info:
            l, t, r, b = self.ecran_parc["travail"]
            return r - 420 - i * 40, b
        x = min(info["x0"] + i * 30 + (12 if sous_agent else 0), info["x1"])
        return x, info["pattes"]

    def garder_devant(self):
        """La barre des tâches passe devant tout quand on la clique : on remet les pigeons et leurs bulles
        au premier plan chaque seconde, sans leur donner le focus."""
        for o in list(self.oiseaux.values()) + [b for b in self.bulles.values() if b.contenu is not None]:
            user32.SetWindowPos(W.HWND(o.hwnd), W.HWND(-1), 0, 0, 0, 0, SWP_NOSIZE | 0x2 | SWP_NOACTIVATE)

    def curseur(self):
        pt = W.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def ancre(self, ident, cx, cy, rang):
        """Le pigeon qui t'appelle se pose près de la souris et y reste : il ne la fuit plus.
        Il ne se recale que si la souris s'éloigne de plus de APPEL_RECALE_PX."""
        a = self.ancres.get(ident)
        if a is None or math.hypot(cx - a[0], cy - a[1]) > APPEL_RECALE_PX:
            a = (cx + 60 + rang * 40, cy - 10)
            self.ancres[ident] = a
        return a

    # -- les clics de l'utilisateur
    def clic_pigeon(self, ident):
        e = self.etats.get(ident)
        if not e:
            return
        maintenant = time.time()
        if ident in self.en_pause:                      # reprendre le guidage
            self.en_pause.pop(ident, None)
            self.ancres.pop(ident, None)
            if e["mode"] == "attend":
                self.rappels[ident] = maintenant
        elif e.get("eff") in ("montre", "appel"):
            # « pas maintenant » : il va attendre en bas, pour la durée réglée (15 min par défaut)
            self.mettre_en_pause(ident, self.reglages["report_clic_min"] or None)
        elif e["mode"] == "attend":
            self.rappels[ident] = maintenant            # il revient près de la souris, sa bulle ouverte
        else:
            self.infos[ident] = maintenant + 4          # un pigeon au travail : sa bulle 4 s

    def fini(self, ident):
        """l'utilisateur a fait le geste : on range la demande, le pigeon dit merci."""
        try:
            (DEMANDES / f"{ident}.json").unlink()
        except OSError:
            pass
        self.merci[ident] = time.time()
        self.en_pause.pop(ident, None)
        self.etapes.pop(ident, None)
        log.info("geste fait pour %s", ident)

    def terminer(self, ident):
        """« Terminer » (l'utilisateur, 13h02 : la session était finie, mais sa ligne et son encadré restaient) : la session
        sort des cartes, des lignes et des encadrés, et son pigeon s'en va. C'est retenu dans
        fermetures\\<session>.json, pour survivre à une relance ; elle revient seule si l'utilisateur lui écrit ou si elle
        se remet au travail (Session.est_fermee). « Annuler » reste 5 s en haut du panneau."""
        maintenant = time.time()
        f = FERMETURES / f"{ident}.json"
        try:
            FERMETURES.mkdir(exist_ok=True)
            provisoire = f.with_suffix(".tmp")
            provisoire.write_text(json.dumps({"session": ident, "heure": maintenant, "par": "danny"}), encoding="utf-8")
            os.replace(provisoire, f)               # le guetteur ne lit jamais un fichier à moitié écrit
        except OSError as ex:
            log.warning("terminer %s : %s", ident, ex)
            return
        for dossier in (DEMANDES, SIGNAUX):
            (dossier / f"{ident}.json").unlink(missing_ok=True)
        for d in (self.en_pause, self.etapes, self.rappels, self.ancres, self.merci):
            d.pop(ident, None)
        self.fermees_recentes[ident] = maintenant
        e = self.etats.get(ident)
        self.annulable = (ident, e["titre"] if e else ident[:8], maintenant)
        self.panneau.signature = None               # le bandeau « Annuler » tout de suite
        log.info("session terminée par l'utilisateur : %s", e["titre"] if e else ident)

    def oublier_livrables(self, ident):
        """« Oublier » sur les livrables d'une session terminée : ils quittent le panneau. Retenu dans sa fermeture
        (fermetures\\<session>.json), pour survivre à une relance ; la session, elle, reste terminée."""
        f = FERMETURES / f"{ident}.json"
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            d["livrables_vus"] = True
            provisoire = f.with_suffix(".tmp")
            provisoire.write_text(json.dumps(d), encoding="utf-8")
            os.replace(provisoire, f)               # jamais un fichier à moitié écrit
        except (OSError, ValueError) as ex:
            log.warning("oublier les livrables de %s : %s", ident, ex)
            return
        self.guetteur.livrables = [l for l in self.guetteur.livrables if l["ident"] != ident]
        self.panneau.signature = None
        log.info("livrables oubliés : %s", ident)

    def annuler_fermeture(self):
        """« Annuler » : la session revient comme avant."""
        if not self.annulable:
            return
        ident = self.annulable[0]
        (FERMETURES / f"{ident}.json").unlink(missing_ok=True)
        self.fermees_recentes.pop(ident, None)
        self.annulable = None
        self.panneau.signature = None
        log.info("fermeture annulée : %s", ident)

    def terminer_premiere(self):
        """Ctrl+Alt+T : la première chose à faire (la même que Ctrl+Alt+P). Une demande de montre.py : c'est
        fait ; une session qui t'attend : terminée."""
        a_faire = [e for e in self.etats.values() if not e["parent"] and e.get("eff") in ("montre", "appel", "attend")]
        if not a_faire:
            return
        e = min(a_faire, key=lambda e: (RANG_IMPORTANCE.get(e.get("importance"), 3), e["depuis"]))
        if e["mode"] == "montre":
            self.fini(e["ident"])
        else:
            self.terminer(e["ident"])

    def guetter_clic(self, cx, cy, etats_eff):
        """Un appui (ou un relâchement, pour un glisser) sur l'endroit montré veut dire « c'est fait »."""
        appuye = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        if appuye == self.bouton_avant:
            return
        self.bouton_avant = appuye
        if any(o.contient(cx, cy) for o in self.oiseaux.values()):
            return                                      # un clic sur un pigeon n'est pas le geste demandé
        for e in etats_eff:
            if e["eff"] != "montre" or not e["cible"] or e.get("provisoire"):
                continue
            ou = (e.get("ou_puis") if e.get("etape") == 2 else e.get("ou")) or {}
            if appuye and dans_zone(cx, cy, e.get("zone"), e["cible"]):
                if e["vers"]:
                    self.appui_sur_a.add(e["ident"])
                elif e.get("etape") == 1:
                    self.etapes[e["ident"]] = 2         # l'étape 1 est faite : on guide vers l'étape 2
                    log.info("étape 1 faite pour %s", e["ident"])
                elif ou.get("etape1"):
                    # Une étape d'avant (la fenêtre réduite ou derrière, l'onglet caché, l'icône couverte) : ce clic
                    # n'est pas le geste demandé. Le guetteur resitue la cible au tour suivant et guide vers la vraie
                    # (démo du 6 octobre 2026, 08h18 : le clic sur Chrome dans la barre des tâches fermait la demande).
                    log.info("étape d'avant faite pour %s : %s", e["ident"], ou["etape1"])
                else:
                    self.fini(e["ident"])
            elif not appuye and e["ident"] in self.appui_sur_a and dans_zone(cx, cy, e.get("zone_vers"), e["vers"], 50):
                self.fini(e["ident"])
        if not appuye:
            self.appui_sur_a.clear()

    # -- chaque image
    def mode_effectif(self, e, maintenant):
        """Le mode du guetteur, corrigé par ce que l'utilisateur a fait à la souris (pause, rappel, merci)."""
        ident, mode = e["ident"], e["mode"]
        if mode not in ("montre", "appel", "attend"):
            self.en_pause.pop(ident, None)
            self.rappels.pop(ident, None)
        if maintenant - self.merci.get(ident, 0) < 2.5:
            return "merci"
        if ident in self.en_pause:
            fin = self.en_pause[ident]
            if fin is not None and maintenant >= fin:
                self.en_pause.pop(ident, None)
                self.rappels[ident] = maintenant         # le report est fini : le pigeon revient près de la souris
            else:
                return "pause"
        duree = self.reglages["duree_appel_s"] if self.reglages["appel_souris"] else 0
        if mode == "appel" and maintenant - e["depuis"] >= duree:
            mode = "attend"                              # le réglage écourte (ou supprime) la visite près de la souris
        if mode == "attend" and maintenant - self.rappels.get(ident, 0) < max(duree, 10):
            return "appel"                               # l'utilisateur a recliqué le pigeon : il revient, même sans visite
        return mode

    def but(self, e, maintenant, cx, cy, rang_appel):
        """L'endroit où le pigeon doit aller, selon son mode."""
        sous, eff = e["parent"] is not None, e["eff"]
        if eff == "montre":
            a, b = e["cible"], e["vers"]
            if a and b:
                # Glisser de A vers B : le pigeon refait le trajet, 2 s à A, 2 s à B.
                p = a if (maintenant % 4.0) < 2.0 else b
                return p[0] + 24, p[1] + 4
            if a:
                # À gauche, en dehors de l'encadré : il ne cache ni le nom ni l'icône.
                z = zone_ou_carre(e.get("zone"), a)
                return z[0] - 16, z[3] + 2
            return self.ancre(e["ident"], cx, cy, rang_appel)
        if eff == "appel":
            return self.ancre(e["ident"], cx, cy, rang_appel)
        if eff == "merci" and e["ident"] in self.pos:
            return self.pos[e["ident"]]          # il reste là le temps de dire merci
        self.ancres.pop(e["ident"], None)
        if eff in ("attend", "repos", "parc", "pause") or (eff == "perche" and self.reglages["cible_cachee"] == "barre"):
            return self.parc(e["parc"], sous)
        return e["x"], e["y"]

    def image(self):
        maintenant = time.time()
        dt = min(0.1, maintenant - self.t_prec)
        self.t_prec = maintenant
        with self.verrou:
            etats = [dict(e) for e in self.partage.values()]
        # Une session que l'utilisateur vient de terminer disparaît tout de suite (le guetteur suit en moins d'une seconde).
        etats = [e for e in etats if maintenant - self.fermees_recentes.get(e["parent"] or e["ident"], 0) > 3]
        if not self.reglages["pigeonneaux"]:
            etats = [e for e in etats if not e["parent"]]
        cx, cy = self.curseur()
        for e in etats:
            e["eff"] = self.mode_effectif(e, maintenant)
            self.etape_courante(e)
            self.etats[e["ident"]] = e
        while not self.file_clavier.empty():
            touche = self.file_clavier.get_nowait()
            if touche == "prochaine":
                self.prochaine_action()
            elif touche == "terminer":
                self.terminer_premiere()
        self.lignes = []            # les pointillés à tracer cette image (réglage « lignes »)
        sessions_la = {e["ident"] for e in etats}
        self.montrer_ou_elles_travaillent(etats)   # avant le tri des pigeons : ces encadrés ne dépendent pas d'eux
        if self.masques:            # le bouton « Masquer les pigeons » du panneau
            etats = []
        elif not self.reglages["pigeons_au_travail"]:
            etats = [e for e in etats if e["eff"] in ("montre", "appel", "attend", "pause", "merci")]
        self.guetter_clic(cx, cy, etats)
        vivants, rang_appel = set(), 0
        montre_recente = None
        appel_recent = max((e for e in etats if e["eff"] == "appel"),
                           key=lambda e: max(e["depuis"], self.rappels.get(e["ident"], 0)), default=None)
        for e in sorted(etats, key=lambda e: e["parent"] is not None):
            ident, sous, eff = e["ident"], e["parent"] is not None, e["eff"]
            if eff == "perche" and self.reglages["cible_cachee"] == "cache":
                continue                                # sa cible est cachée : il se cache aussi (réglage)
            tx, ty = self.but(e, maintenant, cx, cy, rang_appel)
            if eff in ("appel", "montre"):
                rang_appel += 1
            vivants.add(ident)
            if ident in self.oiseaux and self.oiseaux[ident].taille != self.reglages["taille_pigeon"]:
                self.oiseaux.pop(ident).detruire()       # la taille a changé dans les réglages : on le refait
            if ident not in self.oiseaux:
                self.oiseaux[ident] = Oiseau(self.racine, sous, lambda i=ident: self.clic_pigeon(i),
                                             self.reglages["taille_pigeon"],
                                             None if sous else (lambda i=ident: self.terminer(i)))
                if ident not in self.bulles:
                    self.bulles[ident] = Bulle(self.racine)
                if ident not in self.pos:
                    self.pos[ident] = [tx, ty - 400]      # il arrive du ciel
            p = self.pos[ident]
            # Le vol ralentit à l'arrivée (une approche exponentielle) et monte en arc quand c'est loin.
            dx, dy = tx - p[0], ty - p[1]
            k = 1 - math.exp(-dt * 4.5)
            p[0] += dx * k
            p[1] += dy * k
            reste = math.hypot(dx, dy)
            arc = min(60.0, reste * 0.18)
            # Il picosse quand il est arrivé et que sa session travaille encore (1 à 4 coups par seconde).
            bec = 0.0
            if reste < 3 and eff in ("pose", "perche") and maintenant - e["dernier_geste"] < 10:
                f = 1 + min(3, e["rythme"] / 10)
                bec = abs(math.sin(maintenant * math.pi * f)) * 4
            if eff in ("appel", "montre") and reste < 6:
                bec = abs(math.sin(maintenant * math.pi * 2.5)) * 6      # il cogne à la vitre
            o = self.oiseaux[ident]
            anneau = None
            if eff in ("attend", "appel", "montre", "pause"):
                anneau = o.r + 5 + 2 * math.sin(maintenant * 2.2)
            couleur = "#7a7a7a" if eff == "repos" else (e["couleur"] or "#888888")
            visible = self.reglages["afficher_pigeons"]
            if visible:
                o.placer(p[0], p[1] - arc)
                o.dessiner(couleur, bec, anneau, pause=(eff == "pause"), couleur_anneau=self.couleur_guide(e))
            else:
                o.placer_coin(-3000, -3000)             # caché : seulement les lignes, les flèches et les encadrés
            # La bulle : toujours ouverte quand il montre, dit merci ou t'appelle (le plus récent) ; sinon au survol.
            survol = visible and math.hypot(cx - p[0], cy - (p[1] - arc - o.r)) < SURVOL_PX
            texte = None
            ligne = court((e["bulle"] or "").split("\n")[0], 48)
            debut_appel = max(e["depuis"], self.rappels.get(ident, 0))
            if not visible and eff not in ("montre", "merci"):
                texte = None                                   # sans pigeon, pas de bulle qui flotte sans attache
            elif eff == "merci":
                texte = tr("Merci !")
            elif survol and eff == "pause":
                texte = tr("{t} · en pause\n{b}\n(clique-moi pour reprendre)", t=e['titre'], b=e['bulle'])
            elif survol and eff in ("montre", "appel", "attend"):
                texte = tr("{t}\n{b}\n(clique-moi : plus tard)", t=e['titre'], b=e['bulle'])
            elif survol or self.infos.get(ident, 0) > maintenant:
                texte = f"{e['titre']}\n{e['bulle'] or e['libelle']}"
            elif self.reglages["bulles"] != "courte":
                texte = None                                   # réglage « seulement au survol »
            elif eff == "montre":
                # La consigne, en une ligne ; entière, avec l'étape et le raccourci, en « infos complètes ».
                texte = self.consigne_complete(e) if self.reglages["infos_ecran"] == "complet" else ligne
            elif eff == "appel" and appel_recent is not None and ident == appel_recent["ident"] \
                    and maintenant - debut_appel < 8:
                texte = ligne                                  # 8 s, puis seulement le pigeon et son anneau
            # Pas de bulle à côté de la cible, sauf si l'utilisateur la veut (le réglage « bulle_cible », 3 octobre 23h36 : elle
            # cachait trop souvent la cible et ses alentours) ; la consigne reste dans le panneau ; le survol d'un pigeon
            # affiché la montre encore.
            pres_cible = eff == "montre" and e["cible"] and (not e["vers"] or not visible)
            if texte and pres_cible and not survol and not self.reglages["bulle_cible"]:
                texte = None
            if texte:
                # À droite de l'encadré de la cible ; pour un glisser, à côté du pigeon s'il est affiché, sinon de A.
                zone = zone_ou_carre(e.get("zone"), e["cible"]) if pres_cible else None
                autres = [zone_ou_carre(e.get(cz), e[cp]) for cp, cz in (("puis", "zone_puis"), ("vers", "zone_vers"))
                          if eff == "montre" and e.get(cp)]
                self.bulles[ident].montrer(p[0], p[1] - arc, texte, couleur, self.ecrans, zone,
                                           self.reglages["opacite_bulles"], eviter=autres)
            else:
                self.bulles[ident].cacher()
            self.flecher(e, couleur, maintenant)
            self.montrer_travail(e, couleur, survol, (p[0], p[1] - arc - o.r))
            if eff == "montre" and e["cible"] and (montre_recente is None or e["depuis"] > montre_recente["depuis"]):
                montre_recente = e
        self.guider(montre_recente, cx, cy)
        self.guider_attente(etats, cx, cy, maintenant)   # avec la flèche d'une demande, s'il y en a une
        self.baliser(etats, cx, cy, maintenant)
        self.tracer_lignes(cx, cy, maintenant)
        for ident in list(self.oiseaux):
            if ident not in vivants:            # la session est partie (ou son pigeon est masqué)
                self.oiseaux.pop(ident).detruire()
                self.bulles.pop(ident).detruire()
                self.ranger_fleches(ident)
                c = self.cadres_travail.pop(ident, None)
                if c:
                    c.detruire()
                for d in (self.pos, self.ancres):
                    d.pop(ident, None)
                if ident not in sessions_la:    # partie pour de bon : on oublie aussi ce que l'utilisateur en avait fait
                    for d in (self.etats, self.rappels, self.merci, self.infos):
                        d.pop(ident, None)
                    self.en_pause.pop(ident, None)
        for ident in list(self.etats):
            if ident not in sessions_la:
                self.etats.pop(ident, None)
        if maintenant - self.t_battement > 2:
            # Le battement de l'affichage, pour montre.py et annonce.py : un fichier vieux de 30 s dit qu'il est figé.
            self.t_battement = maintenant
            try:
                AFFICHAGE.write_text(str(os.getpid()), encoding="utf-8")
            except OSError:
                pass
        self.racine.after(33, self.image)

    def arreter(self):
        """Le bouton « Arrêter » : un mot dans arret_volontaire.json (montre.py et annonce.py ne relancent pas des
        pigeons que l'utilisateur a arrêtés lui-même), puis la fin du programme."""
        try:
            ARRET.write_text(json.dumps({"heure": time.time(), "heure_lisible": datetime.now().strftime("%Y-%m-%d %H:%M")}),
                             encoding="utf-8")
            AFFICHAGE.unlink(missing_ok=True)
        except OSError:
            log.exception("mot d'arrêt")
        self.racine.destroy()

    def montrer_ou_elles_travaillent(self, etats):
        """Sans pigeons, où chaque IA travaille reste visible (l'utilisateur, 3 octobre, 18h3x : en cachant les pigeons vers 09h10,
        « on a pas gardé les cibles, les encadrés où les IA travaillent » ; son choix : « Encadré + nom de la session »).
        Un encadré pointillé de la couleur de la session autour du fichier ou du dossier qu'elle touche, s'il se voit à
        l'écran (« pose » : le Bureau, un Explorateur ouvert ; caché sous une fenêtre, rien, la règle de 12h54), et son nom
        dans une étiquette. Ni ligne ni pigeon. Les pigeons visibles, c'est montrer_travail qui s'en charge."""
        rg = self.reglages
        voulus = {}
        if not rg["afficher_pigeons"] and rg.get("encadres_travail", True) and not self.masques:
            voulus = {e["ident"]: e for e in etats if not e["parent"] and e["eff"] == "pose" and e.get("zone_travail")}
        for ident in list(self.cadres_seuls):
            if ident not in voulus:
                for x in self.cadres_seuls.pop(ident):
                    x.detruire()
        # Deux sessions au même endroit (l'utilisateur, 19h09:36 : « quand 2 sessions travaillent en même temps les noms se
        # chevauchent ») : les encadrés s'emboîtent (3 px de plus chacun) et chaque nom évite les noms déjà posés
        # (à droite, au-dessus, en dessous, puis à gauche : Bulle.montrer).
        par_zone, poses = {}, []
        for ident, e in sorted(voulus.items()):
            couleur = self.couleur_guide(e)
            cadre, etiquette = self.cadres_seuls.get(ident, (None, None))
            if cadre is None or cadre.couleur != couleur:
                if cadre:
                    cadre.detruire()
                    etiquette.detruire()
                cadre, etiquette = self.cadres_seuls[ident] = (Cadre(self.racine, couleur), Bulle(self.racine))
            zone = tuple(e["zone_travail"])
            rang = par_zone[zone] = par_zone.get(zone, -1) + 1
            cadre.entourer(zone, min(0, rg["encadres_marge"]) - 1 + 3 * rang, 1, "pointilles", None, rg["encadres_arrondi"])
            etiquette.montrer(zone[2], zone[1], court(e["titre"], 40), couleur, self.ecrans, zone, rg["opacite_bulles"],
                              eviter=poses)
            if etiquette.rect():
                poses.append(etiquette.rect())

    def montrer_travail(self, e, couleur, survol, depuis):
        """Le pigeon au travail : une ligne pointillée de lui jusqu'au fichier ou au sous-dossier exact où travaille
        sa session, et un encadré léger autour ; au survol du pigeon, ou toujours (réglage « lignes_travail »).
        l'utilisateur, 12h15
 : « faire apparaître l'emplacement du sous-dossier ou du fichier dans lesquels ils travaillent »."""
        ident, reglage = e["ident"], self.reglages["lignes_travail"]
        # Seulement si l'endroit se voit (« pose ») : caché sous une fenêtre, l'encadré et la ligne se dessinaient
        # par-dessus cette fenêtre (l'utilisateur, 12h54, son navigateur).
        voulu = (self.reglages["afficher_pigeons"] and e["eff"] == "pose" and e.get("travail")
                 and (reglage == "toujours" or (reglage == "survol" and survol)))
        if not voulu:
            c = self.cadres_travail.pop(ident, None)
            if c:
                c.detruire()
            return
        but = e["travail"]
        if math.hypot(but[0] - depuis[0], but[1] - depuis[1]) > 30:
            self.lignes.append((but[0], but[1], couleur, depuis, True))
        if e.get("zone_travail"):
            c = self.cadres_travail.get(ident)
            if c is None or c.couleur != couleur:
                if c:
                    c.detruire()
                c = self.cadres_travail[ident] = Cadre(self.racine, couleur)
            c.entourer(e["zone_travail"], min(0, self.reglages["encadres_marge"]) - 1, 1, "pointilles", None,
                       self.reglages["encadres_arrondi"])

    def couleur_guide(self, e):
        """La couleur des guides d'une tâche (anneau, flèches, lignes, encadrés) : celle de la tâche, ou celle
        de son importance si l'utilisateur a choisi le code d'importance dans les réglages."""
        if self.reglages["couleur_guides"] == "importance" and e.get("importance") in IMPORTANCES:
            return self.reglages["couleur_" + e["importance"]]
        return e.get("couleur") or "#888888"

    def flecher(self, e, couleur, maintenant):
        """Les flèches d'un pigeon qui montre : sur l'endroit (A) et, pour un glisser, l'anneau sur B."""
        ident = e["ident"]
        couleur = self.couleur_guide(e)
        if ident in self.fleches and self.fleches[ident][2].couleur != couleur:
            self.ranger_fleches(ident)          # la couleur a changé (réglage) : on refait les flèches
        if e["eff"] != "montre" or not e["cible"]:
            self.ranger_fleches(ident)
            return
        forme = (e["vers"] is None, e.get("puis") is None)
        if ident not in self.fleches or self.fleches[ident][5] != forme:
            self.ranger_fleches(ident)
            vers, puis = bool(e["vers"]), bool(e.get("puis"))
            self.fleches[ident] = (Fleche(self.racine, couleur), Fleche(self.racine, couleur, anneau=True) if vers else None,
                                   Cadre(self.racine, couleur), Cadre(self.racine, couleur) if vers else None,
                                   Cadre(self.racine, couleur) if puis else None, forme)
        saut = abs(math.sin(maintenant * math.pi * 1.4)) * 8
        fa, fb, ca, cb, cp, _forme = self.fleches[ident]
        self.etiqueter_lien(e, couleur)
        fa.pointer(*e["cible"], saut)
        rg = self.reglages
        cadrer = rg["encadres_montre"] and rg["encadres"] != "jamais"
        numero = e.get("etape") or (1 if e["vers"] else None)     # 1 et 2 : deux étapes, ou un glisser de A vers B
        if cadrer:
            ca.entourer(zone_ou_carre(e.get("zone"), e["cible"], 12), rg["encadres_marge"], rg["encadres_epaisseur"],
                        rg["encadres_style"], numero, rg["encadres_arrondi"], rond=e.get("zone") is None)
        else:
            ca.placer_coin(-3000, -3000); ca.rect = None
        if cp:
            if cadrer:
                cp.entourer(zone_ou_carre(e.get("zone_puis"), e["puis"], 12), rg["encadres_marge"], rg["encadres_epaisseur"],
                            rg["encadres_style"], 2, rg["encadres_arrondi"], rond=e.get("zone_puis") is None)
            else:
                cp.placer_coin(-3000, -3000); cp.rect = None
        if fb:
            fb.pointer(*e["vers"], 0)
            if cadrer:
                cb.entourer(zone_ou_carre(e.get("zone_vers"), e["vers"], 12), rg["encadres_marge"], rg["encadres_epaisseur"],
                            rg["encadres_style"], 2, rg["encadres_arrondi"], rond=e.get("zone_vers") is None)
            else:
                cb.placer_coin(-3000, -3000); cb.rect = None

    def etiqueter_lien(self, e, couleur):
        """Les étiquettes des deux cibles liées (infos à l'écran détaillées ou complètes) : un glisser dit « 1 · prends
        ceci » et « 2 · dépose ici » ; une demande en deux étapes montre déjà sa consigne près de l'étape 1, et dit la
        suivante près de l'étape 2."""
        ident, rg = e["ident"], self.reglages
        voulues = []
        if rg["infos_ecran"] != "discret" and e["eff"] == "montre" and e["cible"]:
            if e["vers"]:
                # Sans pigeon, la bulle de consigne est déjà à côté de A : seulement « 2 · dépose ici ».
                voulues = ([(zone_ou_carre(e.get("zone"), e["cible"]), tr("1 · prends ceci"))] if rg["afficher_pigeons"]
                           else []) + [(zone_ou_carre(e.get("zone_vers"), e["vers"]), tr("2 · dépose ici"))]
            elif e.get("puis"):
                voulues = [(zone_ou_carre(e.get("zone_puis"), e["puis"]),
                            "2 · " + court(e.get("texte_puis") or tr("ensuite ici"), 50))]
        bulles = self.etiquettes_lien.setdefault(ident, [])
        while len(bulles) > len(voulues):
            bulles.pop().detruire()
        while len(bulles) < len(voulues):
            bulles.append(Bulle(self.racine))
        cibles = [zone_ou_carre(e.get("zone"), e["cible"])] if e.get("cible") else []
        cibles += [zone_ou_carre(e.get(cz), e[cp]) for cp, cz in (("puis", "zone_puis"), ("vers", "zone_vers")) if e.get(cp)]
        bulle = self.bulles.get(ident)
        voisines = [bulle.rect()] if bulle else []
        for b, (zone, texte) in zip(bulles, voulues):
            b.montrer(zone[2], zone[1], texte, couleur, self.ecrans, zone, rg["opacite_bulles"],
                      eviter=[z for z in cibles if z != zone] + voisines)
            voisines.append(b.rect())
        if not bulles:
            self.etiquettes_lien.pop(ident, None)

    def contenu_balise(self, e, ou, etape, suite=False):
        """Ce que dit une balise : (morceaux, puces, numéro). Les morceaux font un fil d'Ariane, « [icône] Chrome ›
        onglet « Gemini » › bouton « Envoyer » » ; une étape d'avant (la fenêtre derrière, réduite, l'onglet caché) dit
        ce qu'il faut faire d'abord ; les puces disent ce qui couvre la cible (en ambre), qu'il faut défiler, ou
        l'écran quand ce n'est pas celui de la souris."""
        complet = self.reglages["balise_detail"] == "complet"
        morceaux, puces = [], []
        if ou.get("introuvable") is not None and not e.get("cible"):
            # La cible manque dans sa fenêtre : la balise le dit, et propose les noms proches.
            if ou.get("app"):
                morceaux.append((ou.get("exe"), ou["app"], False))
            if ou.get("lieu"):
                morceaux.append((None, ou["lieu"], False))
            morceaux.append((None if morceaux else ou.get("exe"),
                             tr("« {e} » introuvable", e=ou["introuvable"]) if ou["introuvable"] else tr("introuvable"), True))
            for nom in (ou.get("proches") or [])[:2]:
                puces.append((None, tr("proche : « {n} »", n=court(nom, 24)), "info"))
            if not ou.get("proches"):
                puces.append((None, tr("pas sur cette page"), "alerte"))
            return tuple(morceaux), tuple(puces), None
        if ou.get("etape1"):
            morceaux.append((ou.get("exe"), ou["etape1"], True))
            obstacle = ou.get("obstacle") or {}
            if obstacle.get("app"):
                puces.append((obstacle.get("exe"), tr("sous « {a} »", a=obstacle["app"]), "alerte"))
        else:
            if ou.get("app") and not suite:
                morceaux.append((ou.get("exe"), ou["app"], True))
            if ou.get("lieu") and (complet or not ou.get("element")) and not suite:
                morceaux.append((None, ou["lieu"], False))
            if ou.get("element"):
                morceaux.append((None if morceaux else ou.get("exe"), ou["element"], not morceaux))
        if not morceaux:
            texte = (e.get("texte_puis") if suite else "") or e.get("bulle") or tr("Regarde ici")
            morceaux.append((None, court(texte.split("\n")[0], 40), True))
        if ou.get("defiler"):
            puces.append((None, tr("fais défiler {d}", d=ou["defiler"]), "info"))
        cible = e.get("puis") if suite else e.get("cible")
        cx, cy = self.curseur()
        if cible and ou.get("ecran") and ecran_de(self.ecrans, cx, cy) is not ecran_de(self.ecrans, *cible):
            puces.append((None, ou["ecran"], "info"))
        return tuple(morceaux), tuple(puces), etape

    def baliser(self, etats, cx, cy, maintenant):
        """Les balises (l'utilisateur, 5 octobre 2026) : sur la ligne de chaque demande qui montre, la bulle qui dit où est
        exactement la cible (l'app, l'onglet, l'élément, ce qui la couvre). Une deuxième balise sur le lien vers
        l'étape 2 (ou le point de dépose d'un glisser). Une balise qui n'a pas de place sur sa ligne s'efface : la
        souris est déjà tout près de la cible."""
        rg, voulues, sur_ancre = self.reglages, {}, set()
        if rg["balise"]:
            for e in etats:
                if e.get("eff") == "montre" and not e.get("cible") and e.get("ancre"):
                    # La cible est introuvable dans sa fenêtre : une balise en haut de la page, sans ligne.
                    ancre = tuple(e["ancre"])
                    voulues[(e["ident"], "a")] = (self.contenu_balise(e, e.get("ou") or {}, None),
                                                  rvb(self.couleur_guide(e)), (cx, cy), ancre,
                                                  zone_ou_carre(None, ancre, 12), [], maintenant)
                    sur_ancre.add((e["ident"], "a"))
                    continue
                if e.get("eff") != "montre" or not e.get("cible"):
                    continue
                couleur = rvb(self.couleur_guide(e))
                ou = e.get("ou") or {}
                if e.get("etape") == 2:
                    ou = e.get("ou_puis") or {}
                suite = e.get("puis") or e.get("vers")
                zone_a = zone_ou_carre(e.get("zone"), e["cible"], 12)
                zone_b = zone_ou_carre(e.get("zone_puis") or e.get("zone_vers"), suite, 12) if suite else None
                etape = e.get("etape") or (1 if (ou.get("etape1") or suite) else None)
                voulues[(e["ident"], "a")] = (self.contenu_balise(e, ou, etape), couleur, (cx, cy), tuple(e["cible"]),
                                              zone_a, [zone_b], maintenant)
                if suite:
                    ou_b = (e.get("ou_puis") if e.get("puis") else e.get("ou_vers")) or {}
                    if e.get("vers") and not ou_b.get("etape1"):
                        ou_b = {**ou_b, "element": tr("dépose ici") + (" › " + ou_b["element"] if ou_b.get("element") else "")}
                    voulues[(e["ident"], "b")] = (self.contenu_balise(e, ou_b, 2, suite=True), couleur, tuple(e["cible"]),
                                                  tuple(suite), zone_b, [zone_a], maintenant)
        bouge = self.animations_windows()
        fond, texte = rvb(Panneau.BULLE_FOND), rvb(Panneau.BULLE_TEXTE)
        self.trous = []
        poses = []
        for cle, (contenu, couleur, de, a, zone, eviter, depuis) in voulues.items():
            b = self.balises.get(cle)
            if b is None:
                b = self.balises[cle] = Balise(self.racine)
            b.peindre(contenu, couleur, fond, texte)
            lg, ht = b.taille()
            centre = place_sur_ligne(lg, ht, de, a, zone, list(eviter) + poses, self.ecrans)
            if centre is None and cle in sur_ancre:
                centre = a                             # la souris est déjà sur la page : la balise se pose là
            if centre is None:
                b.partir(maintenant)
                continue
            long = math.hypot(a[0] - de[0], a[1] - de[1]) or 1
            b.poser(centre, ((a[0] - de[0]) / long, (a[1] - de[1]) / long), maintenant,
                    self.lignes_nees_de(a, depuis), bouge, zone if cle[1] == "a" and cle not in sur_ancre else None,
                    couleur, rg["balise_respire"])
            r = b.rect()
            if r:
                self.trous.append(r)
                poses.append(r)
        for cle in list(self.balises):
            if cle not in voulues and self.balises[cle].partir(maintenant):
                self.balises.pop(cle).detruire()           # le geste est fait : fondu de sortie, puis plus rien

    def lignes_nees_de(self, but, defaut):
        """L'heure où la ligne vers ce but est apparue (la balise entre après son tracé) ; sinon « defaut »."""
        for nom, t in self.lignes_nees.items():
            if round(but[0] / 150) == nom[3] and round(but[1] / 150) == nom[4]:
                return t
        return defaut

    def ranger_fleches(self, ident):
        for f in self.fleches.pop(ident, ())[:5]:
            if f:
                f.detruire()
        for b in self.etiquettes_lien.pop(ident, []):
            b.detruire()

    def guider(self, e, cx, cy):
        """La flèche près de la souris : vers l'endroit montré le plus récent, quand il est loin."""
        lignes = self.reglages["guidage"] == "lignes"
        # Le lien entre les deux cibles d'une demande (un glisser de A vers B, ou l'étape 1 puis l'étape 2) : une ligne
        # pleine, avec une pointe vers B, dans les deux modes (l'utilisateur, 3 octobre : « 2 éléments liés par les lignes de
        # guidage, un support visuel simple qui met en relation les actions entre 2 cibles »).
        if e is not None:
            suite = e.get("puis") or e.get("vers")
            if suite:
                self.lignes.append((suite[0], suite[1], self.couleur_guide(e), tuple(e["cible"]), "lien"))
        # En mode lignes, la ligne reste jusqu'au clic, même tout près du but (l'utilisateur, 12h29 : « la ligne disparaît
        # quand on approche de la cible, garde-la jusqu'au clic ») ; la flèche, elle, se cache près du but.
        if e is None or (not lignes and math.hypot(e["cible"][0] - cx, e["cible"][1] - cy) < GUIDE_PX):
            self.guide.placer_coin(-3000, -3000)
            return
        if lignes:
            self.guide.placer_coin(-3000, -3000)
            self.lignes.append((e["cible"][0], e["cible"][1], self.couleur_guide(e), None, False))
            return
        angle = math.atan2(e["cible"][1] - cy, e["cible"][0] - cx)
        self.guide.orienter(cx, cy, angle, self.couleur_guide(e), self.reglages["fleche_creuse"])

    def tracer_lignes(self, cx, cy, maintenant):
        """Les pointillés de la souris vers chaque but (réglage « lignes ») ; redessinés seulement quand
        quelque chose a bougé, au plus 15 fois par seconde (voir Voile)."""
        rg = self.reglages
        # « Moins de mouvement » : si Windows a coupé ses animations (Accessibilité > Effets visuels), ni tracé ni
        # animation continue.
        bouge = self.animations_windows()
        trace = rg["lignes_trace"] and bouge
        animation = rg["lignes_animation"] if bouge else "aucune"
        reglage = (rg["lignes_style"], rg["lignes_epaisseur"], rg["lignes_espacement"], rg["lignes_couleur"],
                   rg["lignes_couleur_unique"], rg["lignes_opacite_depart"], rg["lignes_opacite_arrivee"],
                   rg["lignes_fondu_debut"], rg["lignes_fondu_fin"], rg["lignes_forme"], rg["lignes_courbure"],
                   trace, animation, rg["lignes_vitesse"])
        cle = (cx, cy, tuple((round(x), round(y), c, de and (round(de[0]), round(de[1])), suite)
                             for x, y, c, de, suite in self.lignes), reglage,
               tuple(tuple(int(v) for v in t) for t in self.trous))
        # Une ligne qui se dessine (250 ms) ou une animation continue : on redessine même si rien n'a bougé, jusqu'à
        # ce que chaque ligne ait été dessinée EN ENTIER une fois (mesuré le 2 octobre : créer les toiles prend
        # 0,45 s ; la ligne finissait son tracé sans avoir été dessinée, et restait invisible).
        trace_en_cours = trace and any(nom not in self.lignes_tracees for nom in self.lignes_nees)
        anime = bool(self.lignes) and (animation != "aucune" or trace_en_cours)
        if (cle == self.lignes_cle and not anime) or maintenant - self.lignes_t < (1 / 30 if trace_en_cours else 1 / 15):
            return
        self.lignes_cle, self.lignes_t = cle, maintenant
        if self.lignes and not self.voiles:
            self.voiles = [Voile(self.racine, e) for e in self.ecrans]
        if not self.voiles:
            return
        vitesse = max(1, min(10, rg["lignes_vitesse"]))
        decalage = maintenant * (6 + 6 * vitesse) / max(4, rg["lignes_espacement"]) if animation == "defile" else 0.0
        onde = (maintenant * (0.12 + 0.05 * vitesse)) % 1.5 - 0.2      # la place de l'onde sur le trajet, puis une pause
        morceaux, vues = [], set()
        for x, y, couleur, de, suite in self.lignes:
            if rg["lignes_couleur"] == "unique":
                couleur = rg["lignes_couleur_unique"]
            # La ligne se dessine de la souris au but en 250 ms quand elle apparaît, en ralentissant à l'arrivée.
            nom = (couleur, de is not None, suite, round(x / 150), round(y / 150))
            vues.add(nom)
            visible = 1.0
            if trace:
                u = (maintenant - self.lignes_nees.setdefault(nom, maintenant)) / TRACE_S
                visible = 1.0 if u >= 1 else 1 - (1 - u) ** 3
            if visible >= 1.0:
                self.lignes_tracees.add(nom)
            x0, y0 = de if de else (cx, cy)
            lien = suite == "lien"                       # le lien entre deux cibles : pleine taille, et une pointe
            k = 0.7 if suite is True else 1.0            # la ligne du pigeon au travail : des points plus petits
            dernier = None
            for px, py, ux, uy, f in points_de_ligne(x0, y0, x, y, depart=22 if lien else (10 if de else 26),
                                                     fin=30 if lien else 6, pas=rg["lignes_espacement"],
                                                     forme=rg["lignes_forme"], courbure=rg["lignes_courbure"],
                                                     decalage=decalage):
                if f > visible:
                    break
                dernier = (px, py, ux, uy, f)
                kk = k
                if animation == "onde":
                    kk *= 1 + 0.9 * math.exp(-((f - onde) / 0.07) ** 2)    # les points grossissent au passage
                morceaux.append((px, py, ux, uy, couleur, f, kk))
            if lien and dernier and visible >= 1.0:
                px, py, ux, uy, f = dernier
                morceaux.append((px + ux * 10, py + uy * 10, ux, uy, couleur, f, 1.0, "pointe"))
        for nom in list(self.lignes_nees):
            if nom not in vues:
                del self.lignes_nees[nom]
                self.lignes_tracees.discard(nom)
        if self.trous:                                   # sous une balise, la ligne s'interrompt et reprend après
            morceaux = [m for m in morceaux
                        if not any(t[0] - 5 <= m[0] <= t[2] + 5 and t[1] - 5 <= m[1] <= t[3] + 5 for t in self.trous)]
        for v in self.voiles:
            v.dessiner([m for m in morceaux if v.contient(m[0], m[1])], rg["lignes_style"], rg["lignes_epaisseur"],
                       rg["lignes_opacite_depart"], rg["lignes_opacite_arrivee"], rg["lignes_fondu_debut"],
                       rg["lignes_fondu_fin"])

    def guider_attente(self, etats, cx, cy, maintenant):
        """Les sessions qui t'attendent (sauf celles mises en pause) :
        - chacune a son encadré léger, de sa couleur, autour de sa ligne dans Claude ou de la zone de saisie
          (l'utilisateur, 11h13 : « laisse-les surlignés en tout temps » ; le réglage peut revenir à « à l'approche ») ;
        - la petite flèche près de la souris pointe la plus récente, et se cache près du but."""
        # Toutes les sessions qui attendent ont leur encadré (et leur étiquette) ; la ligne et la flèche, seulement
        # celles que le réglage « lignes_reponse » guide (voir guider_cette_attente).
        attentes = [e for e in (etats or []) if e["eff"] in ("attend", "appel") and not e["parent"]]
        guidees = [e for e in attentes if self.guider_cette_attente(e, maintenant)]
        # Les encadrés
        voulus = {}
        for e in attentes:
            zone = e.get("zone_reponse")
            if not zone or self.reglages["encadres"] == "jamais":
                continue
            if self.reglages["encadres"] == "approche":
                p = e.get("reponse") or zone[:2]
                if math.hypot(p[0] - cx, p[1] - cy) > 400:
                    continue
            voulus[e["ident"]] = (zone, self.couleur_guide(e))
        for ident in list(self.cadres_reponse):
            if ident not in voulus or self.cadres_reponse[ident].couleur != voulus[ident][1]:
                self.cadres_reponse.pop(ident).detruire()
        for ident, (zone, couleur) in voulus.items():
            if ident not in self.cadres_reponse:
                self.cadres_reponse[ident] = Cadre(self.racine, couleur)
            # Dans la ligne (marge -1) : jamais sur la voisine ; l'épaisseur et le style sont des réglages.
            # Les lignes de la liste de Claude se touchent : l'encadré reste au ras ou dedans (jamais sur la voisine).
            self.cadres_reponse[ident].entourer(zone, min(0, self.reglages["encadres_marge"]) - self.reglages["encadres_epaisseur"],
                                                self.reglages["encadres_epaisseur"],
                                                self.reglages["encadres_style"], None, self.reglages["encadres_arrondi"])
        # Les étiquettes (réglage « infos à l'écran », l'utilisateur, 16h51 : « plus d'info à l'écran, pour guider
        # davantage ») : à côté de l'encadré, qui t'attend, pour quoi et depuis quand ; en « complètes », le geste
        # à faire et son raccourci. Elles ne bougent pas : elles suivent l'encadré, pas la souris.
        niveau = self.reglages["infos_ecran"]
        for ident in list(self.etiquettes):
            if niveau == "discret" or ident not in voulus:
                self.etiquettes.pop(ident).detruire()
        if niveau != "discret":
            for e in attentes:
                if e["ident"] not in voulus:
                    continue
                zone, couleur = voulus[e["ident"]]
                if e["ident"] not in self.etiquettes:
                    self.etiquettes[e["ident"]] = Bulle(self.racine)
                    # Plus large qu'une bulle : à 280 px, « depuis 2 min » se coupait en deux (vu le 2 octobre, 16h55).
                    self.etiquettes[e["ident"]].texte.config(wraplength=460)
                # Elle évite le panneau des pigeons (souvent collé à Claude, juste à droite de la zone de saisie).
                panneau = (self.racine.winfo_rootx(), self.racine.winfo_rooty(),
                           self.racine.winfo_rootx() + self.racine.winfo_width(),
                           self.racine.winfo_rooty() + self.racine.winfo_height()) if self.racine.state() == "normal" else None
                self.etiquettes[e["ident"]].montrer(zone[2], zone[1], self.texte_etiquette(e, maintenant, niveau == "complet"),
                                                    couleur, self.ecrans, zone, self.reglages["opacite_bulles"],
                                                    eviter=[panneau])
        # Les petites flèches : une par session qui t'attend, de sa couleur, autour de la souris (l'utilisateur, 11h24 :
        # « il peut y avoir plus qu'une flèche de couleur qui me guident en même temps »). Deux flèches de
        # directions voisines (moins de 25 degrés) ne se chevauchent pas : la suivante se place plus loin.
        taille = self.reglages["taille_fleche"]
        voulues = []
        if self.reglages["fleche_attente"]:
            for e in guidees:
                # Sans endroit où répondre (une session hors de l'app Claude, ou Claude réduite), on visait le pigeon ;
                # caché, il est garé dans la barre des tâches, et la ligne pointait « vers rien » (l'utilisateur, 5 octobre
                # 2026, 20h47, sa capture). Pigeons cachés : pas de ligne, la carte du panneau suffit.
                but = e.get("reponse")
                if not but and self.reglages["afficher_pigeons"] and e["ident"] in self.pos:
                    but = tuple(self.pos[e["ident"]])
                if but and self.reglages["guidage"] == "lignes":
                    self.lignes.append((but[0], but[1], self.couleur_guide(e), None, False))   # jusqu'à la réponse
                elif but and math.hypot(but[0] - cx, but[1] - cy) > 250:
                    voulues.append((math.atan2(but[1] - cy, but[0] - cx), e))
        voulues.sort(key=lambda v: v[0])
        gardees = set()
        anneau, angle_prec = 0, None
        for angle, e in voulues:
            ident = e["ident"]
            ecart = None if angle_prec is None else abs((angle - angle_prec + math.pi) % (2 * math.pi) - math.pi)
            anneau = anneau + 1 if ecart is not None and ecart < math.radians(25) else 0
            angle_prec = angle
            g = self.petits_guides.get(ident)
            if g is None or g.taille != taille:
                if g is not None:
                    g.detruire()
                g = self.petits_guides[ident] = PetitGuide(self.racine, taille)
            g.orienter(cx, cy, angle, self.couleur_guide(e), maintenant, rayon=32 + anneau * taille * 0.9,
                       creuse=self.reglages["fleche_creuse"])
            gardees.add(ident)
        for ident in list(self.petits_guides):
            if ident not in gardees:
                self.petits_guides.pop(ident).detruire()

    @staticmethod
    def texte_etiquette(e, maintenant, complet):
        """L'étiquette d'une session qui attend : « Ma mission · question · depuis 12 min » ; en « complètes », une
        deuxième ligne dit le geste à faire et son raccourci."""
        quoi = tr(IMPORTANCES.get(e.get("importance"), "t'attend"))
        if e.get("questionnaire"):
            quoi = tr("questionnaire : choisis une réponse")
        texte = f"{court(e['titre'], 40)} · {quoi}"
        if e["depuis"]:
            texte += " · " + depuis_lisible(maintenant - e["depuis"])
        if complet:
            if e.get("questionnaire"):
                texte += "\n" + tr("→ choisis une option, puis « Envoyer » (ou « Passer »)")
            else:
                texte += "\n" + (tr("→ va donner la permission dans la session · Ctrl+Alt+P")
                                 if e.get("importance") == "bloquee" else tr("→ clique ici pour lui répondre · Ctrl+Alt+P"))
        return texte

    def consigne_complete(self, e):
        """La bulle d'une demande de montre.py en « infos complètes » : la consigne entière, l'étape, le raccourci."""
        texte = court(e["bulle"] or "", 200)
        if e.get("etape"):
            texte += "\n" + tr("Étape {n} sur 2", n=e["etape"])
        return texte + "\n" + tr("Clique l'endroit encadré · Ctrl+Alt+T : c'est fait")

    def animations_windows(self):
        """Vrai si les animations de Windows sont actives (SPI_GETCLIENTAREAANIMATION, mesuré à 1 chez l'utilisateur le
        2 octobre) ; relu toutes les 10 s."""
        maintenant = time.time()
        if maintenant - getattr(self, "_t_anim", 0) > 10:
            v = ctypes.c_int(1)
            user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(v), 0)
            self._anim_windows, self._t_anim = bool(v.value), maintenant
        return self._anim_windows

    def guider_cette_attente(self, e, maintenant):
        """Une session qui attend ta réponse (fin de tour ou question) : sa ligne et sa flèche durent selon le réglage
        « lignes_reponse » (toujours, quelques minutes, ou jamais). Après « Guider » ou Ctrl+Alt+P : toujours, jusqu'à
        la réponse. Une question posée (son questionnaire) et une permission à donner arrêtent la session : toujours
        guidées (l'utilisateur, 3 octobre 08h57)."""
        if e.get("importance") in ("bloquee", "normale") or e["ident"] in self.rappels:
            return True
        reglage = self.reglages["lignes_reponse"]
        if reglage == "jamais":
            return False
        if reglage == "toujours" or not str(reglage).isdigit():
            return True
        return maintenant - (e["depuis"] or maintenant) < int(reglage) * 60

    def guider_session(self, ident):
        """Le bouton « Guider » du panneau : le pigeon revient près de la souris et les flèches le suivent."""
        e = self.etats.get(ident)
        self.en_pause.pop(ident, None)
        self.ancres.pop(ident, None)
        if e and e["mode"] in ("attend", "appel"):
            self.rappels[ident] = time.time()
        self.infos[ident] = time.time() + 4

    def etape_courante(self, e):
        """Une demande en deux étapes : tant que l'étape 1 n'est pas faite, la cible est l'étape 1 et l'étape 2
        se montre à côté (encadré « 2 », pointillé 1 -> 2) ; une fois l'étape 1 cliquée, l'étape 2 devient la
        cible. Le reste du code (flèches, bulle, clic) ne voit que « la cible »."""
        ident = e["ident"]
        if e["mode"] != "montre" or not e.get("puis"):
            self.etapes.pop(ident, None)
            e["etape"] = 0
            return
        if self.etapes.get(ident) == 2:
            e["precedente"] = e["cible"]
            e["cible"], e["zone"] = e["puis"], e.get("zone_puis")
            e["bulle"] = e.get("texte_puis") or e["bulle"]
            e["puis"], e["zone_puis"] = None, None
            e["etape"] = 2
        else:
            e["etape"] = 1

    def mettre_en_pause(self, ident, minutes=None):
        """Plus tard : pour quelques minutes (le pigeon revient seul), ou sans limite (minutes=None)."""
        self.en_pause[ident] = time.time() + minutes * 60 if minutes else None
        self.rappels.pop(ident, None)

    def uia_principal(self):
        """L'automatisation de Windows pour le fil de l'affichage (celle du guetteur vit dans son propre fil)."""
        if self._uia is None:
            import comtypes, comtypes.client
            try:
                comtypes.CoInitializeEx(comtypes.COINIT_APARTMENTTHREADED)
            except OSError:
                pass
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as U
            self._uia = (comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation), U)
        return self._uia

    def aller_a_la_session(self, ident):
        """« Aller à la session » : ramène l'app Claude devant et ouvre la session dans sa liste de gauche
        (l'utilisateur, 11h55 : prendre action plus vite). On essaie d'abord les gestes de l'automatisation de Windows
        (Invoke, Select, l'action par défaut) sur la ligne et ses parents ; sinon, un clic au centre de la ligne,
        et la souris revient où elle était."""
        e = self.etats.get(ident)
        s = self.guetteur.sessions.get(ident) if getattr(self, "guetteur", None) else None
        app = (getattr(s, "annonce", None) or {}).get("app")
        if app:
            self.amener_fenetre(app)                  # Codex ou AG (suivre_les_autres_ia) : leur fenêtre devant
            return
        h = user32.FindWindowW("Chrome_WidgetWin_1", "Claude")
        if not e or not h:
            return
        amener_devant(h)
        try:
            uia, U = self.uia_principal()
            L, T, R, B = cadre_visible(h)
            cond = uia.CreatePropertyConditionEx(U.UIA_NamePropertyId, e["titre"][:20], 3)
            tab = uia.ElementFromHandle(W.HWND(h)).FindAll(U.TreeScope_Descendants, cond)
            lignes = []
            for k in range(tab.Length):
                el = tab.GetElement(k)
                z = el.CurrentBoundingRectangle
                if (0 < z.right - z.left < (R - L) * 0.5 and z.bottom - z.top < 80 and z.top > T + 40
                        and not (el.CurrentName or "").startswith("Plus d'options")):
                    lignes.append((z.left, el))      # la ligne de la liste, pas « renommer » ni « Plus d'options »
            if not lignes:
                return
            el = min(lignes, key=lambda x: x[0])[1]
            if not activer_element(uia, U, el):
                z = el.CurrentBoundingRectangle
                cliquer((z.left + z.right) // 2, (z.top + z.bottom) // 2)
            log.info("aller à la session %s", e["titre"])
        except Exception as ex:
            log.warning("aller à la session : %s", ex)

    def nouvelle_seance(self, item):
        """« Nouvelle séance » (l'utilisateur, 6 octobre 2026 : le geste le plus fréquent, « ouvre une séance dans X et colle le
        prompt », n'était jamais montré) : l'invite va dans le presse-papiers, l'app Claude vient devant et ouvre une
        nouvelle session dans le bon dossier, par son bouton « Nouvelle session dans X. » de la liste de gauche (un par
        dossier ; « la-marmite » pour Mon projet). Il reste à coller (Ctrl+V) et à envoyer : l'utilisateur garde l'envoi.
        Sans ce bouton (barre latérale cachée, dossier jamais ouvert) : la ligne le guide vers « Nouveau »."""
        import unicodedata

        def norme(t):
            t = unicodedata.normalize("NFD", (t or "").casefold())
            return "".join(c for c in t if c.isalnum() and not unicodedata.combining(c))
        self.racine.clipboard_clear()
        self.racine.clipboard_append(item["valeur"])
        self.infos["__copie__"] = time.time()
        dossier = item.get("dossier")
        nom = os.path.basename(dossier.rstrip("\\/")) if dossier else ""
        h = user32.FindWindowW("Chrome_WidgetWin_1", "Claude")
        if h:
            amener_devant(h)
            try:
                uia, U = self.uia_principal()
                cond = uia.CreateOrCondition(
                    uia.CreatePropertyConditionEx(U.UIA_NamePropertyId, "Nouvelle session dans", 3),
                    uia.CreatePropertyConditionEx(U.UIA_NamePropertyId, "New session in", 3))
                tab = uia.ElementFromHandle(W.HWND(h)).FindAll(U.TreeScope_Descendants, cond)
                groupes = {}
                for k in range(tab.Length if nom else 0):
                    el = tab.GetElement(k)
                    groupe = re.sub(r"^(Nouvelle session dans|New session in)\s*", "", el.CurrentName or "").rstrip(". ")
                    groupes.setdefault(norme(groupe), (groupe, el))
                # Le dossier, sinon son parent le plus proche qui a son groupe (Pigeons n'en a pas : ses séances
                # s'ouvrent dans « Desktop »).
                d = dossier
                for _ in range(3 if nom else 0):
                    trouve = groupes.get(norme(os.path.basename(d.rstrip("\\/"))))
                    if trouve:
                        groupe, el = trouve
                        if not activer_element(uia, U, el):
                            z = el.CurrentBoundingRectangle
                            cliquer((z.left + z.right) // 2, (z.top + z.bottom) // 2)
                        log.info("nouvelle séance ouverte dans « %s »", groupe)
                        return
                    d = os.path.dirname(d.rstrip("\\/"))
            except Exception as ex:
                log.warning("nouvelle séance : %s", ex)
        # Pas de bouton pour ce dossier : la ligne guide vers « Nouveau », et la consigne nomme le dossier.
        demande = {"session": "nouvelle-seance", "titre": tr("Nouvelle séance"), "heure": time.time(), "duree_s": 300,
                   "texte": tr("Clique « Nouveau », choisis le dossier « {d} », puis colle l'invite (Ctrl+V)", d=nom)
                   if nom else tr("Clique « Nouveau », puis colle l'invite (Ctrl+V)"),
                   "cible": {"fenetre": "Claude", "element": "Nouveau" if LANGUE == "fr" else "New"},
                   "vers": None, "importance": "haute", "puis": None, "texte_puis": ""}
        try:
            provisoire = DEMANDES / "nouvelle-seance.tmp"
            provisoire.write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
            os.replace(provisoire, DEMANDES / "nouvelle-seance.json")
        except OSError as ex:
            log.warning("nouvelle séance (guidage) : %s", ex)
        log.info("nouvelle séance : pas de bouton pour « %s », guidage vers Nouveau", nom)

    def amener_fenetre(self, titre):
        """« Amener devant » (l'aide active) : la première fenêtre visible dont le titre contient ce texte, hors des
        nôtres."""
        moi = os.getpid()
        for h in fenetres_visibles():
            pid = W.DWORD()
            user32.GetWindowThreadProcessId(W.HWND(h), ctypes.byref(pid))
            if pid.value != moi and titre.lower() in (titre_de(h) or "").lower():
                amener_devant(h)
                log.info("amener devant : %s", titre_de(h))
                return

    def prochaine_action(self):
        """Ctrl+Alt+P : la chose la plus importante à faire (puis la suivante si on rappuie dans les 6 s).
        Une session qui t'attend : on y va ; une demande « montre » : le pigeon reprend son guidage."""
        maintenant = time.time()
        a_faire = [e for e in self.etats.values() if not e["parent"] and e.get("eff") in ("montre", "appel", "attend")]
        if not a_faire:
            a_faire = [e for e in self.etats.values() if not e["parent"] and e.get("eff") == "pause"]
        if not a_faire:
            return
        a_faire.sort(key=lambda e: (RANG_IMPORTANCE.get(e.get("importance"), 3), e["depuis"]))
        rang = (self.cycle[1] + 1) % len(a_faire) if maintenant - self.cycle[0] < 6 else 0
        self.cycle = (maintenant, rang)
        e = a_faire[rang]
        self.guider_session(e["ident"])
        if e["mode"] != "montre":
            self.aller_a_la_session(e["ident"])

    def tout_en_pause(self):
        """Tout mettre en pause, ou tout reprendre si tout l'est déjà."""
        a_faire = [i for i, e in self.etats.items() if e.get("eff") in ("montre", "appel", "attend", "pause")
                   and not e["parent"]]
        if any(i not in self.en_pause for i in a_faire):
            for i in a_faire:
                self.mettre_en_pause(i)
        else:
            for i in a_faire:
                self.en_pause.pop(i, None)

    def ouvrir_reglages(self):
        """La fenêtre des réglages : un seul grand panneau où tout est visible (l'utilisateur, 12h50 : « j'aimais mieux le
        panneau d'avant où tout était visible ; je voulais juste qu'il soit mieux organisé »), rangé en trois colonnes
        de cartes à titre. Chaque changement s'applique tout de suite et se garde dans reglages.json ; « Remettre par
        défaut » garde la langue, la place du panneau et le démarrage."""
        tk, P = self.tk, Panneau
        if getattr(self, "fen_reglages", None) is not None and self.fen_reglages.winfo_exists():
            self.fen_reglages.lift()
            return
        f = self.fen_reglages = tk.Toplevel(self.racine)
        f.title(tr("Pigeons · réglages"))
        f.configure(bg=P.FOND)
        f.resizable(True, True)
        f.minsize(680, 460)
        barre_de_titre_sombre(f)
        variables = {}

        def appliquer(*_):
            global LANGUE
            avant = self.reglages.get("demarrage_windows")
            langue_avant = self.reglages.get("langue")
            for cle, v in variables.items():
                self.reglages[cle] = v.get()
            if self.reglages["demarrage_windows"] != avant:
                regler_demarrage(self.reglages["demarrage_windows"])
            sauver_reglages(self.reglages)
            if self.appliquer_apparence():
                # Une autre apparence : on rouvre les réglages dans leurs nouvelles couleurs.
                f.destroy()
                self.racine.after(50, self.ouvrir_reglages)
                return
            if self.reglages["langue"] != langue_avant:
                # Une autre langue : on retraduit le panneau, et on rouvre les réglages dans la nouvelle langue.
                LANGUE = self.reglages["langue"]
                self.panneau.retraduire()
                f.destroy()
                self.racine.after(50, self.ouvrir_reglages)

        def par_defaut():
            from tkinter import messagebox
            if not messagebox.askyesno(tr("Pigeons · réglages"), tr("Remettre tous les réglages par défaut ?"), parent=f):
                return
            gardes = {k: self.reglages.get(k) for k in ("langue", "panneau_geometrie", "demarrage_windows")}
            self.reglages.clear()
            self.reglages.update(REGLAGES_DEFAUT)
            self.reglages.update(gardes)
            sauver_reglages(self.reglages)
            f.destroy()
            self.racine.after(50, self.ouvrir_reglages)

        # La mise en page des paramètres de Claude (l'utilisateur, 3 octobre 09h37 : « organise les paramètres dans ce style ») :
        # à gauche, une recherche et les catégories ; à droite, les sections de la catégorie choisie. La recherche
        # montre les sections de toutes les catégories qui contiennent le mot cherché.
        from tkinter import ttk
        cote_fond = melanger(P.FOND, P.TEXTE, 0.04)
        corps_f = tk.Frame(f, bg=P.FOND)
        corps_f.pack(fill="both", expand=True)
        cote = tk.Frame(corps_f, bg=cote_fond, width=210)
        cote.pack(side="left", fill="y")
        cote.pack_propagate(False)
        droite = tk.Frame(corps_f, bg=P.FOND)
        droite.pack(side="left", fill="both", expand=True)
        titre_page = tk.Label(droite, text="", bg=P.FOND, fg=P.TEXTE, font=("Segoe UI Semibold", 16), anchor="w")
        titre_page.pack(fill="x", padx=24, pady=(18, 4))
        toile = tk.Canvas(droite, bg=P.FOND, highlightthickness=0, bd=0)
        defil = ttk.Scrollbar(droite, orient="vertical", command=toile.yview, style="Pigeons.Vertical.TScrollbar")
        toile.configure(yscrollcommand=defil.set)
        defil.pack(side="right", fill="y")
        toile.pack(side="left", fill="both", expand=True)
        contenu = tk.Frame(toile, bg=P.FOND)
        id_contenu = toile.create_window((0, 0), window=contenu, anchor="nw")
        contenu.bind("<Configure>", lambda _e: toile.configure(scrollregion=toile.bbox("all")))
        toile.bind("<Configure>", lambda e: toile.itemconfigure(id_contenu, width=e.width))
        toile.bind("<Enter>", lambda _e: toile.bind_all(
            "<MouseWheel>", lambda e: toile.yview_scroll(int(-e.delta / 120), "units")))
        toile.bind("<Leave>", lambda _e: toile.unbind_all("<MouseWheel>"))
        sections = []          # (titre, catégorie, cadre de la section)
        categorie_de = {"Apparence": "apparence", "Couleurs et bulles": "apparence", "Général": "general",
                        "Guidage": "guidage", "Quand une session m'attend": "guidage", "Lignes pointillées": "lignes",
                        "Forme et mouvement": "lignes", "Fondu": "lignes", "Couleur des lignes": "lignes",
                        "Encadrés": "encadres", "Pigeons": "pigeons"}

        def carte(_colonne, titre):
            """Une section : son titre, puis une carte qui groupe ses réglages ; elle se montre avec sa catégorie."""
            section = tk.Frame(contenu, bg=P.FOND)
            tk.Label(section, text=tr(titre), bg=P.FOND, fg=P.TEXTE, font=("Segoe UI Semibold", 11),
                     anchor="w").pack(fill="x", pady=(12, 6))
            boite = tk.Frame(section, bg=P.CARTE, padx=16, pady=10)
            boite.pack(fill="x")
            sections.append((titre, categorie_de.get(titre, "general"), section))
            return boite

        def sous_titre(parent, texte):
            tk.Label(parent, text=tr(texte), bg=P.CARTE, fg=P.TEXTE, font=("Segoe UI Semibold", 8),
                     anchor="w").pack(fill="x", pady=(6, 0))

        def note(parent, texte):
            tk.Label(parent, text=tr(texte), bg=P.CARTE, fg=P.PALE, font=("Segoe UI", 8), anchor="w", wraplength=520,
                     justify="left").pack(fill="x", pady=(2, 2))

        style_case = dict(P.STYLE_CASE, bg=P.CARTE, activebackground=P.CARTE)

        def choix(parent, cle, options):
            v = variables[cle] = tk.StringVar(value=self.reglages[cle])
            for valeur, texte in options:
                tk.Radiobutton(parent, text=tr(texte), value=valeur, variable=v, command=appliquer, **style_case).pack(fill="x")

        def choix_en_ligne(parent, cle, options):
            """Des choix courts côte à côte, sur une seule ligne (la fenêtre reste moins haute)."""
            v = variables[cle] = tk.StringVar(value=self.reglages[cle])
            ligne = tk.Frame(parent, bg=P.CARTE)
            ligne.pack(fill="x")
            for valeur, texte in options:
                tk.Radiobutton(ligne, text=tr(texte), value=valeur, variable=v, command=appliquer,
                               **style_case).pack(side="left", padx=(0, 6))

        def case(parent, cle, texte):
            v = variables[cle] = tk.BooleanVar(value=self.reglages[cle])
            tk.Checkbutton(parent, text=tr(texte), variable=v, command=appliquer, **style_case).pack(fill="x")

        def glissiere(parent, cle, texte, de, a):
            v = variables[cle] = tk.IntVar(value=self.reglages[cle])
            tk.Scale(parent, label=tr(texte), from_=de, to=a, orient="horizontal", variable=v, command=appliquer,
                     length=420, bg=P.CARTE, fg=P.TEXTE, troughcolor=P.FOND, highlightthickness=0, bd=0,
                     sliderrelief="flat", sliderlength=18, width=10, activebackground=P.ACCENT,
                     font=("Segoe UI", 8)).pack(fill="x")

        def couleur(parent, cle, texte):
            """Une pastille de couleur et son nom ; un clic ouvre le sélecteur de couleurs de Windows."""
            from tkinter import colorchooser
            ligne = tk.Frame(parent, bg=P.CARTE)
            ligne.pack(fill="x", pady=1)
            pastille = tk.Label(ligne, text="      ", bg=self.reglages[cle], cursor="hand2", bd=0)
            pastille.pack(side="left", padx=(2, 8))
            tk.Label(ligne, text=tr(texte), bg=P.CARTE, fg=P.TEXTE, font=("Segoe UI", 9)).pack(side="left")

            def choisir(_e=None):
                choisie = colorchooser.askcolor(color=self.reglages[cle], parent=f, title=tr(texte))[1]
                if choisie:
                    self.reglages[cle] = choisie
                    pastille.config(bg=choisie)
                    sauver_reglages(self.reglages)
                    if self.appliquer_apparence():
                        f.destroy()
                        self.racine.after(50, self.ouvrir_reglages)
            pastille.bind("<Button-1>", choisir)

        # -- Colonne 1 : l'apparence, le général et le guidage
        ap = carte(0, "Apparence")
        choix_en_ligne(ap, "theme", [("systeme", "Système"), ("clair", "Clair"), ("sombre", "Sombre")])
        sous_titre(ap, "Thème sombre")
        choix_en_ligne(ap, "theme_sombre", [("defaut", "Par défaut"), ("nuit", "Nuit"), ("ambre", "Ambre")])
        sous_titre(ap, "Contraste")
        choix_en_ligne(ap, "contraste", [("normal", "Normal"), ("fort", "Fort")])
        case(ap, "theme_perso", "Mes couleurs :")
        couleur(ap, "couleur_fond", "Fond")
        couleur(ap, "couleur_texte", "Texte")
        couleur(ap, "couleur_accent", "Accent")
        sous_titre(ap, "Bulles et étiquettes")
        choix_en_ligne(ap, "bulles_couleurs", [("papier", "Papier (claires)"), ("theme", "Aux couleurs du thème"), ("sombre", "Sombres")])
        case(ap, "bulle_cible", "Une bulle près de la cible (sinon, la consigne reste dans le panneau)")
        note(ap, "« Système » suit le thème clair ou sombre de Windows. « Ambre » reprend les couleurs d'Antigravity.")
        g = carte(0, "Général")
        sous_titre(g, "Langue")
        choix(g, "langue", [("en", "English"), ("fr", "Français")])
        sous_titre(g, "Le panneau")
        choix(g, "ancrer_claude", [("non", "Libre (je le place moi-même)"), ("droite", "Collé à droite de Claude"),
                                   ("gauche", "Collé à gauche de Claude")])
        case(g, "demarrage_windows", "Lancer les pigeons avec Windows")
        note(g, "Ctrl+Alt+P : prochaine action (rappuyer dans les 6 s passe à la suivante).")
        note(g, "Ctrl+Alt+T : « C'est fait » ou « Terminer » sur la première chose à faire. "
                "Clic droit sur un pigeon : terminer sa session.")
        gu = carte(0, "Guidage")
        choix(gu, "guidage", [("lignes", "Des lignes pointillées de ma souris au but"),
                              ("fleches", "Des flèches autour de ma souris")])
        case(gu, "fleche_attente", "Guider vers les sessions qui m'attendent")
        sous_titre(gu, "Infos à l'écran")
        choix(gu, "infos_ecran", [("discret", "Discrètes (la ligne et l'encadré)"),
                                  ("detaille", "Détaillées (une étiquette : qui, quoi, depuis quand)"),
                                  ("complet", "Complètes (et le geste à faire, avec son raccourci)")])
        sous_titre(gu, "La balise")
        case(gu, "balise", "Une balise sur la ligne : où est exactement la cible (l'app, l'onglet, ce qui la couvre)")
        sous_titre(gu, "Ce que dit la balise")
        choix_en_ligne(gu, "balise_detail", [("complet", "Tout le chemin"), ("court", "L'app et l'élément")])
        case(gu, "balise_respire", "Le halo de la balise respire lentement")
        sous_titre(gu, "Les flèches")
        case(gu, "fleche_creuse", "Flèches creuses (juste le contour)")
        glissiere(gu, "taille_fleche", "Taille des flèches (px)", 14, 44)
        at = carte(0, "Quand une session m'attend")
        sous_titre(at, "Ligne vers une session qui attend ma réponse")
        choix(at, "lignes_reponse", [("toujours", "Jusqu'à ma réponse (ou « Terminer »)"), ("15", "Pendant 15 min"),
                                     ("5", "Pendant 5 min"), ("1", "Pendant 1 min"),
                                     ("jamais", "Jamais : Ctrl+Alt+P ou « Guider » la montrent")])
        note(at, "Une fin de tour. L'encadré et l'étiquette restent. Une question posée (son questionnaire), une "
                 "permission à donner et un geste demandé sont toujours guidés.")
        case(at, "appel_souris", "Le pigeon vient près de ma souris")
        glissiere(at, "duree_appel_s", "Pendant (secondes)", 5, 60)
        glissiere(at, "report_clic_min", "Clic sur un pigeon : plus tard (min, 0 = sans fin)", 0, 120)

        # -- Colonne 2 : les lignes
        li = carte(1, "Lignes pointillées")
        choix(li, "lignes_style", [("points", "Des points"), ("tirets", "Des tirets")])
        glissiere(li, "lignes_epaisseur", "Grosseur (px)", 2, 10)
        glissiere(li, "lignes_espacement", "Espacement (px)", 6, 30)
        fm = carte(1, "Forme et mouvement")
        choix_en_ligne(fm, "lignes_forme", [("droite", "Droite"), ("arc", "En arc"), ("sinueuse", "Sinueuse"),
                                            ("vol", "En vol")])
        glissiere(fm, "lignes_courbure", "Courbure (%)", 0, 100)
        case(fm, "lignes_trace", "La ligne se dessine à son apparition")
        sous_titre(fm, "Animation continue")
        choix_en_ligne(fm, "lignes_animation", [("aucune", "Aucune"), ("defile", "Les points avancent"),
                                                ("onde", "Une onde")])
        glissiere(fm, "lignes_vitesse", "Vitesse de l'animation", 1, 10)
        note(fm, "« En vol » : un arc et de petites vagues, comme un pigeon. Une animation continue redessine les "
                 "lignes 15 fois par seconde : un peu plus de processeur.")
        fo = carte(1, "Fondu")
        glissiere(fo, "lignes_opacite_depart", "Opacité près de ma souris (%)", 0, 100)
        glissiere(fo, "lignes_opacite_arrivee", "Opacité près du but (%)", 0, 100)
        glissiere(fo, "lignes_fondu_debut", "Le fondu commence à (% du trajet)", 0, 100)
        glissiere(fo, "lignes_fondu_fin", "Le fondu finit à (% du trajet)", 0, 100)
        note(fo, "0 % du trajet : à ta souris ; 100 % : au but. Deux opacités égales : pas de fondu. "
                 "Exemple : 90 puis 0, de 50 à 100 : la ligne est pleine jusqu'à mi-chemin et s'éteint en arrivant.")
        cl = carte(1, "Couleur des lignes")
        choix(cl, "lignes_couleur", [("guide", "De la couleur du guide"), ("unique", "D'une seule couleur :")])
        couleur(cl, "lignes_couleur_unique", "la couleur unique des lignes")

        # -- Colonne 3 : encadrés, pigeons, couleurs, bulles
        en = carte(2, "Encadrés")
        choix(en, "encadres", [("toujours", "Actifs, toujours affichés"), ("approche", "Actifs quand ma souris approche"),
                               ("jamais", "Désactivés")])
        case(en, "encadres_montre", "Encadrer aussi l'endroit montré par une demande")
        case(en, "encadres_travail", "Sans pigeons, encadrer où chaque IA travaille (avec son nom)")
        choix(en, "encadres_style", [("pointilles", "En pointillés"), ("plein", "En trait plein")])
        glissiere(en, "encadres_marge", "Taille autour de la cible (px)", -3, 12)
        glissiere(en, "encadres_arrondi", "Coins arrondis (px)", 0, 12)
        glissiere(en, "encadres_epaisseur", "Épaisseur du trait (px)", 1, 4)
        pi = carte(2, "Pigeons")
        sous_titre(pi, "Quand une fenêtre cache l'icône où il travaille")
        choix(pi, "cible_cachee", [("barre", "Il va sur la barre des tâches"), ("perche", "Il se perche sur cette fenêtre"),
                                   ("cache", "Il se cache")])
        glissiere(pi, "taille_pigeon", "Taille des pigeons", 5, 14)
        case(pi, "afficher_pigeons", "Afficher les pigeons (sinon : les lignes, les flèches et les encadrés seulement)")
        case(pi, "pigeons_au_travail", "Montrer aussi les pigeons au travail")
        case(pi, "pigeonneaux", "Montrer les pigeonneaux (sous-agents)")
        sous_titre(pi, "Ligne vers l'endroit exact où il travaille")
        choix(pi, "lignes_travail", [("survol", "Au survol du pigeon"), ("toujours", "Toujours"), ("jamais", "Jamais")])
        co = carte(2, "Couleurs et bulles")
        choix(co, "couleur_guides", [("tache", "La couleur de la tâche"), ("importance", "Le code d'importance")])
        couleur(co, "couleur_bloquee", "Bloquée : une permission à donner")
        couleur(co, "couleur_haute", "Haute : un geste à faire")
        couleur(co, "couleur_normale", "Normale : une question posée")
        couleur(co, "couleur_basse", "Basse : à toi quand tu veux")
        sous_titre(co, "Bulles")
        choix(co, "bulles", [("courte", "Une ligne courte quand il montre ou m'appelle"), ("survol", "Seulement au survol")])
        glissiere(co, "opacite_bulles", "Opacité des bulles (%)", 40, 100)

        # -- La barre de gauche : la recherche, les catégories en deux groupes, et les deux boutons du bas.
        import unicodedata

        def sans_accents(t):
            return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if not unicodedata.combining(c))

        def textes(w):
            for opt in ("text", "label"):
                try:
                    valeur = w.cget(opt)
                except Exception:
                    continue
                if valeur:
                    yield str(valeur)
            for c in w.winfo_children():
                yield from textes(c)
        index = [(t, c, sec, sans_accents(" ".join(textes(sec)))) for t, c, sec in sections]
        aucun = tk.Label(contenu, text=tr("Aucun réglage ne correspond."), bg=P.FOND, fg=P.PALE,
                         font=("Segoe UI", 10, "italic"), anchor="w")
        noms = {"guidage": "Guidage", "lignes": "Lignes", "encadres": "Encadrés", "apparence": "Apparence",
                "pigeons": "Pigeons", "general": "Général"}
        groupes = (("Le guidage", (("guidage", "➚"), ("lignes", "⋯"), ("encadres", "▢"))),
                   ("L'app", (("apparence", "◐"), ("pigeons", "✧"), ("general", "⚙"))))
        boutons_cat = {}

        def montrer(cat, requete=""):
            for _t, _c, sec, _x in index:
                sec.pack_forget()
            aucun.pack_forget()
            if requete:
                q = sans_accents(requete)
                trouvees = [sec for _t, _c, sec, x in index if q in x]
                titre_page.config(text=tr("Résultats pour « {q} »", q=requete))
                for sec in trouvees:
                    sec.pack(fill="x", padx=24)
                if not trouvees:
                    aucun.pack(fill="x", padx=24, pady=12)
            else:
                self.page_reglages = cat
                titre_page.config(text=tr(noms[cat]))
                for _t, c, sec, _x in index:
                    if c == cat:
                        sec.pack(fill="x", padx=24)
            for c, b in boutons_cat.items():
                actif = c == cat and not requete
                b.config(bg=P.BOUTON if actif else cote_fond, fg=P.TEXTE if actif else P.PALE)
            toile.yview_moveto(0)

        recherche = tk.Frame(cote, bg=P.CARTE)
        recherche.pack(fill="x", padx=10, pady=(14, 10))
        tk.Label(recherche, text="⌕", bg=P.CARTE, fg=P.PALE, font=("Segoe UI Symbol", 11)).pack(side="left", padx=(8, 2))
        champ = tk.Entry(recherche, bg=P.CARTE, fg=P.PALE, insertbackground=P.TEXTE, relief="flat", bd=0,
                         font=("Segoe UI", 10))
        champ.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        indice = tr("Rechercher")
        champ.insert(0, indice)

        def entrer(_e):
            if champ.get() == indice:
                champ.delete(0, "end")
                champ.config(fg=P.TEXTE)

        def sortir(_e):
            if not champ.get():
                champ.insert(0, indice)
                champ.config(fg=P.PALE)

        def chercher(_e=None):
            q = champ.get().strip()
            montrer(self.page_reglages, q if q != indice and len(q) >= 2 else "")
        champ.bind("<FocusIn>", entrer)
        champ.bind("<FocusOut>", sortir)
        champ.bind("<KeyRelease>", chercher)

        def aller(cat):
            champ.delete(0, "end")
            sortir(None)
            montrer(cat)
        for nom_groupe, cats in groupes:
            tk.Label(cote, text=tr(nom_groupe), bg=cote_fond, fg=P.PALE, font=("Segoe UI", 8),
                     anchor="w").pack(fill="x", padx=18, pady=(10, 2))
            for cat, icone in cats:
                b = tk.Button(cote, text=f"{icone}   {tr(noms[cat])}", anchor="w", relief="flat", bd=0, cursor="hand2",
                              bg=cote_fond, fg=P.PALE, activebackground=P.BOUTON_ACTIF, activeforeground=P.TEXTE,
                              font=("Segoe UI", 10), padx=12, pady=4, command=lambda c=cat: aller(c))
                b.pack(fill="x", padx=8, pady=1)
                boutons_cat[cat] = b
        bas = tk.Frame(cote, bg=cote_fond)
        bas.pack(side="bottom", fill="x", padx=8, pady=10)
        Panneau.bouton(bas, "Fermer", f.destroy, cote="bottom").pack_configure(fill="x", pady=2)
        Panneau.bouton(bas, "Remettre par défaut", par_defaut, cote="bottom").pack_configure(fill="x", pady=2)
        montrer(getattr(self, "page_reglages", None) if getattr(self, "page_reglages", None) in noms else "guidage")

        # La placer à gauche du panneau, sans sortir de son écran.
        lg, ht = 820, 640
        ecran = ecran_de(self.ecrans, self.racine.winfo_rootx() + 20, self.racine.winfo_rooty() + 20) or self.ecrans[0]
        l, t, r, b = ecran["travail"]
        lg, ht = min(lg, r - l - 20), min(ht, b - t - 20)
        x = min(max(l, self.racine.winfo_rootx() - lg - 12), r - lg)
        y = min(max(t, self.racine.winfo_rooty()), b - ht - 40)
        f.geometry(f"{lg}x{ht}+{x}+{max(t, y)}")

    def appliquer_apparence(self):
        """Une nouvelle apparence (un réglage, ou Windows qui passe du clair au sombre) : la palette, le panneau,
        les bulles et les étiquettes. Rend vrai si quelque chose a changé."""
        pal = palette(self.reglages)
        if pal == self._palette:
            return False
        self._palette = pal
        Panneau.appliquer_palette(pal)
        self.panneau.peindre()
        for b in (list(self.bulles.values()) + list(self.etiquettes.values())
                  + [x for liste in self.etiquettes_lien.values() for x in liste]):
            b.peindre()
        return True

    def publier_boutons_panneau(self):
        """La place de chaque bouton visible du panneau et de la fenêtre des réglages, pour que montre.py puisse les
        montrer (--fenetre "Pigeons" --element "Réglages") : le guetteur la lit, elle est remplacée d'un bloc."""
        import tkinter as tk
        boutons = {}

        def parcourir(w, hwnd):
            for c in w.winfo_children():
                if isinstance(c, tk.Toplevel):
                    continue
                if isinstance(c, (tk.Button, tk.Menubutton, tk.Radiobutton, tk.Checkbutton)) and c.winfo_ismapped():
                    texte = str(c.cget("text")).strip().lower()
                    x, y = c.winfo_rootx(), c.winfo_rooty()
                    if texte and texte not in boutons:
                        boutons[texte] = ((x, y, x + c.winfo_width(), y + c.winfo_height()), hwnd)
                parcourir(c, hwnd)
        try:
            fenetres = [self.racine]
            if getattr(self, "fen_reglages", None) is not None and self.fen_reglages.winfo_exists():
                fenetres.insert(0, self.fen_reglages)
            for fen in fenetres:
                if fen.state() == "normal":
                    parcourir(fen, user32.GetParent(fen.winfo_id()))
        except Exception as ex:
            log.warning("boutons du panneau : %s", ex)
        self.guetteur.boutons_panneau = boutons

    def rafraichir_panneau(self):
        """Chaque seconde : les pigeons au premier plan, puis le panneau (reconstruit seulement s'il a changé)."""
        self.garder_devant()
        self.publier_boutons_panneau()
        if int(time.time()) % 5 == 0:
            self.suivre_ecrans()
        if self.reglages.get("theme") == "systeme" and int(time.time()) % 10 == 0:
            self.appliquer_apparence()                  # Windows a peut-être changé de thème
        try:
            self.panneau.rafraichir()
        except Exception:
            log.exception("panneau")
        self.racine.after(1000, self.rafraichir_panneau)

    def suivre_ecrans(self):
        """Les écrans peuvent changer pendant que les pigeons tournent (l'utilisateur, 3 octobre 2026, 23h44 : la Super
        Résolution Virtuelle d'AMD a passé l'écran de gauche de 1920 x 1080 à 2560 x 1440). Ils étaient lus une fois, au
        lancement : on les relit toutes les 5 s ; s'ils ont changé, les toiles des lignes se refont à la nouvelle taille,
        et le guetteur (qui partage la même liste) situe ses cibles sur les nouveaux écrans."""
        try:
            ecrans = lire_ecrans()
            if not ecrans or ecrans == self.ecrans:
                return
            log.info("les écrans ont changé : %s", [e["rect"] for e in ecrans])
            self.ecrans[:] = ecrans
            self.ecran_parc = next((e for e in ecrans if e["principal"]), ecrans[0])
            for v in self.voiles:
                v.detruire()
            self.voiles, self.lignes_cle = [], None
        except Exception:
            log.exception("écrans")

    def veiller_guetteur(self):
        """Toutes les 5 s, le garde-fou du guetteur (5 octobre 2026 : mort sans un mot à l'ouverture de session, il a
        laissé le registre figé plus de 40 h pendant que le panneau tournait). Figé depuis 30 s : sa pile va dans le
        journal, pour savoir où il bloque. Mort, ou figé depuis 2 min : un nouveau guetteur prend sa place (au plus un
        par 5 min) ; l'ancien, s'il se réveille, s'arrête sans rien écrire (actif est faux)."""
        g, maintenant = self.guetteur, time.time()
        try:
            fige = maintenant - g.battement
            if g.is_alive() and fige > GUETTEUR_FIGE_S and not g.signale:
                g.signale = True
                import traceback
                cadre = sys._current_frames().get(g.ident)
                pile = "".join(traceback.format_stack(cadre)) if cadre else "(pile introuvable)"
                log.error("le guetteur est figé depuis %d s ; il en est là :\n%s", fige, pile)
            if (not g.is_alive() or fige > GUETTEUR_RELANCE_S) and maintenant - self.t_relance_guetteur > 300:
                log.error("le guetteur est %s : on en relance un", "figé" if g.is_alive() else "mort")
                self.t_relance_guetteur = maintenant
                g.actif = False
                self.guetteur = Guetteur(self.partage, self.verrou, self.ecrans)
                self.guetteur.start()
        except Exception:
            log.exception("garde-fou du guetteur")
        self.racine.after(5000, self.veiller_guetteur)

    def lancer(self):
        self.racine.mainloop()


_MUTEX = None


def est_le_panneau(h):
    """Le panneau des pigeons : une fenêtre Tk (TkTopLevel) titrée « Pigeons » qui n'est pas une fenêtre outil.
    Les pigeons, les flèches et les toiles des lignes portent le même titre mais sont des fenêtres outils ; un
    Explorateur ouvert sur un dossier « Pigeons » porte aussi ce titre, mais pas cette classe."""
    return (titre_de(h) == "Pigeons" and nom_de_classe(h) == "TkTopLevel"
            and not user32.GetWindowLongW(W.HWND(h), GWL_EXSTYLE) & WS_EX_TOOLWINDOW)


def deja_lancee():
    """Une seule volée à la fois : le lancement avec Windows plus « Lancer la preuve.bat » en feraient deux.
    Un verrou nommé de Windows ; s'il existe déjà, on ramène le panneau déjà ouvert devant, et on s'arrête."""
    global _MUTEX
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\Pigeons")
    if ctypes.windll.kernel32.GetLastError() != 183:       # ERROR_ALREADY_EXISTS
        return False
    # Le panneau est une fenêtre Tk (TkTopLevel) : un Explorateur ouvert sur un dossier « Pigeons » porte le même titre.
    panneaux = [h for h in fenetres_visibles() if est_le_panneau(h)]
    if panneaux:
        h = max(panneaux, key=lambda h: (cadre_visible(h)[2] - cadre_visible(h)[0]) * (cadre_visible(h)[3] - cadre_visible(h)[1]))
        amener_devant(h)
    return True


def essai_texte():
    """Pour Claude : deux tours du guetteur sans fenêtre, puis l'état de chaque pigeon."""
    partage, verrou = {}, threading.Lock()
    g = Guetteur(partage, verrou, lire_ecrans())
    g.preparer_uia()
    g.tour(); time.sleep(0.5); g.tour()
    for e in sorted(partage.values(), key=lambda e: (e["parent"] or "", e["ident"])):
        pos = f"({e['x']}, {e['y']})" if e["x"] is not None else "-"
        qui = "  pigeonneau" if e["parent"] else "PIGEON"
        extra = f" cible={e['cible']} vers={e['vers']}" if e["mode"] == "montre" else ""
        print(f"{qui} {e['couleur']} {e['titre'][:40]!r} {e['mode']} {pos}{extra} rythme={e['rythme']} | {e['libelle']}")
        if e["bulle"]:
            print("      bulle :", e["bulle"].replace("\n", " / ")[:150])


if __name__ == "__main__":
    if "--texte" in sys.argv:
        essai_texte()
    elif deja_lancee():
        sys.exit(0)
    else:
        try:
            Volee().lancer()
        except Exception:
            log.exception("arrêt sur erreur")
            raise
