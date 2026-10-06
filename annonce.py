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
  -> code de sortie 0 : libre (avec, s'il y a lieu, « attention : même dossier ») ; 1 : occupé ; 2 : je ne sais pas
     (le message dit lequel : les pigeons ne tournent pas, ou ils tournent mais leur registre est figé).

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


def pigeons_lances():
    """Le programme des pigeons tourne-t-il ? Il tient le verrou de Windows « Local\\Pigeons » tant qu'il vit.
    Un registre figé ne veut pas dire qu'il est arrêté (5 octobre 2026 : le panneau tournait, son guetteur était mort,
    et deux séances ont dit à l'utilisateur, à tort, que les pigeons ne tournaient plus). None : on ne sait pas."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.OpenMutexW.restype = ctypes.c_void_p
        h = k32.OpenMutexW(0x00100000, False, "Local\\Pigeons")          # SYNCHRONIZE : seulement regarder
    except (AttributeError, OSError):
        return None
    if h:
        k32.CloseHandle(ctypes.c_void_p(h))
        return True
    return False


ARRET = ICI / "arret_volontaire.json"            # écrit par « Arrêter » : l'utilisateur a arrêté les pigeons lui-même
AFFICHAGE = ICI / "demandes" / "_affichage.txt"  # réécrit toutes les 2 s par l'affichage (son numéro de processus)
AFFICHAGE_FIGE_S = 30
LANCEUR = ICI / "Lancer la preuve.bat"


def arretes_par_danny():
    """Quand l'utilisateur a cliqué « Arrêter » (texte), s'il a arrêté les pigeons lui-même ; sinon None."""
    try:
        return json.loads(ARRET.read_text(encoding="utf-8")).get("heure_lisible") or "?"
    except (OSError, ValueError):
        return None


def panneau_de(pid):
    """La fenêtre du panneau (TkTopLevel titrée « Pigeons ») du processus pid, ou None."""
    import ctypes
    import ctypes.wintypes as W
    u = ctypes.windll.user32
    trouve = []

    def rappel(h, _l):
        p, nom, titre = ctypes.c_ulong(), ctypes.create_unicode_buffer(64), ctypes.create_unicode_buffer(64)
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            u.GetClassNameW(h, nom, 64); u.GetWindowTextW(h, titre, 64)
            if nom.value == "TkTopLevel" and titre.value == "Pigeons":
                trouve.append(h)
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)(rappel), 0)
    return trouve[0] if trouve else None


def relancer(raison):
    """Relance le programme des pigeons, sans console, depuis son dossier ; attend qu'il tienne son verrou (10 s au
    plus). Une ligne va dans son journal, avant le lancement (le nouveau programme ouvre le journal à son tour)."""
    import subprocess
    try:
        with open(ICI / "preuve_pigeons.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},000 WARNING relance sûre par {Path(sys.argv[0]).name} : {raison}\n")
    except OSError:
        pass
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    subprocess.Popen([str(pythonw) if pythonw.exists() else "pythonw", str(ICI / "preuve_pigeons.py")], cwd=str(ICI),
                     creationflags=0x00000008 | 0x00000200, close_fds=True)   # sans console, détaché de l'appelant
    for _ in range(40):
        time.sleep(0.25)
        if pigeons_lances():
            return True
    return False


def soigner():
    """La relance sûre (5 octobre 2026, 22h39 : l'affichage a gelé pendant la mise à jour de l'app Claude ; Windows a
    fermé le programme, et une séance ne l'a su qu'à 22h43). Arrêtés sans que l'utilisateur ait cliqué « Arrêter » : on les
    relance. Lancés mais l'affichage gelé depuis 30 s (Windows le dit « ne répond pas ») : on ferme ce processus-là, et
    on relance. Rend une phrase pour l'IA qui appelle (vide si tout va bien)."""
    lances = pigeons_lances()
    if lances is None:
        return ""
    if not lances:
        quand = arretes_par_danny()
        if quand:
            return (f"l'utilisateur a arrêté les pigeons lui-même (« Arrêter », {quand}) : je ne les relance pas. Dis-le-lui ; "
                    f"il les relance par {LANCEUR}.")
        if relancer("ils ne tournaient pas"):
            return "Les pigeons ne tournaient pas : je les ai relancés."
        return f"Les pigeons ne tournent pas, et la relance a échoué : l'utilisateur peut les lancer par {LANCEUR}."
    try:
        age = time.time() - AFFICHAGE.stat().st_mtime
        pid = int(AFFICHAGE.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return ""                                 # une version d'avant le battement : rien à dire
    if age < AFFICHAGE_FIGE_S or not pid:
        return ""
    import ctypes
    panneau = panneau_de(pid)
    if not panneau or not ctypes.windll.user32.IsHungAppWindow(panneau):
        # Pas gelé pour Windows (l'ordinateur sortait de veille, ou l'affichage ne dessine plus sans être bloqué).
        return f"L'affichage des pigeons n'a rien dessiné depuis {int(age)} s ; le journal dit pourquoi (preuve_pigeons.log)."
    import subprocess
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    for _ in range(20):
        time.sleep(0.25)
        if not pigeons_lances():
            break
    if relancer(f"affichage gelé depuis {int(age)} s (processus {pid} fermé)"):
        return f"L'affichage des pigeons était gelé depuis {int(age)} s : je l'ai fermé et relancé."
    return f"L'affichage des pigeons était gelé, et la relance a échoué : l'utilisateur peut les lancer par {LANCEUR}."


def pourquoi_pas_a_jour(depuis):
    """La raison, en clair, quand le registre manque ou n'est plus à jour : arrêtés, ou lancés mais figés."""
    lances, lanceur = pigeons_lances(), ICI / "Lancer la preuve.bat"
    if lances:
        return (f"les pigeons tournent, mais leur registre est figé{depuis} (leur guetteur ne fait plus son tour ; "
                f"ils le relancent seuls en 2 min, sinon l'utilisateur les relance : « Arrêter », puis {lanceur})")
    if lances is False:
        return f"les pigeons ne tournent pas{depuis} (l'utilisateur peut les lancer : {lanceur})"
    return f"le registre n'est plus à jour{depuis} (les pigeons tournent-ils ?)"


def qui(chemin, moi):
    """Qui travaille sur ce fichier ou dans ce dossier, d'après le registre des pigeons."""
    soin = soigner()                      # arrêtés ou gelés sans que l'utilisateur l'ait voulu : relancés d'abord
    if soin:
        print(soin)
        for _ in range(16):               # un registre neuf vient 2 à 4 s après une relance
            if ACTIVITE.exists() and time.time() - ACTIVITE.stat().st_mtime < 3:
                break
            time.sleep(0.5)
    try:
        registre = json.loads(ACTIVITE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("Je ne sais pas : pas de registre activite.json ;", pourquoi_pas_a_jour("") + ".")
        return 2
    if time.time() - registre.get("maj", 0) > 15:
        maj = registre.get("maj_lisible", "")
        depuis = f" depuis le {maj[:10]} à {maj[11:16]}" if len(maj) >= 16 else ""
        print("Je ne sais pas :", pourquoi_pas_a_jour(depuis) + ".")
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
