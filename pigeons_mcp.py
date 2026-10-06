"""
pigeons_mcp.py : le serveur MCP des pigeons. Il ouvre les pigeons aux outils mêmes de chaque IA.

Pourquoi (l'utilisateur, 6 octobre 2026, 08h2x : « il y a encore des coupures et des oublis d'utiliser l'app ») : jusqu'ici,
chaque IA devait se souvenir d'une ligne de commande écrite dans Desktop\\CLAUDE.md (montre.py, annonce.py). Une
session lancée ailleurs, Cowork, Antigravity ou Codex ne la voyaient pas. Branché comme serveur MCP, les pigeons
paraissent dans la liste d'outils de chaque IA, avec leur mode d'emploi : rien à retenir.

Les outils : montrer, lister, effacer, terminer, qui_travaille, annoncer, etat. Ils appellent montre.py et annonce.py
(la même logique, la même relance sûre des pigeons arrêtés ou gelés) et rendent leur réponse en texte.

Qui appelle : le serveur le sait seul.
  - Claude Code : le processus de la session a une fiche ~/.claude/sessions/<pid>.json ; on remonte nos parents
    jusqu'à elle (ou on lit CLAUDE_CODE_SESSION_ID). Le pigeon est celui de la session, comme avec montre.py.
  - Une autre IA : son nom, donné à l'ouverture (clientInfo) : Codex, Antigravity (AG), l'app Claude (Cowork).
    Chaque outil accepte aussi « session » et « titre » pour le préciser.

Le protocole : JSON-RPC 2.0 sur l'entrée et la sortie standard, un message par ligne (MCP, transport stdio). Écrit à
la main, sans dépendance, pour marcher partout où Python marche.

Brancher (le chemin complet : %USERPROFILE%\\Desktop\\Pigeons\\pigeons_mcp.py) : BRANCHER_LES_IA.md. L'app Claude
lance UN serveur pour toutes ses conversations (Cowork) et le prête aussi aux sessions Claude Code de l'app (vérifié le
6 octobre 2026 : un seul processus de pont-ag, enfant de l'app). On l'y branche donc sous le nom « pigeons-cowork »,
avec --ia cowork ; chaque session Claude Code a son propre serveur « pigeons », branché dans Claude Code même.
Essayer sans IA : python pigeons_mcp.py --essai
"""

import ctypes
import ctypes.wintypes as W
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
ACTIVITE = ICI / "activite.json"
JOURNAL = ICI / "mcp.log"
VERSION = "1.0"

CONSIGNES = (
    "Les pigeons : le système d'indication de l'utilisateur (Windows). Il voit où chaque IA travaille et guide l'utilisateur vers "
    "ce qu'elle attend de lui, par une ligne pointillée, un encadré et une balise qui dit où est la cible.\n"
    "- Quand tu as besoin d'un geste de l'utilisateur à l'écran (cliquer un bouton ou un lien, ouvrir un dossier, glisser "
    "un fichier) : dis-le dans ta réponse ET appelle « montrer ». Lis sa réponse : trouvée ou pas, et les noms proches.\n"
    "- Avant d'écrire dans un dossier partagé (un autre projet, Mon projet, un jeu) : « qui_travaille ». Occupé : n'écris pas, "
    "dis-le à l'utilisateur.\n"
    "- Si tu n'es pas Claude Code : « annoncer » le fichier où tu écris, puis « annoncer » avec fin=true à la fin.\n"
    "- À la fin de ta séance (passation faite, ou l'utilisateur ferme) : « terminer », en tout dernier.\n"
    "- Écris en clair les chemins et les liens de tes livrables : le panneau les offre à l'utilisateur."
)

# -- qui appelle

