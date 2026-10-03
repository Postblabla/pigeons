"""
crochet_notification.py : reçoit les notifications de Claude Code et les dépose pour les pigeons.

Ce qu'il fait : Claude Code l'appelle par son crochet « Notification » quand une session attend une permission
(permission_prompt), attend depuis 60 s (idle_prompt), ouvre un formulaire (elicitation_dialog, elicitation_url_dialog)
ou qu'un agent a besoin de l'utilisateur (agent_needs_input). Il lit le JSON reçu sur l'entrée standard et écrit
signaux\\<session>.json ; le programme des pigeons le lit et passe le pigeon en « bloquée ».
Il ne bloque jamais Claude : Claude Code lance ce crochet en arrière-plan et ignore sa réponse.

Qui s'en sert : Claude Code, par le crochet posé dans %USERPROFILE%\\.claude\\settings.json (l'utilisateur l'a accepté).
Le nom n'est pas « signal.py » : il cacherait le module « signal » de Python à tout le dossier.
Où lire la suite : MANUEL.md ; le format reçu : https://code.claude.com/docs/en/hooks (section Notification).
"""

import json
import os
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent


def main():
    try:
        d = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return
    session = d.get("session_id")
    if not session:
        return
    dossier = ICI / "signaux"
    dossier.mkdir(exist_ok=True)
    signal_recu = {"session": session, "type": d.get("notification_type") or "", "message": d.get("message") or "",
                   "heure": time.time()}
    provisoire = dossier / f"{session}.tmp"
    provisoire.write_text(json.dumps(signal_recu, ensure_ascii=False), encoding="utf-8")
    os.replace(provisoire, dossier / f"{session}.json")     # jamais un fichier à moitié écrit


if __name__ == "__main__":
    main()
