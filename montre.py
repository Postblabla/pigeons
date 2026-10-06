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
  python montre.py --fenetre "Chrome" --onglet "Gemini" --element "Envoyer" --texte "Envoie ta fiche"
  python montre.py --fenetre "Chrome" --onglet "Gemini" --page 812 640 64 32 --echelle 1.25 --texte "Clique ici"
  python montre.py --liste --fenetre "Chrome" --onglet "Gemini"
  python montre.py --fichier "C:\\...\\photo.png" --vers-fichier "C:\\...\\Images" --texte "Glisse la photo dans Images"
  python montre.py --fin
  python montre.py --termine

--fenetre : une partie du titre de la fenêtre ; --element : une partie du nom du bouton,
du lien ou de la case (lu par l'automatisation de Windows). --point : en pixels physiques.
La demande tient jusqu'au prochain message de l'utilisateur dans la session, --fin, ou --minutes (15).

--onglet (5 octobre 2026) : l'automatisation de Windows ne voit que la page de l'onglet AFFICHÉ d'un navigateur ;
avec --onglet, si cet onglet est caché, le guidage montre d'abord l'onglet, puis la cible. --page X Y L H : le
rectangle de getBoundingClientRect() d'un élément sans nom (en pixels CSS), --echelle = window.devicePixelRatio ;
préfère --element : il suit le bouton s'il bouge. --dans « Chrome » (avec --point) : si une autre fenêtre couvre le
point, on ramène d'abord Chrome devant. --liste : les éléments cliquables visibles d'une fenêtre, pour viser juste.

La réponse (5 octobre 2026) : montre.py attend le guetteur (5 s au plus) et dit si la cible est trouvée, où (l'app,
l'onglet, l'écran), et sinon pourquoi, avec les noms proches. Code de sortie : 0 trouvée, 1 pas trouvée, 2 je ne sais
pas. Si les pigeons sont arrêtés (sans que l'utilisateur ait cliqué « Arrêter ») ou gelés, il les relance d'abord.

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

from annonce import pigeons_lances, soigner   # le verrou « Local\Pigeons » ; la relance sûre (5 octobre 2026)

# Une IA lit la réponse par un tuyau : en UTF-8, sinon les accents arrivent en « ? » (rapport d'AG, 3 octobre).
if not sys.stdout.isatty():
    sys.stdout.reconfigure(encoding="utf-8")

ICI = Path(__file__).resolve().parent
DEMANDES = ICI / "demandes"
FERMETURES = ICI / "fermetures"
ACTIVITE = ICI / "activite.json"


def cible(fichier, fenetre, element, point, quoi, onglet=None, page=None, echelle=None, dans=None):
    """Une cible au format que lit le programme des pigeons ; arrête avec un message clair si elle est fausse."""
    if fichier:
        chemin = os.path.abspath(fichier)
        if not os.path.exists(chemin):
            sys.exit(f"{quoi} : le fichier n'existe pas : {chemin}")
        return {"fichier": chemin}
    if page and not fenetre:
        fenetre = "Chrome"
    if fenetre:
        c = {"fenetre": fenetre, "element": element}
        if onglet:
            c["onglet"] = onglet
        if page:
            c["page"] = [float(v) for v in page]
            c["echelle"] = echelle or 1.0
        return c
    if point:
        return {"point": [int(point[0]), int(point[1])], **({"dans": dans} if dans else {})}
    return None


def lister(fenetre, onglet=None):
    """--liste : les éléments cliquables visibles des fenêtres dont le titre contient « fenetre » (l'idée de l'outil
    « Snapshot » de Windows-MCP, licence MIT), pour qu'une IA choisisse un vrai nom au lieu de deviner."""
    import ctypes
    import ctypes.wintypes as W
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))     # des pixels physiques
    import comtypes
    import comtypes.client
    comtypes.CoInitializeEx(comtypes.COINIT_APARTMENTTHREADED)
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen import UIAutomationClient as U
    uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
    genres = {50000: "bouton", 50031: "bouton", 50005: "lien", 50019: "onglet", 50007: "élément", 50024: "élément",
              50011: "menu", 50002: "case", 50013: "option", 50004: "zone de texte", 50003: "liste"}
    u32, trouvees = ctypes.windll.user32, []

    def rappel(h, _l):
        n = u32.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, b, n + 1)
        if u32.IsWindowVisible(h) and n and fenetre.casefold() in b.value.casefold():
            trouvees.append((h, b.value))
        return True
    u32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, W.HWND, W.LPARAM)(rappel), 0)
    if not trouvees:
        print(f"Aucune fenêtre ouverte dont le titre contient « {fenetre} ».")
        return 1
    cache = uia.CreateCacheRequest()
    for prop in (U.UIA_NamePropertyId, U.UIA_ControlTypePropertyId, U.UIA_BoundingRectanglePropertyId,
                 U.UIA_IsOffscreenPropertyId):
        cache.AddProperty(prop)
    cond = None
    for g in genres:
        c = uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, g)
        cond = c if cond is None else uia.CreateOrCondition(cond, c)
    for h, titre in trouvees[:3]:
        print(f"== {titre}")
        racine = uia.ElementFromHandle(W.HWND(h))
        # Les onglets d'abord (un navigateur) : leur nom sert à --onglet, et on voit lequel est affiché.
        onglets = racine.FindAll(U.TreeScope_Descendants,
                                 uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_TabItemControlTypeId))
        for i in range(min(onglets.Length, 60)):
            o = onglets.GetElement(i)
            nom = " ".join((o.CurrentName or "").split())
            if onglet and onglet.casefold() not in nom.casefold():
                continue
            motif = o.GetCurrentPattern(U.UIA_SelectionItemPatternId)
            choisi = motif and motif.QueryInterface(U.IUIAutomationSelectionItemPattern).CurrentIsSelected
            print(f"  onglet « {nom[:60]} »" + ("  ← affiché" if choisi else ""))
        tab = racine.FindAllBuildCache(U.TreeScope_Descendants, cond, cache)
        vus, n = set(), 0
        for i in range(tab.Length):
            it = tab.GetElement(i)
            nom = " ".join((it.CachedName or "").split())          # sur une ligne
            g = genres.get(it.CachedControlType, "?")
            if not nom or g == "onglet" or it.CachedIsOffscreen or (nom, g) in vus:
                continue
            vus.add((nom, g))
            r = it.CachedBoundingRectangle
            print(f"  {g} « {nom[:60]} »  ({(r.left + r.right) // 2}, {(r.top + r.bottom) // 2})")
            n += 1
            if n >= 150:
                print("  (la suite est coupée : 150 au plus)")
                break
    print("La page d'un navigateur : seulement celle de l'onglet affiché. Vise avec --element (une partie du nom).")
    return 0