class ENTREE(ctypes.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", W.DWORD), ("cntThreads", W.DWORD),
                ("th32ParentProcessID", W.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", W.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def parents():
    """{pid: pid du parent} de tous les processus (un instantané de Windows)."""
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    cliche = k32.CreateToolhelp32Snapshot(0x2, 0)          # TH32CS_SNAPPROCESS
    liens, e = {}, ENTREE()
    e.dwSize = ctypes.sizeof(ENTREE)
    try:
        ok = k32.Process32FirstW(ctypes.c_void_p(cliche), ctypes.byref(e))
        while ok:
            liens[e.th32ProcessID] = e.th32ParentProcessID
            ok = k32.Process32NextW(ctypes.c_void_p(cliche), ctypes.byref(e))
    finally:
        k32.CloseHandle(ctypes.c_void_p(cliche))
    return liens


def session_claude_code():
    """La session Claude Code qui nous a lancés : (identifiant, nom), ou (None, None). Claude Code écrit une fiche par
    processus de session, ~/.claude/sessions/<pid>.json (sessionId, name) ; on remonte nos parents jusqu'à l'une
    d'elles. On ne lit que ces fiches .json, jamais les fichiers .key voisins."""
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if sid:
        return sid, None
    dossier = Path.home() / ".claude" / "sessions"
    try:
        liens = parents()
    except (OSError, AttributeError):
        return None, None
    pid, chaine = os.getpid(), []
    for _ in range(10):
        pid = liens.get(pid)
        if not pid:
            break
        chaine.append(pid)
    if os.environ.get("CLAUDE_PID", "").isdigit():
        chaine.append(int(os.environ["CLAUDE_PID"]))         # le processus de Claude Code, quand il le donne
    for pid in chaine:
        fiche = dossier / f"{pid}.json"
        if fiche.exists():
            try:
                d = json.loads(fiche.read_text(encoding="utf-8"))
                return d.get("sessionId"), d.get("name")
            except (OSError, ValueError):
                break
    return None, None


def ia_du_client(info):
    """(session, titre, outil) pour une IA autre que Claude Code, d'après le nom qu'elle donne à l'ouverture."""
    nom = ((info or {}).get("name") or "").lower()
    if "claude-code" in nom or "claude code" in nom:          # sa fiche de session est introuvable : un nom commun
        return "claude-code", "Claude Code", "Claude Code"
    if "codex" in nom:
        return "codex", "Codex", "Codex"
    if "antigravity" in nom or "gemini" in nom:
        return "ag", "AG", "Antigravity"
    if "claude" in nom or "cowork" in nom:                    # l'app Claude : Cowork ou une conversation
        return "cowork", "Cowork", "Cowork"
    court = "".join(c for c in nom if c.isalnum() or c in "-_")[:24] or "ia"
    return court, court, court


class Appelant:
    """Qui parle au serveur : fixé à l'ouverture (initialize). « impose » : le nom donné au lancement (--ia cowork),
    pour le serveur de l'app Claude, qui sert toutes ses conversations à la fois."""
    def __init__(self, impose=None):
        self.client, self.impose = {}, impose
        self.session, self.titre, self.outil, self.claude_code = None, None, None, False

    def ouvrir(self, info):
        self.client = info or {}
        self.session, self.titre, self.outil = ia_du_client({"name": self.impose} if self.impose else info)
        sid, nom = (None, None)
        if self.outil not in ("Codex", "Antigravity", "Cowork") and not self.impose:
            # Claude Code (ou une IA sans nom connu) : on cherche la session qui nous a lancés. Une IA qui se nomme
            # passe avant : Codex lancé depuis une session Claude Code reste Codex.
            sid, nom = session_claude_code()
        if sid:
            self.session, self.titre, self.outil, self.claude_code = sid, None, "Claude Code", True
        noter(f"ouverture : {json.dumps(self.client, ensure_ascii=False)} -> {self.outil} {self.session} {nom or ''}")

    def qui(self, args):
        """(session, titre) pour un appel : ceux donnés par l'IA, sinon ceux de l'ouverture."""
        if self.session is None:
            self.ouvrir(self.client)
        return args.get("session") or self.session, args.get("titre") or self.titre


def noter(ligne):
    """Le petit journal du serveur (mcp.log, privé) : qui s'ouvre, quels outils sont appelés. Coupé à 200 Ko."""
    try:
        if JOURNAL.exists() and JOURNAL.stat().st_size > 200_000:
            JOURNAL.write_text("", encoding="utf-8")
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {ligne}\n")
    except OSError:
        pass


# -- les outils

def lancer(script, options, delai=25):
    """Lance montre.py ou annonce.py avec ces options ; rend (texte, code de sortie)."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    env.pop("CLAUDE_CODE_SESSION_ID", None)                 # la session est toujours donnée par --session
    try:
        r = subprocess.run([sys.executable, str(ICI / script), *options], cwd=str(ICI), env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=delai,
                           creationflags=0x08000000)         # CREATE_NO_WINDOW : pas de console qui clignote
    except subprocess.TimeoutExpired:
        return f"{script} n'a pas répondu en {delai} s.", 2
    texte = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
    return texte or "(rien)", r.returncode


def cible_en_options(a, prefixe=""):
    """Les champs d'une cible (fichier, fenetre, element, onglet, point) en options de montre.py."""
    o = []
    for champ in ("fichier", "fenetre", "element", "onglet"):
        v = a.get(prefixe + champ) if not (prefixe == "vers_" and champ == "onglet") else None   # pas de --vers-onglet
        if v:
            o += [f"--{prefixe.replace('_', '-')}{champ}", str(v)]
    p = a.get(prefixe + "point")
    if p:
        o += [f"--{prefixe.replace('_', '-')}point", str(int(p[0])), str(int(p[1]))]
    return o


def montrer(a, qui):
    session, titre = qui
    o = ["--session", session, "--texte", a.get("texte") or ""]
    if titre:
        o += ["--titre", titre]
    o += cible_en_options(a)
    if a.get("page"):
        o += ["--page", *[str(v) for v in a["page"]]]
        if a.get("echelle"):
            o += ["--echelle", str(a["echelle"])]
    o += cible_en_options(a, "vers_") + cible_en_options(a, "puis_")
    if a.get("puis_texte"):
        o += ["--puis-texte", a["puis_texte"]]
    if a.get("importance"):
        o += ["--importance", a["importance"]]
    if a.get("minutes"):
        o += ["--minutes", str(a["minutes"])]
    return lancer("montre.py", o)


def lister(a, qui):
    o = ["--liste", "--fenetre", a.get("fenetre") or ""]
    if a.get("onglet"):
        o += ["--onglet", a["onglet"]]
    return lancer("montre.py", o, delai=40)


def effacer(a, qui):
    return lancer("montre.py", ["--fin", "--session", qui[0]])


def terminer(a, qui):
    return lancer("montre.py", ["--termine", "--session", qui[0]])


def qui_travaille(a, qui):
    return lancer("annonce.py", ["--qui", a.get("chemin") or "", "--session", qui[0]])


def annoncer(a, qui, appelant):
    session, titre = qui
    if appelant.claude_code and not a.get("session"):
        return ("Inutile : une session Claude Code est suivie seule, par son journal (ses lectures et ses écritures "
                "sont déjà dans le registre)."), 0
    if a.get("fin"):
        return lancer("annonce.py", ["--session", session, "--fin"])
    o = ["--session", session, "--titre", titre or session, "--ia", appelant.outil or ""]
    if a.get("fichier"):
        o += ["--fichier", a["fichier"]]
    if a.get("dossier"):
        o += ["--dossier", a["dossier"]]
    if a.get("ecrit"):
        o.append("--ecrit")
    if a.get("minutes"):
        o += ["--minutes", str(a["minutes"])]
    return lancer("annonce.py", o)


def etat(a, qui):
    """Le registre en clair : qui travaille où, ce que chaque IA attend de l'utilisateur, les conflits."""
    try:
        r = json.loads(ACTIVITE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "Pas de registre (activite.json) : les pigeons tournent-ils ? « qui_travaille » les relance au besoin.", 2
    age = time.time() - r.get("maj", 0)
    lignes = [f"Registre des pigeons, mis à jour il y a {int(age)} s" + (" (figé : les pigeons sont-ils arrêtés ?)"
                                                                        if age > 15 else "") + "."]
    for s in r.get("sessions", []):
        moi = " (toi)" if s.get("session") == qui[0] else ""
        ligne = f"- « {s.get('titre')} » ({s.get('ia')}){moi} : {s.get('etat')}"
        if s.get("fichier"):
            ligne += f", sur {s['fichier']}"
        ecrits = s.get("ecrits") or []
        if ecrits:
            ligne += f" ; a écrit {len(ecrits)} fichier(s) en 10 min, le dernier à {ecrits[-1].get('heure', '')[11:16]}"
        d = s.get("demande")
        if d:
            ligne += f" ; montre à l'utilisateur : « {d.get('texte')} » ({'trouvée' if d.get('trouvee') else 'pas trouvée'})"
        lignes.append(ligne)
    for c in r.get("conflits", []):
        lignes.append(f"! Conflit possible : {json.dumps(c, ensure_ascii=False)}")
    if len(lignes) == 1:
        lignes.append("Personne ne travaille en ce moment.")
    return "\n".join(lignes), 0


TEXTE = {"type": "string"}
CIBLE = {
    "fichier": {"type": "string", "description": "Chemin complet d'un fichier ou d'un dossier dont l'icône se voit "
                                                 "(Bureau ou dossier ouvert dans l'Explorateur)."},
    "fenetre": {"type": "string", "description": "Une partie du titre de la fenêtre (« Chrome », « Claude », "
                                                 "« Pigeons » pour le panneau des pigeons)."},
    "element": {"type": "string", "description": "Avec fenetre : une partie du nom du bouton, du lien ou de la case. "
                                                 "Le meilleur choix : il suit l'élément s'il bouge."},
    "onglet": {"type": "string", "description": "Avec fenetre, dans un navigateur : une partie du titre de l'onglet. "
                                                "Windows ne voit que la page de l'onglet affiché ; si l'onglet est "
                                                "caché, l'utilisateur y est guidé d'abord."},
    "point": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2,
              "description": "[x, y] en pixels physiques de l'écran. En dernier recours."},
}


def prefixer(p, quoi, sans=()):
    return {p + k: {**v, "description": f"{quoi} : " + v["description"]} for k, v in CIBLE.items() if k not in sans}


QUI = {"session": {"type": "string", "description": "Seulement pour une IA autre que Claude Code qui veut préciser "
                                                    "son nom (par exemple « ag-recherche »). Sinon, ne le donne pas."},
       "titre": {"type": "string", "description": "Le nom affiché dans le panneau, avec session."}}

OUTILS = [
    {"name": "montrer", "fn": montrer, "lecture": False,
     "description": "Montre à l'utilisateur un geste à faire à l'écran (cliquer, ouvrir, glisser) : une ligne pointillée part "
                    "de sa souris, un encadré épouse la cible, une balise dit où elle est (l'app, l'onglet, ce qui la "
                    "couvre). Dis aussi le geste dans ta réponse. Donne une seule cible : fichier, ou fenetre (+ element, "
                    "+ onglet), ou point. La réponse dit si la cible est trouvée, sinon pourquoi et les noms proches "
                    "(appelle « lister » pour viser juste). La demande tient jusqu'au geste, au prochain message de "
                    "l'utilisateur, ou 15 min.",
     "proprietes": {"texte": {**TEXTE, "description": "Ce que l'utilisateur doit faire, en une phrase courte, en français."},
                    **CIBLE,
                    "page": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4,
                             "description": "Avec fenetre (un navigateur) : [x, y, largeur, hauteur], le rectangle de "
                                            "getBoundingClientRect() d'un élément sans nom, en pixels CSS."},
                    "echelle": {"type": "number", "description": "Avec page : window.devicePixelRatio (1 par défaut)."},
                    **prefixer("puis_", "Une deuxième étape après la première"),
                    "puis_texte": {**TEXTE, "description": "La consigne de la deuxième étape."},
                    **prefixer("vers_", "Le point d'arrivée d'un glisser", sans=("onglet",)),
                    "importance": {"type": "string", "enum": ["haute", "normale", "basse"],
                                   "description": "haute (par défaut) : le geste bloque ton travail ; normale ; basse."},
                    "minutes": {"type": "number", "description": "Combien de temps la demande tient (15 par défaut)."},
                    **QUI},
     "requis": ["texte"]},
    {"name": "lister", "fn": lister, "lecture": True,
     "description": "Les onglets et les éléments cliquables visibles d'une fenêtre (nom, genre, place), pour choisir "
                    "un vrai nom à donner à « montrer » au lieu de deviner. Dans un navigateur, seulement la page de "
                    "l'onglet affiché.",
     "proprietes": {"fenetre": CIBLE["fenetre"], "onglet": CIBLE["onglet"]}, "requis": ["fenetre"]},
    {"name": "effacer", "fn": effacer, "lecture": False,
     "description": "Retire ta demande en cours (la ligne et l'encadré) : le geste n'est plus utile.",
     "proprietes": {**QUI}, "requis": []},
    {"name": "terminer", "fn": terminer, "lecture": False,
     "description": "Ta séance est finie (passation faite, ou l'utilisateur ferme) : ta carte, tes lignes et ton encadré "
                    "s'en vont du panneau et de l'écran. Appelle-le en tout dernier, juste avant ta dernière réponse. "
                    "Si l'utilisateur t'écrit encore, tu reviens seule.",
     "proprietes": {**QUI}, "requis": []},
    {"name": "qui_travaille", "fn": qui_travaille, "lecture": True,
     "description": "Avant d'écrire dans un fichier ou un dossier partagé : une autre IA y travaille-t-elle ? Réponse : "
                    "libre, libre avec une attention (même dossier), ou occupé (ne pas écrire : le dire à l'utilisateur). "
                    "Relance au besoin des pigeons arrêtés ou figés.",
     "proprietes": {"chemin": {**TEXTE, "description": "Chemin complet du fichier ou du dossier."}, **QUI},
     "requis": ["chemin"]},
    {"name": "annoncer", "fn": annoncer, "lecture": False,
     "description": "Pour une IA autre que Claude Code (Codex, Antigravity, Cowork) : dis aux pigeons où tu travailles, "
                    "pour que les autres IA le voient. À refaire quand tu changes de fichier (tient 10 min) ; fin=true "
                    "à la fin. Une session Claude Code n'en a pas besoin.",
     "proprietes": {"fichier": {**TEXTE, "description": "Le fichier où tu travailles (chemin complet)."},
                    "dossier": {**TEXTE, "description": "Ou le dossier (chemin complet)."},
                    "ecrit": {"type": "boolean", "description": "Vrai si tu écris ce fichier (pas seulement le lire)."},
                    "minutes": {"type": "number", "description": "Combien de temps l'annonce tient (10 par défaut)."},
                    "fin": {"type": "boolean", "description": "Vrai : tu as fini, ton annonce s'en va."},
                    **QUI},
     "requis": []},
    {"name": "etat", "fn": etat, "lecture": True,
     "description": "Le registre en clair : chaque IA au travail (Claude Code, Cowork, AG, Codex), son fichier, ses "
                    "écritures récentes, ce qu'elle montre à l'utilisateur, et les conflits possibles.",
     "proprietes": {}, "requis": []},
]


POUR_COWORK = ("Ce serveur « pigeons-cowork » sert Cowork et les conversations de l'app Claude. Une session Claude Code "
               "se sert de son propre serveur « pigeons » : il sait quelle session tu es.")


def description_des_outils(impose=None):
    avant = "(Cowork et l'app Claude ; une session Claude Code prend le serveur « pigeons ») " if impose else ""
    return [{"name": o["name"], "description": avant + o["description"],
             "inputSchema": {"type": "object", "properties": o["proprietes"], "required": o["requis"]},
             "annotations": {"readOnlyHint": o["lecture"], "destructiveHint": False, "openWorldHint": False}}
            for o in OUTILS]


# -- le protocole

def repondre(message, appelant):
    """La réponse à un message JSON-RPC, ou None pour une notification."""
    methode, ident, p = message.get("method"), message.get("id"), message.get("params") or {}
    if ident is None:
        return None                                          # une notification (initialized, cancelled...)
    if methode == "initialize":
        appelant.ouvrir(p.get("clientInfo"))
        version = p.get("protocolVersion") or "2025-06-18"   # les outils simples n'ont pas changé d'une version à l'autre
        return {"jsonrpc": "2.0", "id": ident, "result": {
            "protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "pigeons", "title": "Pigeons", "version": VERSION},
            "instructions": CONSIGNES + ("\n" + POUR_COWORK if appelant.impose else "")}}
    if methode == "ping":
        return {"jsonrpc": "2.0", "id": ident, "result": {}}
    if methode == "tools/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": description_des_outils(appelant.impose)}}
    if methode == "tools/call":
        nom, args = p.get("name"), p.get("arguments") or {}
        outil = next((o for o in OUTILS if o["name"] == nom), None)
        if not outil:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": f"outil inconnu : {nom}"}}
        qui = appelant.qui(args)
        try:
            texte, code = (outil["fn"](args, qui, appelant) if nom == "annoncer" else outil["fn"](args, qui))
        except Exception as ex:                               # une erreur ne tue jamais le serveur
            texte, code = f"Erreur dans « {nom} » : {ex!r}", 2
        noter(f"{nom} par {appelant.outil} {qui[0]} -> code {code}")
        if code == 2 and nom != "montrer":
            texte += "\n(Code 2 : je ne sais pas.)"
        return {"jsonrpc": "2.0", "id": ident, "result": {
            "content": [{"type": "text", "text": texte}], "isError": code not in (0, 1)}}
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"méthode inconnue : {methode}"}}


