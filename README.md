# Pigeons

**A guidance overlay for working with AI agents on Windows.** When an AI session (Claude Code, Cowork, Antigravity or
any script) needs you to do something on screen (open a folder, click a button, drag a file, answer a question), the
pigeons draw a dotted line from your mouse to the exact spot, frame it, and add a card to a small “To do for you”
panel. Everything stays on your computer.

*Version française : [README.fr.md](README.fr.md).*

## What it does

- **Shows where to click**: dotted lines from the mouse to the target (straight, arc, wavy), frames that hug the
  target, numbered steps, and an arrowed line between two linked targets (drag A into B).
- **Knows what your Claude Code sessions are doing**, by reading their local logs: which session waits for you, which
  one asks a question (it frames the questionnaire), which one needs a permission (with a Notification hook).
- **A panel**: one card per session waiting for you, with *Go*, *Guide*, *Done*, *Later* and *End*; active help
  buttons (*Open the folder*, *Bring to front*); per-session turn duration and context size.
- **Coordinates AIs**: a live registry (`activite.json`) of who works where, `annonce.py` for other AIs to announce
  themselves and ask whether a file is free, and a warning when two AIs write the same file.
- **Plugs into each AI's own tools**: an MCP server (`pigeons_mcp.py`, no dependency) gives Claude Code, Codex,
  Antigravity and the Claude app the same tools (show, list, who works, announce, end); Claude Code hooks remind every
  session of the pigeons, ask you before a session overwrites a file another AI just wrote, and send a session back
  when it asks you for a click without showing it. Codex and Antigravity are followed by reading their local
  conversation databases (read-only).
- **Settings in the style of modern apps**: themes (system, light, dark, night, amber), your own colors, contrast,
  line shape and motion, frames, and a search box. English and French.

## Requirements

Windows 10 or 11, Python 3.11+, and: `python -m pip install --user -r requirements.txt`

## Run

Double-click `Lancer la preuve.bat`, or run `pythonw preuve_pigeons.py`. Settings, then *Start with Windows*, to
launch it at login.

## For AI agents

Read [POUR_LES_IA.md](POUR_LES_IA.md) (one page, French then English). In short:

```
python montre.py --texte "Click Accept" --fenetre "Chrome" --element "Accept"
python annonce.py --qui "C:\path\to\file.md"
python montre.py --termine
```

## Documentation

The full manual: [MANUAL.md](MANUAL.md) (or `MANUAL.docx`); in French, [MANUEL.md](MANUEL.md).
`python faire_manuel.py` rebuilds it from the code.

## Privacy

See [PRIVACY.md](PRIVACY.md): the app reads local files only and sends nothing over the network.

## License

MIT, see [LICENSE](LICENSE).
