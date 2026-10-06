"""
crochet_fin_de_tour.py : le garde-fou des pigeons, un crochet « Stop » de Claude Code. Quand une session finit son tour
en demandant un geste à l'utilisateur à l'écran (« Clique sur… », « Ouvre le dossier… », « Glisse… ») sans le lui avoir
montré pendant ce tour (l'outil « montrer » du serveur pigeons, ou montre.py), il la renvoie le faire, une seule fois.

Pourquoi (l'utilisateur, 6 octobre 2026, 08h2x : « des oublis d'utiliser l'app ») : mesuré le même matin dans les journaux,
le plus souvent un geste était demandé dans le texte sans que le pigeon le montre. La règle de Desktop\\CLAUDE.md ne
suffit pas : il faut un rappel au moment même où l'oubli se produit.

Ce qu'il ne fait pas : renvoyer deux fois de suite (stop_hook_active : la deuxième fin de tour passe toujours) ;
juger un geste écrit dans un bloc de code ou une citation ; bloquer quand les pigeons ne tournent pas. Toute erreur :
il se tait. La session garde le dernier mot : si ce n'était pas un geste à l'écran, elle finit son tour sans rien
changer.

Entrée (stdin) : {"session_id", "transcript_path", "stop_hook_active", "last_assistant_message", ...}.
Sortie pour renvoyer : {"decision": "block", "reason": "..."} (format vérifié dans la documentation de Claude Code le
6 octobre 2026).
Mesurer sur les vieux journaux : python crochet_fin_de_tour.py --mesure
"""

import json
import os
import re
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
ACTIVITE = ICI / "activite.json"

# Un geste demandé à l'utilisateur : un impératif en tête de ligne ou de phrase (après une puce, un numéro, du gras, ou
# « Ton geste : »). « Ouvre » seul est trop courant dans les descriptions : il faut « ouvre le dossier », « l'onglet »...
VERBES = (r"(?:Double-clique|Clique|Glisse|Fais glisser|Dépose|Colle|Appuie sur|Coche|Décoche|Sélectionne|"
          r"Ouvre (?:le|la|les|l'|ton|ta|tes|une|un)\b|Ferme (?:le|la|l'|ton|ta)\b|Lance (?:le|la|l'|ton|ta)\b|"
          r"Redémarre|Relance (?:le|la|l'|ton|ta|les)\b|Va dans|Choisis|Approuve|Accepte|Autorise)")
RE_GESTE = re.compile(r"(?:^|(?<=[.!?:]\s)|(?<=\*\*Ton geste\*\*\s:\s)|(?<=Ton geste\s:\s))"
                      r"[\s>*_•\-\d.)]*(?:\*\*)?" + VERBES + r"\b[^\n]{0,140}", re.M)
RE_TON_GESTE = re.compile(r"\bTon geste\**\s*:\s*\**\s*([^\n]{3,140})", re.I)    # « **Ton geste** : clique… »
RE_BLOC = re.compile(r"```.*?```", re.S)
RE_CODE = re.compile(r"`[^`\n]*`")


def geste_demande(texte):
    """La phrase qui demande un geste à l'utilisateur, ou None. Les blocs de code et les citations (>) ne comptent pas."""
    if not texte:
        return None
    t = RE_BLOC.sub("", texte)
    t = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith(">"))
    t = RE_CODE.sub("…", t)
    m = RE_GESTE.search(t)
    if m:
        return " ".join(m.group(0).split()).strip("*•- ")
    m = RE_TON_GESTE.search(t)
    return " ".join(m.group(1).split()).strip("*•- ") if m else None


RE_APPEL_MONTRE = re.compile(r"montre\.py[\"']?\s+--(?!liste|fin\b|help)")


def appel_de_montre(x):
    """Un appel d'outil qui montre vraiment un geste : l'outil « montrer » (ou « terminer ») du serveur pigeons, ou une
    commande qui lance montre.py (pas un fichier qu'on écrit et qui en parle, pas --liste ni --fin)."""
    nom = x.get("name") or ""
    if "pigeons" in nom and nom.endswith(("montrer", "terminer")):
        return True
    commande = (x.get("input") or {}).get("command") if nom in ("Bash", "PowerShell") else None
    return bool(commande and RE_APPEL_MONTRE.search(commande))


