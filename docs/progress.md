# Progress

Append a new entry at the top each time something material changes.

---

## 2026-05-20 — Word audio, neural TTS, sentence translation

Expanded what the addon fills in on note add.

- `Word Audio` fallback: generates word TTS from `Target Word` when
  Yomitan's Forvo lookup found nothing. Refactored the generate→media→
  field logic into a shared `_attach_audio` helper used for both audio
  fields; only fires on empty fields so Forvo recordings still win.
- Neural TTS: audio now uses edge-tts (`zh-CN-XiaoxiaoNeural`) when
  online, falling back to macOS `say` (`Tingting`) offline or on any
  failure. Replaces the robotic compact `say` voice as the default.
- `Sentence Translation`: new `_translate` step fills the field via
  deep-translator's Google backend (free, no API key). Text piped over
  stdin to avoid shell-quoting issues; fails silently to blank if offline.

## 2026-05-18 — Public release prep

Cleaned up the repo so it can be flipped to public.

- Rewrote all 3 commits via `git filter-branch` to use the GitHub noreply
  email (`55215635+carolynqian@users.noreply.github.com`) instead of the
  Berkeley address that was baked into the original author lines.
  Author name preserved, contribution graph still credits @carolynqian.
  Force-pushed; old SHAs are gone from `origin/main` but kept locally
  under `refs/original/refs/heads/main` as a backup.
- Set `git config --global user.email` to the noreply form so future
  commits across all repos default to it. Per-repo override still works
  for work/uni repos that need a different identity.
- Added Yomitan settings export under `yomitan_settings/` as a personal
  restore backup. Committed the 38 KB settings JSON; gitignored the
  218 MB dictionaries JSON (GitHub blocks files >100 MB anyway, and the
  dictionaries are public CC-CEDICT / SUBTLEX / HSK / BLCU data
  reimportable from source). README has a new "Personal backup" section
  making it clear this is my config, not part of the install.

## 2026-05-18 — Initial build

Set up the full Yomitan → bracketized + audio pipeline from scratch after losing the previous machine.

- `yomitan_stylized_migaku.py`: jieba.posseg + pypinyin (Style.TONE3, neutral=5)
  to produce Migaku `汉[pinyin;pos]` format. Wraps target word in `<t>...</t>`.
  Two modes: `--text TEXT --target WORD` for live one-shot use, no-args for
  AnkiConnect backfill across all `[CURRENT] Yomitan` notes tagged `yomitan*`.
  Idempotent (skips already-bracketized).
- `yomitan_postprocess` Anki addon: hooks `anki.hooks.note_will_be_added`
  (fires synchronously for both Add Cards dialog and AnkiConnect — confirmed
  in Anki's hook docstring). Generates audio via macOS `say -v Tingting` +
  `afconvert` → m4a, attaches via `col.media.add_file`, shells out to the
  script to bracketize. Mutates note in-place before DB write — single save.
  Filters on note type `[CURRENT] Yomitan` AND tag prefix `yomitan` (matches
  `yomitan`, `yomitan::chinese`, etc.).
- Addon lives in this repo at `yomitan_postprocess/`; Anki picks it up via a
  symlink at `~/Library/Application Support/Anki2/addons21/yomitan_postprocess`.
  Repo is single source of truth.
- Logs to `/tmp/yomitan_postprocess.log` for debugging.

### Design decisions made along the way

- **Polling vs hook**: First built a 5s QTimer poller because I (wrongly)
  thought no Anki hook fired for AnkiConnect-added notes. `note_will_be_added`
  does. Polling deleted in favor of the hook.
- **HyperTTS**: Initially configured with auto-fire intent, but its "automatic"
  mapping flag only filters which rules run when the user clicks 🔊 — it does
  not hook note-add events. Replaced its auto role with the addon; HyperTTS
  preset kept around as a manual fallback for the editor button.
- **Migaku Anki add-on**: Considered but ignored — modern Migaku requires a
  subscription. Card template already has the parser JS embedded inline, so
  bracket format alone is enough; no add-on needed.
- **Subprocess vs vendored libs**: Addon shells out to `uv run` instead of
  vendoring jieba+pypinyin into the addon dir. ~500ms cold-start overhead but
  single source of truth for bracketize logic, no 10MB of vendored deps.
- **Audio source**: macOS `say -v Tingting` (the same engine HyperTTS uses
  when you pick the MacOS Tingting voice). No API key, no network.
