"""
crochet_ecriture.py : le harnais des pigeons, un crochet « PreToolUse » de Claude Code sur Write, Edit, MultiEdit et
NotebookEdit. Avant qu'une session écrive un fichier, il lit le registre des pigeons (activite.json) : si une AUTRE
session ou une autre IA a écrit ce même fichier il y a moins de 5 min, ou annonce qu'elle l'écrit, il demande l'accord
de l'utilisateur, avec la raison (qui, quand).

Pourquoi (l'utilisateur, 3 octobre 2026, 09h12, l'idée 22.4 ; redemandé le 6 octobre) : « un harnais pour qu'elles voient
qu'un agent ou une autre IA travaille dans le fichier, pour éviter les conflits d'écriture ». Jusqu'ici, la règle
(annonce.py --qui) reposait sur la mémoire de chaque session.

Ce qu'il ne fait jamais : bloquer pour un simple « même dossier » (trop de bruit), ni gêner quand le registre manque ou
date de plus de 15 s (les pigeons arrêtés ne doivent pas arrêter le travail). Toute erreur : il se tait.

Entrée (stdin) : {"session_id", "tool_name", "tool_input": {"file_path" | "notebook_path"}, ...}.
Sortie, s'il y a conflit : {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
"permissionDecisionReason": "..."}} (format vérifié dans la documentation de Claude Code le 6 octobre 2026).
Essayer : python crochet_ecriture.py --essai "CHEMIN"
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
ACTIVITE = ICI / "activite.json"
CONFLIT_S = 5 * 60          # comme le bandeau des conflits du panneau
ANNONCE_S = 10 * 60         # une annonce « j'écris ce fichier » tient 10 min
REGISTRE_VIEUX_S = 15


def norme(chemin):
    return os.path.normcase(os.path.abspath(chemin)) if chemin else ""


def conflits(chemin, moi, maintenant=None):
    """Les autres sessions ou IA qui écrivent ce fichier : une liste de phrases (vide : libre)."""
    maintenant = maintenant or time.time()
    try:
        registre = json.loads(ACTIVITE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if maintenant - registre.get("maj", 0) > REGISTRE_VIEUX_S:
        return []
    cible, qui = norme(chemin), []
    for s in registre.get("sessions", []):
        if not s.get("session") or s.get("session") == moi:
            continue
        nom = f"« {s.get('titre')} » ({s.get('ia')})"
        autre_ia = s.get("ia") != "Claude Code"
        for e in s.get("ecrits", []):
            if norme(e.get("fichier")) != cible:
                continue
            try:
                quand = datetime.fromisoformat(e["heure"]).timestamp()
            except (KeyError, ValueError):
                continue
            if maintenant - quand < (ANNONCE_S if autre_ia else CONFLIT_S):
                qui.append(f"{nom} a écrit ce fichier à {e['heure'][11:16]}" if not autre_ia
                           else f"{nom} annonce qu'il écrit ce fichier (depuis {e['heure'][11:16]})")
                break
    return qui


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--essai":
        sys.stdout.reconfigure(encoding="utf-8")
        print("\n".join(conflits(sys.argv[2], None)) or "Libre.")
        return
    try:
        entree = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except (OSError, ValueError):
        return
    outil = entree.get("tool_input") or {}
    chemin = outil.get("file_path") or outil.get("notebook_path")
    if not chemin:
        return
    qui = conflits(chemin, entree.get("session_id"))
    if not qui:
        return
    raison = ("Les pigeons : une autre IA travaille sur ce fichier. " + " ; ".join(qui) +
              ". Écrire maintenant risque d'écraser son travail. l'utilisateur, tu acceptes ? (Claude : sinon, attends ou "
              "travaille ailleurs, et dis-le à l'utilisateur.)")
    sortie = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                     "permissionDecisionReason": raison}}
    sys.stdout.buffer.write(json.dumps(sortie, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception:                          # le harnais ne doit jamais casser une écriture par sa propre faute
        pass
    sys.exit(0)
