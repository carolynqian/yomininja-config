# yomininja-config

Auto-styles Anki cards created via Yomitan to look like Migaku Chinese cards:
hover-pinyin in the `Sentence` field, plus Mandarin TTS in the `Sentence Audio`
field — all generated automatically the moment Yomitan sends the card to Anki.

## What's in the box

| Path | Role |
|---|---|
| `yomitan_stylized_migaku.py` | Converts raw Chinese → Migaku `汉[pinyin;pos]` bracket format using jieba + pypinyin. Two modes: CLI (`--text`) for live use by the addon, AnkiConnect backfill (no args) for existing cards. |
| `yomitan_postprocess/` | Anki addon. Hooks `anki.hooks.note_will_be_added`, fires on every `[CURRENT] Yomitan` note tagged `yomitan*`. Generates audio with macOS `say -v Tingting` → `afconvert` → m4a, then shells out to the script to bracketize. |

## Prerequisites

- macOS (the addon uses `say` + `afconvert` from the system).
- [Anki](https://apps.ankiweb.net/) with these addons installed via AnkiWeb:
  - **AnkiConnect** (code `2055492159`) — required, lets Yomitan add cards.
  - *Optional:* **HyperTTS** (code `111623432`) for manual audio on one-off cards via the 🔊 editor button.
- [uv](https://github.com/astral-sh/uv) on `PATH` (or at `~/.local/bin/uv`). The addon shells out to `uv run` so jieba/pypinyin auto-install on first use.
- [Yomitan](https://yomitan.wiki/) browser extension, configured to send cards via AnkiConnect.
- A Yomitan-compatible Anki note type **named exactly `[CURRENT] Yomitan`** with these fields: `Sentence`, `Plain Sentence`, `Sentence Audio`, `Target Word`. The template must include the Migaku hover-pinyin JS on the `Sentence` field (the one with `data-reading="hover" data-reading-type="pinyin"`) — the parser is embedded in the template itself.
- Yomitan configured to tag every card it adds with `yomitan` (or a `yomitan::*` child tag).

## Install on a new machine

```bash
# 1. Clone the repo
mkdir -p ~/GitRepos && git clone git@github.com:carolynqian/yomininja-config.git ~/GitRepos/yomininja-config

# 2. Symlink the addon into Anki's addon directory
ln -s ~/GitRepos/yomininja-config/yomitan_postprocess \
      "$HOME/Library/Application Support/Anki2/addons21/yomitan_postprocess"

# 3. Restart Anki — confirm "Yomitan Post-Process" appears in Tools → Add-ons
```

That's it. Add a card via Yomitan; within ~2 seconds Anki will save it with bracketized `Sentence`, raw text in `Plain Sentence`, and an mp4 in `Sentence Audio`.

> **Why a symlink?** So the repo is the single source of truth — `git pull` updates the live addon, and edits to either location propagate to the other. If you'd rather not symlink, just copy the directory; you'll need to re-copy after every `git pull`.

## Backfill existing cards

The addon only fires on *new* notes. To process cards added before installing:

```bash
uv run ~/GitRepos/yomininja-config/yomitan_stylized_migaku.py
```

Idempotent — skips cards already bracketized. Audio backfill isn't handled by the script; use HyperTTS's browser → Add Audio (Collection) with a preset sourcing from `Sentence` → `Sentence Audio`.

## Customizing

All paths in `yomitan_postprocess/__init__.py`:

- `NOTE_TYPE` — change if your Yomitan note type is named differently.
- `TAG` — change if Yomitan tags cards with something other than `yomitan*`.
- `VOICE` — any voice from `say -v ?`. Other Mandarin options: `Lilian`, `Sin-ji`.
- `SCRIPT` is auto-resolved relative to the addon directory via the symlink — no change needed if you cloned to `~/GitRepos/yomininja-config/`.

## Troubleshooting

The addon writes a log to `/tmp/yomitan_postprocess.log`. After adding a card, check it:

```bash
tail /tmp/yomitan_postprocess.log
```

You should see something like:

```
[16:53:01] === addon loaded, hook registered (total hooks: 1) ===
[16:53:14] hook fired, tags=['yomitan::chinese']
[16:53:14]   processing: sentence='我打开了收音机'
```

If you see `skip: no yomitan tag` — your Yomitan setup isn't tagging the cards; configure that in Yomitan's Anki settings.
If you see nothing after "addon loaded" — the note type name doesn't match `NOTE_TYPE`.
If the hook fires but no audio appears — `uv` isn't on Anki's `PATH`; hardcode the full path in the `UV` constant.
