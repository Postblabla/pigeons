# Pigeons: the manual

*The guidance system for working with AI sessions · version of 2026-10-06*

## 1. Who this manual is for

- **If you use it**: sections 2 to 4 (launching, using the pigeons, settings).
- **If you take over the work, as a person or an AI**: sections 5 to 10 (AIs and `montre.py`, how it works inside, files, pitfalls, privacy, how to continue).
- This manual is built by `faire_manuel.py` from the code: the settings list and the guide are always accurate. After changing the app, run `python faire_manuel.py` again.

## 2. Installing and launching

- **Requirements**: Windows 10 or 11; Python 3.11 or newer (tested with 3.13); the modules `comtypes`, `pywin32` and `Pillow`: `python -m pip install --user comtypes pywin32 pillow`.
- **Launch**: double-click `Lancer la preuve.bat`, or run `pythonw preuve_pigeons.py` in the folder. Only one copy runs at a time (a Windows mutex): launching again brings the panel to the front.
- **With Windows**: the “Start the pigeons with Windows” box puts a shortcut in the Windows Startup folder.
- **Stop**: the panel's “Quit” button. The window's ✕ only minimizes the panel; the pigeons keep going.
- **Check without windows**: `python preuve_pigeons.py --texte` prints each pigeon's state.
- **See permissions to give** (optional): a Claude Code “Notification” hook in `~/.claude/settings.json`, with the matcher `permission_prompt|elicitation_dialog|elicitation_url_dialog|agent_needs_input` and the command `python "<folder>\crochet_notification.py"`.

## 3. Using the pigeons

The same text as the panel's “Guide” tab.

#### What the pigeons do

Each AI session (Claude Code, Cowork, another AI) has its own pigeon and color. When a session needs you, the pigeons show you what to do and where to click.

Everything stays on your computer: the pigeons read Claude Code's logs and send nothing anywhere.

#### On screen

- A dotted line goes from your mouse to what is waiting for you: a session, a button, a file.
- A frame hugs the target. With more on-screen info, a label says who is waiting, for what, and since when.
- The pigeons themselves are hidden by default (Settings, Pigeons card, to show them). When shown, the body has its session's color; a breathing ring: it is waiting for you; dotted: paused.
- Two linked targets (drag a file into a folder, or click here then there): an arrowed line goes from the first to the second, their frames show 1 and 2, and labels say “take this” and “drop here”.
- The beacon: on the line, just before the target, a small label says exactly where it is: the app, the tab, the button (“Chrome › tab “Gemini” › button “Send””). If another window covers the target, an amber chip says which one, and step 1 shows the app's taskbar button first; a hidden tab is shown first too. The beacon never covers the target: it moves back along the line, and fades out when your mouse is close (Settings, Guidance).
- Squabs are a session's sub-agents.

#### Importance colors