def montre_pendant_le_tour(chemin_journal, session=None):
    """La session a-t-elle montré un geste (montre.py, ou l'outil « montrer » du serveur pigeons) depuis le dernier
    message de l'utilisateur ? On lit la fin du journal, à rebours."""
    try:
        with open(chemin_journal, "rb") as f:
            f.seek(0, 2)
            taille = f.tell()
            f.seek(max(0, taille - 600_000))
            lignes = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return True                            # dans le doute, on ne renvoie pas
    for l in reversed(lignes):
        try:
            d = json.loads(l)
        except ValueError:
            continue
        m = d.get("message") or {}
        contenu = m.get("content")
        if d.get("type") == "user" and not d.get("isSidechain"):
            if isinstance(contenu, str) or (isinstance(contenu, list) and any(
                    isinstance(x, dict) and x.get("type") == "text" for x in contenu)):
                return False                   # le message de l'utilisateur : rien montré depuis
        if d.get("type") == "assistant" and isinstance(contenu, list):
            for x in contenu:
                if isinstance(x, dict) and x.get("type") == "tool_use" and appel_de_montre(x):
                    return True
    return False


def pigeons_en_marche():
    try:
        return time.time() - json.loads(ACTIVITE.read_text(encoding="utf-8")).get("maj", 0) < 30
    except (OSError, ValueError):
        return False


def main():
    entree = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    if entree.get("stop_hook_active"):
        return                                 # déjà renvoyée une fois : elle finit son tour
    phrase = geste_demande(entree.get("last_assistant_message"))
    if not phrase or not pigeons_en_marche():
        return
    if montre_pendant_le_tour(entree.get("transcript_path") or ""):
        return
    raison = (f"Les pigeons : ta réponse demande un geste à l'utilisateur (« {phrase[:120]} ») sans le lui montrer. "
              "Montre-le maintenant : l'outil « montrer » du serveur MCP pigeons, sinon python "
              f"\"{ICI / 'montre.py'}\" --texte \"...\" avec --fenetre et --element (ou --fichier). Puis finis ton tour "
              "en une ligne, sans répéter ta réponse. Si ce n'est pas un geste à faire à l'écran, finis ton tour sans "
              "rien changer.")
    sys.stdout.buffer.write(json.dumps({"decision": "block", "reason": raison}, ensure_ascii=False).encode("utf-8"))


def mesurer():
    """Sur les journaux récents : combien de fins de tour le garde-fou aurait renvoyées, et lesquelles."""
    sys.stdout.reconfigure(encoding="utf-8")
    depuis = time.time() - 5 * 86400
    total = renvois = deja = 0
    for f in (Path.home() / ".claude" / "projects").glob("*/*.jsonl"):
        if f.stat().st_mtime < depuis:
            continue
        tour_montre, dernier_texte = False, ""
        for l in open(f, encoding="utf-8", errors="replace"):
            try:
                d = json.loads(l)
            except ValueError:
                continue
            c = (d.get("message") or {}).get("content")
            if d.get("type") == "user" and not d.get("isSidechain") and (isinstance(c, str) or (
                    isinstance(c, list) and any(isinstance(x, dict) and x.get("type") == "text" for x in c))):
                if dernier_texte:
                    total += 1
                    p = geste_demande(dernier_texte)
                    if p and tour_montre:
                        deja += 1
                    elif p:
                        renvois += 1
                        print(f"{f.stem[:8]} | {p[:110]}")
                tour_montre, dernier_texte = False, ""
            if d.get("type") == "assistant" and isinstance(c, list):
                for x in c:
                    if isinstance(x, dict) and x.get("type") == "text":
                        dernier_texte = x.get("text") or ""
                    if isinstance(x, dict) and x.get("type") == "tool_use" and appel_de_montre(x):
                        tour_montre = True
    print(f"\n{total} fins de tour ; geste demandé et montré : {deja} ; renvoyées par le garde-fou : {renvois}")


if __name__ == "__main__":
    if "--mesure" in sys.argv:
        mesurer()
        sys.exit(0)
    try:
        main()
    except Exception:                          # un garde-fou ne doit jamais coincer une session
        pass
    sys.exit(0)
