# Pigeons

**Un guide visuel pour travailler avec des agents d'IA sous Windows.** Quand une session d'IA (Claude Code, Cowork,
Antigravity ou un script) a besoin d'un geste de ta part (ouvrir un dossier, cliquer un bouton, glisser un fichier,
répondre à une question), les pigeons tracent une ligne pointillée de ta souris jusqu'à l'endroit, l'encadrent, et
ajoutent une carte au petit panneau « À faire pour toi ». Tout reste sur ton ordinateur.

*English version: [README.md](README.md).*

## Ce que ça fait

- **Montre où cliquer** : des lignes pointillées de la souris à la cible (droites, en arc, sinueuses), des encadrés
  qui épousent la cible, des étapes numérotées, et une ligne fléchée entre deux cibles liées (glisser A dans B).
- **Sait ce que font tes sessions Claude Code**, en lisant leurs journaux locaux : laquelle t'attend, laquelle pose
  une question (le questionnaire est encadré), laquelle demande une permission (avec un crochet Notification).
- **Un panneau** : une carte par session qui t'attend, avec Aller, Guider, C'est fait, Plus tard et Terminer ; une
  aide active (Ouvrir le dossier, Amener devant) ; la durée du tour et la taille du contexte de chaque session.
- **Coordonne les IA** : un registre en direct (`activite.json`) de qui travaille où, `annonce.py` pour qu'une autre
  IA s'annonce et demande si un fichier est libre, et une alerte quand deux IA écrivent le même fichier.
- **Se branche dans les outils mêmes de chaque IA** : un serveur MCP (`pigeons_mcp.py`, sans dépendance) donne à
  Claude Code, Codex, Antigravity et l'app Claude les mêmes outils (montrer, lister, qui travaille, annoncer,
  terminer) ; des crochets de Claude Code rappellent les pigeons à chaque session, te demandent ton accord avant
  qu'une session écrase un fichier qu'une autre IA vient d'écrire, et renvoient une session qui te demande un clic
  sans le montrer. Codex et Antigravity sont suivis en lisant leurs bases de conversations locales (en lecture seule).
- **Des réglages dans le style des applications modernes** : thèmes (système, clair, sombre, nuit, ambre), tes
  couleurs, le contraste, la forme et le mouvement des lignes, les encadrés, et une recherche. En français et en
  anglais.

## Installer et lancer

Windows 10 ou 11, Python 3.11 ou plus récent, puis : `python -m pip install --user -r requirements.txt`.
Double-clic sur `Lancer la preuve.bat`, ou `pythonw preuve_pigeons.py`.

## Pour les IA

Lis [POUR_LES_IA.md](POUR_LES_IA.md) (une page).

## Le manuel

[MANUEL.md](MANUEL.md) (ou `MANUEL.docx`) ; en anglais, [MANUAL.md](MANUAL.md). `python faire_manuel.py` le refait
à partir du code.

## Vie privée et licence

[PRIVACY.md](PRIVACY.md) : l'app ne lit que des fichiers locaux et n'envoie rien. Licence MIT ([LICENSE](LICENSE)).
