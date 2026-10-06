"""
crochet_debut.py : le crochet « SessionStart » des pigeons. À l'ouverture de toute session (Claude Code, et Codex, qui
lit le même format de crochets), il rappelle les trois gestes des pigeons, quel que soit le dossier de la session.

Pourquoi (l'utilisateur, 6 octobre 2026, 08h2x : « des oublis d'utiliser l'app ») : les règles des pigeons ne vivaient que dans
Desktop\\CLAUDE.md. Une session lancée ailleurs ne les voyait pas, et les autres les oubliaient en route. Ce rappel
revient aussi après une compaction (le crochet repart alors) ; il tient en une dizaine de lignes.

Branché dans ~/.claude/settings.json (« hooks » > « SessionStart ») et ~/.codex/hooks.json, avec l'accord de l'utilisateur.
Sortie : {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}} (format vérifié dans la
documentation de Claude Code le 6 octobre 2026). Il ne bloque jamais rien : au pire, il ne dit rien.
"""

import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent

RAPPEL = f"""\
Les pigeons (le système d'indication de l'utilisateur, {ICI}) voient où chaque IA travaille et guident l'utilisateur vers ce que tu attends de lui. Trois gestes, sans exception :
1. Un geste de l'utilisateur à l'écran (cliquer, ouvrir un dossier, glisser un fichier, coller un prompt dans une nouvelle séance) : dis-le dans ta réponse ET montre-le, par l'outil « montrer » du serveur MCP pigeons, sinon par python "{ICI / 'montre.py'}" --texte "..." --fenetre "..." --element "..." (ou --fichier CHEMIN). Lis sa réponse : trouvée, ou les noms proches.
2. Avant d'écrire dans un dossier partagé (un autre projet, Mon projet, un jeu) : l'outil « qui_travaille », sinon python "{ICI / 'annonce.py'}" --qui "CHEMIN". Occupé : n'écris pas, dis-le à l'utilisateur.
3. À la fin de ta séance (passation faite, ou l'utilisateur ferme) : l'outil « terminer », sinon python "{ICI / 'montre.py'}" --termine, en tout dernier.
Si tu n'es pas Claude Code (Codex, Antigravity) : « annoncer » le fichier où tu écris, et ajoute --session ton-nom aux commandes.
Écris en clair les chemins et les liens de tes livrables : le panneau les offre à l'utilisateur (Copier, Ouvrir, Montrer).
"""


def main():
    try:
        sys.stdin.read()                       # l'entrée du crochet (session, source) : rien à en tirer ici
    except (OSError, ValueError):
        pass
    if not (ICI / "montre.py").exists():
        return
    sortie = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": RAPPEL}}
    sys.stdout.buffer.write(json.dumps(sortie, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception:                          # un crochet ne doit jamais empêcher une session de s'ouvrir
        pass
    sys.exit(0)
