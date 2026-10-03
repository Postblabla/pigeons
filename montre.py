"""
montre.py : demande au pigeon de ta session de MONTRER un endroit à l'utilisateur, à l'écran.

Qui s'en sert : une session Claude qui a besoin d'un geste de l'utilisateur (cliquer un lien
ou un bouton, ouvrir un dossier, glisser un fichier). Le pigeon de la session vole
jusqu'à l'endroit, une flèche qui sautille pointe l'endroit exact, une bulle dit quoi
faire, et une petite flèche près de la souris de l'utilisateur indique la direction quand
c'est loin. Pour un glisser, le pigeon refait le trajet de A vers B, et un anneau
marque B.

Exemples (le chemin complet : %USERPROFILE%\\Desktop\\Pigeons\\montre.py) :
  python montre.py --fichier "%USERPROFILE%\\Desktop\\Mon projet" --texte "Ouvre ce dossier"
  python montre.py --fenetre "Chrome" --element "Accepter" --texte "Clique sur Accepter"
  python montre.py --point 1200 540 --texte "Clique ici"
  python montre.py --fichier "C:\\...\\photo.png" --vers-fichier "C:\\...\\Images" --texte "Glisse la photo dans Images"
  python montre.py --fin
  python montre.py --termine

--fenetre : une partie du titre de la fenêtre ; --element : une partie du nom du bouton,
du lien ou de la case (lu par l'automatisation de Windows). --point : en pixels physiques.
La demande tient jusqu'au prochain message de l'utilisateur dans la session, --fin, ou --minutes (15).

--termine (2 octobre 2026, après-midi) : la séance est finie (passation faite, ou l'utilisateur ferme). Le pigeon, la carte
et les lignes de la session s'en vont. À lancer en tout dernier, juste avant la dernière réponse : si la session
relance un outil plus de 2 min après, ou si l'utilisateur lui écrit, elle revient.

Où lire la suite : MANUEL.md, section « Le pigeon qui montre ».
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Une IA lit la réponse par un tuyau : en UTF-8, sinon les accents arrivent en « ? » (rapport d'AG, 3 octobre).
if not sys.stdout.isatty():
    sys.stdout.reconfigure(encoding="utf-8")

ICI = Path(__file__).resolve().parent
DEMANDES = ICI / "demandes"
FERMETURES = ICI / "fermetures"


def cible(fichier, fenetre, element, point, quoi):
    """Une cible au format que lit le programme des pigeons ; arrête avec un message clair si elle est fausse."""
    if fichier:
        chemin = os.path.abspath(fichier)
        if not os.path.exists(chemin):
            sys.exit(f"{quoi} : le fichier n'existe pas : {chemin}")
        return {"fichier": chemin}
    if fenetre:
        return {"fenetre": fenetre, "element": element}
    if point:
        return {"point": [int(point[0]), int(point[1])]}
    return None


def main():
    a = argparse.ArgumentParser(description="Le pigeon de ta session montre un endroit à l'utilisateur.")
    a.add_argument("--texte", help="ce que l'utilisateur doit faire, en une phrase")
    a.add_argument("--fichier"); a.add_argument("--fenetre"); a.add_argument("--element")
    a.add_argument("--point", nargs=2, type=int, metavar=("X", "Y"))
    a.add_argument("--vers-fichier"); a.add_argument("--vers-fenetre"); a.add_argument("--vers-element")
    a.add_argument("--vers-point", nargs=2, type=int, metavar=("X", "Y"))
    # Une deuxième étape (l'utilisateur, 12h12) : « clique ici, puis là ». Le pointillé va de la souris à l'étape 1, puis de
    # l'étape 1 à l'étape 2 ; le clic sur l'étape 1 fait passer le guidage à l'étape 2.
    a.add_argument("--puis-fichier"); a.add_argument("--puis-fenetre"); a.add_argument("--puis-element")
    a.add_argument("--puis-point", nargs=2, type=int, metavar=("X", "Y"))
    a.add_argument("--puis-texte", help="la consigne de l'étape 2")
    a.add_argument("--minutes", type=float, default=15)
    a.add_argument("--fin", action="store_true", help="le pigeon arrête de montrer")
    a.add_argument("--termine", action="store_true",
                   help="la séance est finie : le pigeon, la carte et les lignes de la session s'en vont "
                        "(en tout dernier, juste avant ta dernière réponse)")
    a.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID"),
                   help="la session dont le pigeon montre (par défaut : celle qui lance la commande) ; "
                        "une autre IA donne son nom, par exemple --session cowork")
    a.add_argument("--titre", help="le nom affiché du pigeon, pour une autre IA (par exemple « Cowork »)")
    a.add_argument("--importance", choices=["haute", "normale", "basse"], default="haute",
                   help="haute : un geste qui bloque le travail (par défaut) ; normale ; basse : quand l'utilisateur veut")
    arg = a.parse_args()
    if not arg.session:
        sys.exit("Je ne sais pas quelle session appelle : lance montre.py depuis une session Claude Code, ou donne --session.")

    DEMANDES.mkdir(exist_ok=True)
    fichier = DEMANDES / f"{arg.session}.json"
    if arg.termine:
        FERMETURES.mkdir(exist_ok=True)
        fermeture = FERMETURES / f"{arg.session}.json"
        provisoire = fermeture.with_suffix(".tmp")
        provisoire.write_text(json.dumps({"session": arg.session, "heure": time.time(), "par": "session"}),
                              encoding="utf-8")
        os.replace(provisoire, fermeture)
        fichier.unlink(missing_ok=True)          # une demande encore ouverte s'en va avec elle
        print("Séance notée finie : le pigeon, la carte et les lignes de cette session s'en vont. "
              "Elle revient si l'utilisateur lui écrit.")
        return
    if arg.fin:
        fichier.unlink(missing_ok=True)
        print("Le pigeon arrête de montrer.")
        return

    c = cible(arg.fichier, arg.fenetre, arg.element, arg.point, "--fichier")
    if not c:
        sys.exit("Dis au pigeon quoi montrer : --fichier, --fenetre (et --element) ou --point.")
    v = cible(arg.vers_fichier, arg.vers_fenetre, arg.vers_element, arg.vers_point, "--vers-fichier")
    puis = cible(arg.puis_fichier, arg.puis_fenetre, arg.puis_element, arg.puis_point, "--puis-fichier")
    demande = {"session": arg.session, "heure": time.time(), "duree_s": int(arg.minutes * 60),
               "texte": arg.texte or "", "cible": c, "vers": v, "titre": arg.titre, "importance": arg.importance,
               "puis": puis, "texte_puis": arg.puis_texte or ""}
    provisoire = fichier.with_suffix(".tmp")
    provisoire.write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
    os.replace(provisoire, fichier)          # le programme ne lit jamais une demande à moitié écrite

    vivant = DEMANDES / "_vivant.txt"
    en_vol = vivant.exists() and time.time() - vivant.stat().st_mtime < 10
    print("Demande envoyée au pigeon :", json.dumps({"cible": c, "vers": v, "texte": arg.texte}, ensure_ascii=False))
    if not en_vol:
        print("Attention : le programme des pigeons ne tourne pas. l'utilisateur peut le lancer : "
              "%USERPROFILE%\\Desktop\\Pigeons\\Lancer la preuve.bat")


if __name__ == "__main__":
    main()