- Blocked: a permission to give (#ff2d55)
- High: an action to take (#ff5a5f)
- Normal: a question asked (#ffb020)
- Low: whenever you're ready (#5aa0ff)

You can change these colors in Settings.

#### The panel

To do for you: one card per session waiting for you, the most important first. Working: the sessions at work, their file and their rhythm. Resting: the ones asleep.

- Go: opens the session in Claude.
- Guide: the line and the pigeon show you the way.
- Done: the requested action is done.
- Later: 5 min, 15 min, 1 h or no limit.
- End: the session is finished; it comes back if you write to it.
- Copy, Open, Show: the links and files the session mentioned.
- New session: when the session gives a prompt to paste into a fresh session, this button copies it and opens a new session in the right folder of the Claude app. Then paste (Ctrl+V) and send.
- Active help: when a session asks you to go into a folder, open a file or a window, its card offers “Open the folder”, “Open the file” or “Bring to front”.
- Working: “Folder” opens the place where the session works; the row shows how long its turn has lasted and its context size (a compaction comes near the limit); a warning if two sessions work in the same folder.

Hover a button: it says what it does. The window's ✕ minimizes the panel; “Quit” stops the pigeons.

#### With the mouse

- Click the spot shown: done, the pigeon says thanks.
- If the pigeons are shown: click a pigeon for later (click again: resume); right-click: end its session.
- Hover a pigeon: its full bubble.

#### With the keyboard

- Ctrl+Alt+P: go to the most important thing; press again within 6 s for the next one.
- Ctrl+Alt+T: “Done” or “End” on the first thing to do.

#### Ending a finished session

End (card, right-click, Ctrl+Alt+T), archive the session in Claude, or the session itself at the end of its handoff (montre.py --termine). It comes back if you write to it.

#### For AIs: montre.py

A session that needs an action runs: python montre.py --texte "Click Accept" --fenetre "Chrome" --element "Accept".

Other targets: --fichier, --point X Y. A drag: --vers-… Two steps: --puis-… Also --importance, --fin, --termine. Another AI: --session name --titre "Name".

Coordination: the pigeons keep activite.json up to date (who works where, every 2 s). Another AI announces itself with annonce.py --session name --fichier PATH --ecrit, and asks before writing: annonce.py --qui PATH (free, occupied). The panel warns when two AIs write the same file.

The MCP server (pigeons_mcp.py): the same tools in each AI's own tool list (show, list, clear, end, who_works, announce, state), with no command line to remember. Claude Code, Codex, Antigravity and the Claude app (as “pigeons-cowork”) can plug it in. A Claude Code hook reminds every session of the pigeons at start, and another asks you before a session writes a file another AI wrote < 5 min ago.

#### Settings

At the bottom of the panel: guidance (lines or arrows), on-screen info, line shape and motion, fade, frames, pigeons, colors, language. Everything is kept in reglages.json.

The line to a session that finished its turn: never by default (Ctrl+Alt+P or “Guide” shows it), a few minutes, or until you answer. A question, a permission and a requested action are always guided; a question points to its questionnaire, down to the “Send” button. If Windows has turned off its animations, the lines stop moving too.

#### Files

The folder: %USERPROFILE%\Desktop\Pigeons. MANUAL.docx (or MANUAL.md) explains everything in detail; preuve_pigeons.log keeps the errors.

## 4. All settings

The panel's “Settings” button opens the settings window, in the style of Claude's settings: on the left, a search box and the categories (guidance: Guidance, Lines, Frames; the app: Appearance, Pigeons, General); on the right, their sections. The search shows the sections of every category that contain the typed word. Every change applies at once and is kept in `reglages.json`. “Reset to defaults” keeps the language, the panel's place and the Windows startup.

#### Appearance

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Theme | System ; Light ; Dark | System | `theme` |
| Dark theme | Default ; Night ; Amber | Default | `theme_sombre` |
| Contrast | Normal ; Strong | Normal | `contraste` |
| My colors: | yes or no | no | `theme_perso` |
| Background | a color | #16171b | `couleur_fond` |
| Text | a color | #e9e9ec | `couleur_texte` |
| Accent | a color | #8ab4ff | `couleur_accent` |
| Bubbles and labels | Paper (light) ; Theme colors ; Dark | Paper (light) | `bulles_couleurs` |
| A bubble near the target (otherwise, the instruction stays in the panel) | yes or no | no | `bulle_cible` |

- “System” follows Windows' light or dark theme. “Amber” uses Antigravity's colors.

#### General

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Language | English ; Français | English | `langue` |
| The panel | Free (I place it myself) ; Docked to the right of Claude ; Docked to the left of Claude | Free (I place it myself) | `ancrer_claude` |
| Start the pigeons with Windows | yes or no | no | `demarrage_windows` |

- Ctrl+Alt+P: next action (press again within 6 s for the next one).
- Ctrl+Alt+T: “Done” or “End” on the first thing to do. Right-click a pigeon: end its session.

#### Guidance

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Guidance to what you need to do | Dotted lines from my mouse to the target ; Arrows around my mouse | Arrows around my mouse | `guidage` |
| Guide me to the sessions waiting for me | yes or no | yes | `fleche_attente` |
| On-screen info | Discreet (the line and the frame) ; Detailed (a label: who, what, since when) ; Complete (plus the action to take, with its shortcut) | Discreet (the line and the frame) | `infos_ecran` |
| A beacon on the line: exactly where the target is (the app, the tab, what covers it) | yes or no | yes | `balise` |
| What the beacon says | The whole path ; The app and the item | The whole path | `balise_detail` |
| The beacon's halo breathes slowly | yes or no | no | `balise_respire` |
| Hollow arrows (outline only) | yes or no | yes | `fleche_creuse` |
| Arrow size (px) | from 14 to 44 | 23 | `taille_fleche` |

#### When a session is waiting for me

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Line to a session waiting for my answer | Until I answer (or “End”) ; For 15 min ; For 5 min ; For 1 min ; Never: Ctrl+Alt+P or “Guide” shows it | Never: Ctrl+Alt+P or “Guide” shows it | `lignes_reponse` |
| The pigeon comes near my mouse | yes or no | no | `appel_souris` |
| For (seconds) | from 5 to 60 | 20 | `duree_appel_s` |
| Pigeon click: later (min, 0 = indefinitely) | from 0 to 120 | 15 | `report_clic_min` |

- A finished turn. The frame and the label stay. A question asked (its questionnaire), a permission to give and a requested action are always guided.

#### Dotted lines

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Style | Dots ; Dashes | Dots | `lignes_style` |
| Size (px) | from 2 to 10 | 4 | `lignes_epaisseur` |
| Spacing (px) | from 6 to 30 | 11 | `lignes_espacement` |

#### Shape and motion

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Shape | Straight ; Arc ; Wavy ; Flight | Arc | `lignes_forme` |
| Curvature (%) | from 0 to 100 | 35 | `lignes_courbure` |
| The line draws itself when it appears | yes or no | yes | `lignes_trace` |
| Continuous animation | None ; Dots move forward ; A wave | None | `lignes_animation` |
| Animation speed | from 1 to 10 | 4 | `lignes_vitesse` |

- “Flight”: an arc with small waves, like a pigeon. A continuous animation redraws the lines 15 times per second: a little more CPU.

#### Fade

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Opacity near my mouse (%) | from 0 to 100 | 90 | `lignes_opacite_depart` |
| Opacity near the target (%) | from 0 to 100 | 90 | `lignes_opacite_arrivee` |
| The fade starts at (% of the way) | from 0 to 100 | 0 | `lignes_fondu_debut` |
| The fade ends at (% of the way) | from 0 to 100 | 100 | `lignes_fondu_fin` |

- 0 % of the way: at your mouse; 100 %: at the target. Two equal opacities: no fade. Example: 90 then 0, from 50 to 100: the line is full until halfway and fades out on arrival.

#### Line color

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Line color | In the guide's color ; In a single color: | In the guide's color | `lignes_couleur` |
| the single line color | a color | #ffffff | `lignes_couleur_unique` |

#### Frames

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Frames | On, always shown ; On when my mouse gets close ; Off | On, always shown | `encadres` |
| Also frame the spot shown by a request | yes or no | yes | `encadres_montre` |
| Without pigeons, frame where each AI works (with its name) | yes or no | yes | `encadres_travail` |
| Style | Dotted ; Solid | Dotted | `encadres_style` |
| Size around the target (px) | from -3 to 12 | 0 | `encadres_marge` |
| Rounded corners (px) | from 0 to 12 | 6 | `encadres_arrondi` |
| Line thickness (px) | from 1 to 4 | 1 | `encadres_epaisseur` |

#### Pigeons

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| When a window hides the icon it works on | It goes to the taskbar ; It perches on that window ; It hides | It goes to the taskbar | `cible_cachee` |
| Pigeon size | from 5 to 14 | 8 | `taille_pigeon` |
| Show the pigeons (otherwise: only the lines, arrows and frames) | yes or no | no | `afficher_pigeons` |
| Also show working pigeons | yes or no | yes | `pigeons_au_travail` |
| Show squabs (sub-agents) | yes or no | yes | `pigeonneaux` |
| Line to the exact spot it works on | When hovering the pigeon ; Always ; Never | When hovering the pigeon | `lignes_travail` |

#### Colors and bubbles

| Setting | Possible values | Default | Key in reglages.json |
|---|---|---|---|
| Guide color | The task's color ; The importance code | The task's color | `couleur_guides` |
| Blocked: a permission to give | a color | #ff2d55 | `couleur_bloquee` |
| High: an action to take | a color | #ff5a5f | `couleur_haute` |
| Normal: a question asked | a color | #ffb020 | `couleur_normale` |
| Low: whenever you're ready | a color | #5aa0ff | `couleur_basse` |
| Bubbles | A short line when it shows or calls me ; Only on hover | A short line when it shows or calls me | `bulles` |
| Bubble opacity (%) | from 40 to 100 | 90 | `opacite_bulles` |

#### Settings kept by the program

They are not in the window: the program keeps them by itself (the panel's place), or they remain from an older version, to read old files. Don't change them by hand.

- `panneau_geometrie`: `''`
- `lignes_opacite`: `80`
- `lignes_fondu`: `'aucun'`
- `lignes_fondu_portee`: `100`
- `lignes_fondu_min`: `0`

## 5. For AIs and scripts

### 5.1 Showing an action: montre.py

A session that needs an action from the user runs, for example:

```
python "%USERPROFILE%\Desktop\Pigeons\montre.py" --texte "Click Accept" --fenetre "Chrome" --element "Accept"
```

| Option | What it does |
|---|---|
| `--texte TEXT` | the instruction, in one sentence |
| `--fichier PATH` | an icon on the Desktop or in an open folder |
| `--fenetre TITLE --element NAME` | a button, link or box in a window, by part of its name (read by Windows UI Automation); with --fenetre "Pigeons", a panel button (“Réglages”, “Guide”...) |
| `--onglet TITLE` | with --fenetre, the browser tab holding the target: if it is hidden, the guidance shows the tab first (Windows UI Automation only sees the page of the displayed tab) |
| `--page X Y W H, --echelle F` | an unnamed element of a web page: the getBoundingClientRect() rectangle in CSS pixels, and window.devicePixelRatio; --element is better: it follows the button if it moves |
| `--point X Y` | a point on the screen, in physical pixels; with --dans TITLE, if another window covers the point, the guidance brings that one to the front first |
| `--liste` | with --fenetre (and --onglet): the tabs and the visible clickable elements, to aim right; nothing is shown |
| `--sans-attendre` | don't wait for the answer: by default montre.py waits for the watcher (5 s at most) and says whether the target is found, where (app, tab, screen), and if not why, with close names; exit code 0 found, 1 not found, 2 unknown |
| `--vers-fichier, --vers-fenetre, --vers-element, --vers-point` | the end of a drag |
| `--puis-fichier, --puis-fenetre, --puis-element, --puis-point, --puis-texte` | a second step (“click here, then there”): frames numbered 1 and 2 |
| `--importance haute\|normale\|basse` | high (haute) by default |
| `--minutes N` | how long the request lasts (15 by default); it also ends at the user's next message to the session |
| `--fin` | clears the request at once |
| `--termine` | the session is finished: its pigeon, card and lines go away (run it last, just before the final answer) |
| `--session NAME, --titre NAME` | for another AI without a Claude Code log; by default the session is read from the CLAUDE_CODE_SESSION_ID variable |

### 5.2 Exchange files (JSON)

- **`demandes\<session>.json`** (written by `montre.py`): `session`, `heure`, `duree_s`, `texte`, `cible`, `vers`, `puis`, `texte_puis`, `titre`, `importance`. A target is `{"fichier": path}`, `{"fenetre": title, "element": name}` or `{"point": [x, y]}`.
- **`signaux\<session>.json`** (written by `crochet_notification.py`): `session`, `type` (`permission_prompt`, `elicitation_dialog`, `elicitation_url_dialog`, `agent_needs_input`), `message`, `heure`. Cleared as soon as the session moves on.
- **`fermetures\<session>.json`**: `session`, `heure`, `par` (`danny` or `session`). Forgotten after 3 days, or as soon as the session moves on.
- **`demandes\_vivant.txt`**: the time of the last round; `montre.py` uses it to see whether the pigeons are running.
- Each file is first written next to its place, then renamed: the program never reads a half-written file.

### 5.3 Rules given to Claude sessions

In `Desktop\CLAUDE.md`, which every session launched on the Desktop reads:

- show every action asked of the user with `montre.py`;
- run `montre.py --termine` at the end of the handoff;
- write the links and paths of deliverables in full: the panel offers them (Copy, Open, Show).

Another AI (Cowork, Gemini, a script) passes `--session name --titre "Name"`, or writes the request file itself; its pigeon lives as long as its request exists.

### 5.4 Coordinating AIs: activite.json and annonce.py

So that two AIs don't write the same file at the same time (the user, October 3, 2026):

- **The registry** `activite.json`: every 2 s the pigeons write who works where (session, tool, file, project folder, state, files written in the last 10 min) and the conflicts. For an AI that made a request, `demande.trouvee` says whether its target was found on screen, and `demande.precision` why not. Claude Code sessions are in it on their own, from their logs.
- **Announcing** (another AI): `python annonce.py --session ag --titre "AG" --ia Antigravity --fichier PATH --ecrit`; or `--dossier PATH`; `--fin` at the end. The announcement lasts 10 min (`--minutes`): announce again when changing files.
- **Asking before writing**: `python annonce.py --qui PATH --session ag`. Exit code 0: free (with a warning if another AI works in the same folder); 1: occupied (another AI wrote this file in the last 10 min, or works on it); 2: unknown, and the message says why: the pigeons are not running, or they run but their registry is frozen (their watcher stopped its rounds; they restart it on their own within 2 min). `montre.py` makes the same distinction.
- **Conflicts**: two AIs writing the same file less than 5 min apart bring up a banner at the top of the panel.

## 6. How it works inside

Everything is in `preuve_pigeons.py` (about 5600 lines), in three parts that talk through a shared state.

#### The watcher (Guetteur class, its own thread, one round per second)

- It reads the end of Claude Code's logs (`~/.claude/projects/*/*.jsonl`, and `subagents/` for sub-agents): the `Session` class follows tools, touched files, finished turns, questions, the user's messages and the links mentioned.
- It reads requests, signals, closings, and the Claude app's session files (`%APPDATA%\Claude\claude-code-sessions`, to know a session is archived).
- It locates targets with Windows UI Automation (UIA, `comtypes` module): Desktop and Explorer icons, a window's buttons, a session's row in the Claude app, a taskbar button.
- It decides each pigeon's mode (`placer`) and puts everything in the shared state.

#### Modes and importances

- **Modes**: `montre` (a `montre.py` request), `appel` then `attend` (a session waits for the user), `pose` (on the icon of the file it works on), `perche` (that icon is hidden), `parc` (no file), `repos` (2 min without a tool); on the display side, `pause` and `merci`.
- **Importances**: `bloquee` (a permission, from the hook), `haute` (a requested action), `normale` (a question), `basse` (a finished turn).
- **A closed session** (`Session.est_fermee`): a file in `fermetures\`, or archived in the app. It reopens if the user writes to it, if it asks for a permission or an action, or if it runs a tool more than 2 min later.

#### The display (Volee class, the Tk thread, 30 frames per second)

- Each pigeon, arrow, frame and bubble is a small transparent window that is moved around (a full-screen canvas cost 13 % of a core).
- The dotted lines are layered windows (`Voile` class, `UpdateLayeredWindow`): each dot has its own transparency; they only cover the lines' bounding box and are redrawn only when something moves.
- `chemin()` gives the path (straight, arc, wavy, flight); `points_de_ligne()` places the dots at even intervals along it; `tracer_lignes()` handles the 250 ms trace and the animations.
- `guider_attente()` places the frames, labels and lines toward waiting sessions; `guetter_clic()` detects the click on the shown spot; the `Raccourci` class (a thread) receives Ctrl+Alt+P and Ctrl+Alt+T.

#### The panel (Panneau class)

- The “To do” and “Guide” tabs, the cards, the tooltips (`Infobulle` class), and the settings window (`Volee.ouvrir_reglages`). It is rebuilt only when its content changes.
- Language: French is written in the code; `tr()` translates it with the `ANGLAIS` table; the guide has both versions in `contenu_guide()`.
- The error log: `preuve_pigeons.log`, 1 MB at most, then three copies.
- Measured: about 4.6 % of a core without lines, 7.2 % with them.

## 7. Files in the folder

| File | Role |
|---|---|
| `preuve_pigeons.py` | the whole program |
| `montre.py` | the command a session runs to show an action |
| `crochet_notification.py` | receives Claude Code notifications (permissions) and drops them in signaux\ |
| `faire_manuel.py` | builds this manual |
| `annonce.py` | another AI says where it works, or asks who works somewhere (section 5.4) |
| `activite.json, annonces\` | the registry of who works where, and other AIs' announcements |
| `Lancer la preuve.bat` | launches the pigeons |
| `reglages.json` | the user's settings: never overwrite them |
| `couleurs.json` | each session's fixed color |
| `demandes\, signaux\, fermetures\` | the exchange files (section 5.2) |
| `preuve_pigeons.log` | the error log |
| `MANUEL.md, MANUEL.docx, MANUAL.md, MANUAL.docx` | this manual, in French and English |

## 8. Known pitfalls

- **`reglages.json`**: stop the program before writing to it, or it writes over your changes. These are the user's settings.
- **Never name a function `t()`**: local variables are called `t` (a window's top).
- **Layered windows**: no Tk `-alpha` or `-transparentcolor` on a `Voile` (they prevent `UpdateLayeredWindow`).
- **Physical pixels everywhere** (`SetProcessDpiAwarenessContext(-4)`): a screen may be at 125 %.
- **UIA is per thread**: the watcher has its own, the display too.
- **The panel is recognized** by its `TkTopLevel` class, its “Pigeons” title, and not being a tool window.
- **Capturing the lines**: `ImageGrab.grab(all_screens=True, include_layered_windows=True)`, or they don't show.
- **Creating the line canvases takes about 0.45 s**: a line is redrawn until it has been drawn in full once.
- **Stop only the pigeons**, not every `pythonw`: filter on the `preuve_pigeons.py` command line.
- **The Claude app's session files** are internal and undocumented: they may change.
- **Times** are read in the logs or with a tool, never guessed.

## 9. Privacy

Everything stays on the computer. The pigeons read Claude Code's logs and the app's session files without writing to them; they send nothing over the network and have no telemetry. They write only in their own folder (settings, colors, requests, signals, closings, log) and, if asked, a shortcut in the Startup folder.

## 10. Continuing the work

- **Try without windows**: `python preuve_pigeons.py --texte`.
- **Restart**: stop the `pythonw` whose command line contains `preuve_pigeons.py`, then run `pythonw preuve_pigeons.py`.
