"""
annonce.py : pour qu'une IA dise aux pigeons où elle travaille, et demande qui travaille déjà quelque part.

Pourquoi (l'utilisateur, 3 octobre 2026, 09h12) : coordonner les sessions et les IA (Claude Code, Antigravity, Cowork, un
script), pour éviter que deux d'entre elles écrivent le même fichier en même temps. Les sessions Claude Code sont
suivies seules, par leur journal ; les autres IA s'annoncent avec cette commande.

S'annoncer (à refaire quand on change de fichier ; l'annonce tient 10 min, ou --minutes) :
  python annonce.py --session ag --titre "AG" --fichier "C:\\...\\IDEES.md" --ecrit
  python annonce.py --session ag --titre "AG" --dossier "%USERPROFILE%\\Desktop\\Pigeons"
  python annonce.py --session ag --fin
Demander avant d'écrire (lit activite.json, que les pigeons écrivent toutes les 2 s) :
  python annonce.py --qui "C:\\...\\IDEES.md" --session ag
  -> code de sortie 0 : libre (avec, s'il y a lieu, « attention : même dossier ») ; 1 : occupé ; 2 : je ne sais pas.

Où lire la suite : MANUEL.md (ou MANUAL.md), section 5.4.
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
ANNONCES = ICI / "annonces"
ACTIVITE = ICI / "activite.json"


def norme(chemin):
    return os.path.normcase(os.path.abspath(chemin)) if chemin else ""


def qui(chemin, moi):
    """Qui travaille sur ce fichier ou dans ce dossier, d'après le registre des pigeons."""
    try:
        registre = json.loads(ACTIVITE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("Je ne sais pas : le registre activite.json est absent (les pigeons tournent-ils ?).")
        return 2
    if time.time() - registre.get("maj", 0) > 15:
        print("Je ne sais pas : le registre n'est plus à jour (les pigeons ne tournent plus).")
        return 2
    cible = norme(chemin)
    occupe, voisins = [], []
    for s in registre.get("sessions", []):
        if s.get("session") == moi:
            continue
        nom = f"« {s.get('titre')} » ({s.get('ia')})"
        ecrits = [norme(e["fichier"]) for e in s.get("ecrits", [])]
        fichier = norme(s.get("fichier"))
        if cible and (cible == fichier or cible in ecrits
                      or (os.path.isdir(chemin) and (fichier.startswith(cible + os.sep) or
                                                     any(e.startswith(cible + os.sep) for e in ecrits)))):
            ecrit = next((e["heure"][11:16] for e in s.get("ecrits", []) if norme(e["fichier"]) == cible), None)
            occupe.append(f"{nom} : a écrit ce fichier à {ecrit}" if ecrit else f"{nom} : {s.get('etat')}, sur "
                          f"{s.get('fichier')}")
        elif s.get("dossier") and cible.startswith(norme(s["dossier"]) + os.sep) and s.get("etat") == "travaille":
            voisins.append(f"{nom} travaille dans le même dossier ({s.get('fichier')})")
    if occupe:
        print("Occupé :")
        for ligne in occupe:
            print("  " + ligne)
        return 1
    if voisins:
        print("Libre, mais attention :")
        for ligne in voisins:
            print("  " + ligne)
        return 0
    print("Libre : personne d'autre ne travaille ici.")
    return 0


def main():
    a = argparse.ArgumentParser(description="Dire aux pigeons où une IA travaille, ou demander qui travaille quelque part.")
    a.add_argument("--session", help="le nom de l'IA (par exemple ag) ; par défaut, la session Claude Code qui lance")
    a.add_argument("--titre", help="le nom affiché (par exemple « AG »)")
    a.add_argument("--ia", default="", help="le nom de l'outil (Antigravity, Cowork, script...)")
    a.add_argument("--fichier")
    a.add_argument("--dossier")
    a.add_argument("--ecrit", action="store_true", help="l'IA écrit ce fichier (pas seulement le lit)")
    a.add_argument("--minutes", type=float, default=10, help="combien de temps l'annonce tient (10 par défaut)")
    a.add_argument("--fin", action="store_true", help="l'IA a fini : son annonce s'en va")
    a.add_argument("--qui", metavar="CHEMIN", help="qui travaille sur ce fichier ou dans ce dossier ?")
    arg = a.parse_args()
    session = arg.session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if arg.qui:
        sys.exit(qui(arg.qui, session))
    if not session:
        sys.exit("Donne --session (le nom de l'IA, par exemple ag).")
    ANNONCES.mkdir(exist_ok=True)
    fichier = ANNONCES / f"{session}.json"
    if arg.fin:
        fichier.unlink(missing_ok=True)
        print("Annonce retirée.")
        return
    if not (arg.fichier or arg.dossier):
        sys.exit("Dis où tu travailles : --fichier CHEMIN ou --dossier CHEMIN.")
    annonce = {"session": session, "titre": arg.titre or session, "ia": arg.ia or (arg.titre or session),
               "fichier": os.path.abspath(arg.fichier) if arg.fichier else None,
               "dossier": os.path.abspath(arg.dossier) if arg.dossier else None,
               "ecrit": arg.ecrit, "heure": time.time(), "duree_s": int(arg.minutes * 60)}
    provisoire = fichier.with_suffix(".tmp")
    provisoire.write_text(json.dumps(annonce, ensure_ascii=False), encoding="utf-8")
    os.replace(provisoire, fichier)          # les pigeons ne lisent jamais une annonce à moitié écrite
    print("Annonce envoyée :", annonce["fichier"] or annonce["dossier"], "(écrit)" if arg.ecrit else "")


if __name__ == "__main__":
    main()
