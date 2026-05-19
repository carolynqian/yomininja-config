# yomininja-config

Auto-styles Anki cards created via Yomitan with stylization for Chinese learning:
mouse-hover to show pinyin in the `Sentence` field (above sentence text), plus Mandarin TTS in the `Sentence Audio`
field — all generated automatically the moment Yomitan sends the card to Anki.

## Why this exists

I read Chinese comics by OCRing them with [YomiNinja](https://github.com/matheusvalverde/YomiNinja),
looking up unfamiliar words with [Yomitan](https://yomitan.wiki/), and adding
those words into Anki via [AnkiConnect](https://ankiweb.net/shared/info/2055492159).

Yomitan ships the **word audio** (Forvo) and the raw **sentence text** to Anki,
but two things I want it can't do on its own:

1. **Hover-pinyin** on every character in the sentence. My note template has the
   parser embedded (from a legacy Migaku Chinese export), but it requires the
   sentence to be in `汉字[pinyin;pos]` bracket format, which Yomitan doesn't
   produce.
2. **Sentence audio** (not just word audio). HyperTTS does this manually, but
   doesn't expose any auto-fire hook for AnkiConnect-added notes.

This repo automates both, synchronously, as the card lands in Anki.

## End-to-end flow

```
YomiNinja (OCR a comic panel)
  ↓
Yomitan (look up a word, click "send to Anki")
  ↓
AnkiConnect (HTTP) → collection.add_note()
  ↓
[hook fires] yomitan_postprocess addon
  ├─ `say -v Tingting` → afconvert → m4a → Sentence Audio
  └─ shells out to yomitan_stylized_migaku.py --text "..."
       └─ jieba.posseg + pypinyin → 汉[pinyin;pos] format → Sentence
       └─ raw text → Plain Sentence
  ↓
Anki saves the fully-populated note
```

## Example transformation

| Field | Before (what Yomitan sends) | After (what gets saved) |
|---|---|---|
| `Sentence` | `我打开了收音机` | `我[wo3;r]打开[da3 kai1;v]了[le5;ul]<t>收音机[shou1 yin1 ji1;n]</t>` |
| `Plain Sentence` | *(empty)* | `我打开了收音机` |
| `Sentence Audio` | *(empty)* | `[sound:yomitan_pp_abc123.m4a]` |

The bracket-format `Sentence` triggers the Migaku JS in the card template to
render hover-pinyin tooltips on every word during review.

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

## Personal backup (not needed to use this project)

The `yomitan_settings/` directory contains an export of my own Yomitan
extension settings — note type mappings, popup behavior, scan key
bindings, etc. — that I keep here so I can restore my workflow on a
fresh machine. It's personal config, not part of the install.

- `yomitan-settings-*.json` — committed, 38 KB.
- `yomitan-dictionaries-*.json` — gitignored (200+ MB). The dictionaries
  themselves are public (CC-CEDICT, etc.) and can be re-imported from
  source any time, so I keep the export only locally.

To restore: open Yomitan → Settings → Backup → Import Settings →
select the JSON. Then re-import dictionaries from their original
sources.

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