def attendre_reponse(session, cree, delai=5.0):
    """Ce que le guetteur a fait de CETTE demande (sa clé : l'heure de la demande) : le registre activite.json est
    réécrit toutes les 2 s. Rend la demande vue par le guetteur, ou None."""
    fin = time.time() + delai
    while time.time() < fin:
        time.sleep(0.4)
        try:
            registre = json.loads(ACTIVITE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for s in registre.get("sessions", []):
            d = s.get("demande") or {}
            if s.get("session") == session and d.get("cree") and abs(d["cree"] - cree) < 0.01:
                return d
    return None


def dire_reponse(d):
    """La réponse en clair pour l'IA : trouvée, où ; sinon pourquoi, et les noms proches."""
    ou = d.get("ou") or {}
    fil = " › ".join(x for x in (ou.get("app"), ou.get("lieu"), ou.get("element")) if x)
    if d.get("trouvee"):
        print("Trouvée :", fil or "oui", f"({ou['ecran']})" if ou.get("ecran") else "", f"au point {d.get('point')}")
        if ou.get("etape1"):
            obstacle = (ou.get("obstacle") or {}).get("app")
            print(f"  l'utilisateur passe d'abord par une étape : {ou['etape1']}" + (f" (sous « {obstacle} »)" if obstacle else ""))
        if ou.get("defiler"):
            print(f"  La cible est hors de la vue : l'utilisateur doit faire défiler {ou['defiler']}.")
        return 0
    print("Pas trouvée :", d.get("precision") or "?")
    if ou.get("proches"):
        print("  Essaie un de ces noms avec --element :", ", ".join(f"« {x} »" for x in ou["proches"]))
    return 1


def main():
    a = argparse.ArgumentParser(description="Le pigeon de ta session montre un endroit à l'utilisateur.")
    a.add_argument("--texte", help="ce que l'utilisateur doit faire, en une phrase")
    a.add_argument("--fichier"); a.add_argument("--fenetre"); a.add_argument("--element")
    a.add_argument("--point", nargs=2, type=int, metavar=("X", "Y"))
    a.add_argument("--onglet", help="l'onglet du navigateur où est la cible (une partie de son titre)")
    a.add_argument("--page", nargs=4, type=float, metavar=("X", "Y", "L", "H"),
                   help="le rectangle d'un élément dans la page (getBoundingClientRect, pixels CSS)")
    a.add_argument("--echelle", type=float, help="window.devicePixelRatio de la page (1 par défaut)")
    a.add_argument("--dans", help="avec --point : la fenêtre qui doit être sous le point (une partie de son titre)")
    a.add_argument("--liste", action="store_true", help="les éléments cliquables visibles de --fenetre, puis rien d'autre")
    a.add_argument("--sans-attendre", action="store_true", help="ne pas attendre la réponse du guetteur")
    a.add_argument("--vers-fichier"); a.add_argument("--vers-fenetre"); a.add_argument("--vers-element")
    a.add_argument("--vers-point", nargs=2, type=int, metavar=("X", "Y"))
    # Une deuxième étape (l'utilisateur, 12h12) : « clique ici, puis là ». Le pointillé va de la souris à l'étape 1, puis de
    # l'étape 1 à l'étape 2 ; le clic sur l'étape 1 fait passer le guidage à l'étape 2.
    a.add_argument("--puis-fichier"); a.add_argument("--puis-fenetre"); a.add_argument("--puis-element")
    a.add_argument("--puis-point", nargs=2, type=int, metavar=("X", "Y"))
    a.add_argument("--puis-onglet")
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
    if arg.liste:
        if not arg.fenetre:
            sys.exit("--liste a besoin de --fenetre (une partie du titre de la fenêtre).")
        sys.exit(lister(arg.fenetre, arg.onglet))
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

    c = cible(arg.fichier, arg.fenetre, arg.element, arg.point, "--fichier", arg.onglet, arg.page, arg.echelle, arg.dans)
    if not c:
        sys.exit("Dis au pigeon quoi montrer : --fichier, --fenetre (et --element) ou --point.")
    v = cible(arg.vers_fichier, arg.vers_fenetre, arg.vers_element, arg.vers_point, "--vers-fichier")
    puis = cible(arg.puis_fichier, arg.puis_fenetre, arg.puis_element, arg.puis_point, "--puis-fichier",
                 arg.puis_onglet)
    demande = {"session": arg.session, "heure": time.time(), "duree_s": int(arg.minutes * 60),
               "texte": arg.texte or "", "cible": c, "vers": v, "titre": arg.titre, "importance": arg.importance,
               "puis": puis, "texte_puis": arg.puis_texte or ""}
    soin = soigner()                         # arrêtés ou gelés sans que l'utilisateur l'ait voulu : relancés d'abord
    if soin:
        print(soin)
    provisoire = fichier.with_suffix(".tmp")
    provisoire.write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
    os.replace(provisoire, fichier)          # le programme ne lit jamais une demande à moitié écrite

    vivant = DEMANDES / "_vivant.txt"
    en_vol = vivant.exists() and time.time() - vivant.stat().st_mtime < 10
    print("Demande envoyée au pigeon :", json.dumps({"cible": c, "vers": v, "texte": arg.texte}, ensure_ascii=False))
    if not en_vol:
        # Arrêtés, ou lancés mais figés : ce n'est pas la même panne (5 octobre 2026 ; voir annonce.pigeons_lances).
        depuis = time.strftime(" depuis le %Y-%m-%d à %H:%M", time.localtime(vivant.stat().st_mtime)) if vivant.exists() else ""
        lanceur = ICI / "Lancer la preuve.bat"
        if pigeons_lances():
            print(f"Attention : le programme des pigeons tourne, mais son guetteur est figé{depuis} : ta demande ne sera "
                  f"pas montrée tant qu'il ne repart pas. Il se relance seul en 2 min ; sinon, l'utilisateur le relance "
                  f"(« Arrêter », puis {lanceur}).")
        else:
            print(f"Attention : le programme des pigeons ne tourne pas. l'utilisateur peut le lancer : {lanceur}")
        sys.exit(2)
    if arg.sans_attendre:
        return
    d = attendre_reponse(arg.session, demande["heure"])
    if d is None:
        print("Je ne sais pas encore si la cible est trouvée (pas de réponse du guetteur en 5 s) : regarde "
              f"{ACTIVITE}, ta session, « demande ».")
        sys.exit(2)
    sys.exit(dire_reponse(d))


if __name__ == "__main__":
    main()
