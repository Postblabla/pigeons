# Pigeons : ce que toute IA doit savoir (une page)

*Pour Claude Code, Cowork, Antigravity (AG) ou un script, qui travaille sur l'ordinateur de l'utilisateur. Le détail :
`MANUEL.md` (français) ou `MANUAL.md` (anglais), section 5. Les commandes sont dans `%USERPROFILE%\Desktop\Pigeons`.*

## 1. Montrer un geste à l'utilisateur

Quand tu as besoin d'un geste de l'utilisateur à l'écran (ouvrir un dossier, cliquer un bouton, glisser un fichier), dis-le
dans ta réponse ET montre-le :

```
python "%USERPROFILE%\Desktop\Pigeons\montre.py" --texte "Clique sur Accepter" --fenetre "Chrome" --element "Accepter"
```

- Les cibles : `--fichier CHEMIN` (une icône visible), `--fenetre TITRE --element NOM` (un bouton ; `--fenetre
  "Pigeons"` vise le panneau des pigeons), `--point X Y` (pixels physiques). Une deuxième étape : `--puis-…` ; un
  glisser : `--vers-…`.
- Une IA autre que Claude Code ajoute `--session nom --titre "Nom"` (par exemple `--session ag --titre "AG"`).
- **Dans un navigateur**, donne l'onglet : `--fenetre "Chrome" --onglet "Gemini" --element "Envoyer"`. L'automatisation
  de Windows ne voit que la page de l'onglet affiché ; si l'onglet est caché, l'utilisateur est guidé vers lui d'abord.
  `--element` (une partie du nom) suit le bouton s'il bouge ; `--page X Y L H --echelle devicePixelRatio` (le
  rectangle de `getBoundingClientRect`) seulement pour un élément sans nom ; `--point` en dernier.
- **Pour viser juste** : `montre.py --liste --fenetre "Chrome" --onglet "Gemini"` donne les onglets et les noms des
  éléments cliquables visibles.
- **montre.py répond lui-même** (5 s au plus) : « Trouvée : Chrome › onglet « Gemini » › bouton « Envoyer » », ou
  « Pas trouvée : … ; les noms proches : … ». Code 0 trouvée, 1 pas trouvée, 2 je ne sais pas. La balise sur la ligne
  dit la même chose à l'utilisateur (l'app, l'onglet, ce qui couvre la cible).
- Les pigeons arrêtés sans que l'utilisateur ait cliqué « Arrêter », ou gelés, sont relancés par `montre.py` et `annonce.py`.
- Ta demande disparaît de `demandes\<session>.json` quand l'utilisateur a fait le geste.

## 2. Ne pas écrire là où une autre IA écrit

- **Le registre** `activite.json` dit, toutes les 2 s, qui travaille où (fichier, dossier de projet, écritures
  récentes) et les conflits.
- **Avant d'écrire** dans un dossier partagé :
  `python "%USERPROFILE%\Desktop\Pigeons\annonce.py" --qui "CHEMIN" --session nom`
  Code 0 : libre (lis l'« attention » s'il y en a une) ; **1 : occupé, n'écris pas, dis-le à l'utilisateur** ; 2 : inconnu.
  Avec le code 2, lis le message : « ne tournent pas » (arrêtés) n'est pas « tournent, mais registre figé » (le
  programme est là, son guetteur s'est arrêté). Ne dis pas à l'utilisateur que les pigeons sont arrêtés s'ils sont figés.
- **Une IA autre que Claude Code s'annonce** pendant qu'elle écrit :
  `python "…\annonce.py" --session nom --titre "Nom" --ia Outil --fichier "CHEMIN" --ecrit` (à refaire quand elle
  change de fichier ; `--fin` à la fin). Les sessions Claude Code sont suivies seules, par leur journal.

## 3. À la fin de ta séance

`python "%USERPROFILE%\Desktop\Pigeons\montre.py" --termine` (avec `--session nom` si tu n'es pas Claude Code), en
tout dernier, juste avant ta dernière réponse : ta carte et tes lignes s'en vont.

## 4. Les règles

- N'écris jamais dans `reglages.json` ni `couleurs.json` ; ne lis aucun fichier `cle_*` ; n'arrête pas le programme.
- Une demande à la fois, une consigne courte, en français.
- Écris en clair les liens et les chemins de tes livrables : le panneau les offre à l'utilisateur (Copier, Ouvrir, Montrer).

---

# Pigeons: what every AI should know (one page)

*For Claude Code, Cowork, Antigravity or a script working on the user's computer. Details: `MANUAL.md`, section 5.*

1. **Show an action**: say it in your reply AND run `montre.py --texte "…"` with `--fichier`, `--fenetre --element`
   (`--fenetre "Pigeons"` targets the pigeons' panel) or `--point X Y`; `--puis-…` for a second step, `--vers-…` for a
   drag. Not Claude Code: add `--session name --titre "Name"`. In a browser, add `--onglet "Tab title"` (only the
   displayed tab's page is visible to Windows UI Automation; a hidden tab is shown to the user first). `--liste
   --fenetre X` lists the tabs and clickable names. montre.py answers itself within 5 s: found (app › tab › element)
   or not, with close names; exit code 0 / 1 / 2.
2. **Don't write where another AI writes**: before writing, `annonce.py --qui "PATH" --session name` (0 free, **1
   occupied: don't write, tell the user**, 2 unknown: the message tells "not running" from "running, registry frozen").
   Not Claude Code: announce with `annonce.py --session name --titre
   "Name" --fichier "PATH" --ecrit`, and `--fin` at the end.
3. **At the end of your session**: `montre.py --termine` (plus `--session name` if not Claude Code), last thing before
   your final answer.
4. **Rules**: never write `reglages.json` or `couleurs.json`; never read `cle_*` files; don't stop the program; one
   request at a time; write deliverables' links and paths in full.