def option(nom):
    """La valeur d'une option de la ligne de commande (--ia cowork), ou None."""
    return sys.argv[sys.argv.index(nom) + 1] if nom in sys.argv[:-1] else None


def servir():
    entree, sortie, appelant = sys.stdin.buffer, sys.stdout.buffer, Appelant(option("--ia"))
    for ligne in entree:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            message = json.loads(ligne.decode("utf-8"))
        except ValueError:
            reponses = [{"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON illisible"}}]
        else:
            lot = message if isinstance(message, list) else [message]
            reponses = [r for r in (repondre(m, appelant) for m in lot if isinstance(m, dict)) if r]
        for r in reponses:
            sortie.write(json.dumps(r, ensure_ascii=False).encode("utf-8") + b"\n")
            sortie.flush()


def essai():
    """python pigeons_mcp.py --essai : la conversation d'une IA, sans IA (l'ouverture, la liste, l'état)."""
    appelant = Appelant()
    for m in ({"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": "essai", "version": "0"}}},
              {"jsonrpc": "2.0", "method": "notifications/initialized"},
              {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
              {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "etat", "arguments": {}}}):
        r = repondre(m, appelant)
        if r and m.get("method") == "tools/list":
            print("outils :", ", ".join(o["name"] for o in r["result"]["tools"]))
        elif r and "result" in r and "content" in r["result"]:
            print(r["result"]["content"][0]["text"])
        elif r:
            print(json.dumps(r, ensure_ascii=False)[:300])


if __name__ == "__main__":
    if "--essai" in sys.argv:
        sys.stdout.reconfigure(encoding="utf-8")
        essai()
    else:
        servir()
