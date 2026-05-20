"""
Yomitan Post-Process

Fires synchronously on note add (Add Cards dialog OR AnkiConnect) via
`anki.hooks.note_will_be_added`. For [CURRENT] Yomitan notes tagged `yomitan`:

  1. Generates audio for any of `Sentence Audio` / `Word Audio` that are
     still empty — edge-tts neural voice when online, macOS `say` offline.
     Word Audio is a fallback for when Yomitan's Forvo lookup found nothing.
  2. Translates the sentence into `Sentence Translation` if empty, via
     deep-translator's Google backend (free, no API key).
  3. Shells out to yomitan_stylized_migaku.py --text "..." --target "..." to
     bracketize, then writes `Sentence` (bracketed) + `Plain Sentence` (raw).

Hook fires before the note hits the DB, so we mutate the note in-place and
Anki saves our changes — no second write needed.
"""

import hashlib
import os
import shutil
import subprocess
import time
import traceback

from anki.hooks import note_will_be_added

NOTE_TYPE = "[CURRENT] Yomitan"
TAG = "yomitan"  # also matches yomitan::chinese, yomitan::*, etc.
# Resolves through the addon symlink to the real script in the repo.
SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                      "..", "yomitan_stylized_migaku.py")
UV = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
EDGE_VOICE = "zh-CN-XiaoxiaoNeural"  # neural; needs network. `edge-tts -l` for more
SAY_VOICE = "Tingting"               # offline fallback; `say -v '?'` for more
LOG_PATH = "/tmp/yomitan_postprocess.log"


def _log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except Exception:
        pass
    print(f"[yomitan_postprocess] {msg}")


def _translate(text: str) -> str | None:
    """Translate Chinese `text` → English via deep-translator (Google backend).
    Free, no API key. Returns None on any failure. Text passed over stdin to
    sidestep shell-quoting."""
    try:
        r = subprocess.run(
            [UV, "run", "--with", "deep-translator", "python3", "-c",
             "import sys; from deep_translator import GoogleTranslator; "
             "print(GoogleTranslator(source='auto', target='en')"
             ".translate(sys.stdin.read().strip()))"],
            input=text, capture_output=True, text=True, timeout=30, check=True,
        )
        return r.stdout.strip() or None
    except Exception as e:
        _log(f"  translate failed: {e}")
        return None


def _bracketize(text: str, target: str) -> str | None:
    try:
        r = subprocess.run(
            [UV, "run", SCRIPT, "--text", text, "--target", target],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return r.stdout
    except Exception as e:
        _log(f"bracketize failed: {e}")
        return None


def _make_audio(text: str) -> str | None:
    """Synthesize `text` to an audio file. Tries edge-tts (neural, needs
    network), falls back to macOS `say` (offline). Returns a path or None."""
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]

    # Preferred: edge-tts neural voice.
    mp3 = f"/tmp/yomitan_pp_{h}.mp3"
    try:
        subprocess.run(
            [UV, "tool", "run", "edge-tts", "--voice", EDGE_VOICE,
             "--text", text, "--write-media", mp3],
            check=True, capture_output=True, timeout=60,
        )
        if os.path.getsize(mp3) > 0:
            return mp3
    except Exception as e:
        _log(f"  edge-tts failed ({e}); falling back to say")
    if os.path.exists(mp3):
        try: os.unlink(mp3)
        except OSError: pass

    # Fallback: macOS `say`, fully offline.
    aiff = f"/tmp/yomitan_pp_{h}.aiff"
    m4a = f"/tmp/yomitan_pp_{h}.m4a"
    try:
        subprocess.run(["say", "-v", SAY_VOICE, "-o", aiff, text],
                       check=True, capture_output=True, timeout=30)
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", aiff, m4a],
                       check=True, capture_output=True, timeout=30)
        os.unlink(aiff)
        return m4a
    except Exception as e:
        _log(f"  audio gen failed for {text[:30]!r}: {e}")
        return None


def _attach_audio(col, note, field: str, text: str) -> None:
    """TTS `text` into `field` as a [sound:..] tag, only if `field` is empty."""
    if (note[field] or "").strip() or not text:
        return
    path = _make_audio(text)
    if path:
        note[field] = f"[sound:{col.media.add_file(path)}]"
        _log(f"  added {field} for {text[:20]!r}")
        try: os.unlink(path)
        except OSError: pass


def on_note_will_be_added(col, note, deck_id) -> None:
    try:
        if note.note_type()["name"] != NOTE_TYPE:
            return
        if not any(t == TAG or t.startswith(f"{TAG}::") for t in note.tags):
            _log(f"skip: no {TAG} tag, tags={list(note.tags)!r}")
            return
        _log(f"hook fired, tags={list(note.tags)!r}")
        sentence = (note["Sentence"] or "").strip()
        if not sentence or "[" in sentence:
            _log(f"  skip: empty or already bracketed")
            return
        _log(f"  processing: sentence={sentence[:40]!r}")

        # 1. Audio — sentence (raw), and word as a fallback when Yomitan's
        #    Forvo lookup found nothing. Target Word is plain text; strip any
        #    bracket annotation defensively before TTS.
        target = (note["Target Word"] or "").strip()
        target_plain = target.split("[")[0].strip()
        _attach_audio(col, note, "Sentence Audio", sentence)
        _attach_audio(col, note, "Word Audio", target_plain)

        # 2. Sentence translation (raw sentence → English)
        if not (note["Sentence Translation"] or "").strip():
            tr = _translate(sentence)
            if tr:
                note["Sentence Translation"] = tr
                _log(f"  added Sentence Translation")

        # 3. Bracketize
        bracketed = _bracketize(sentence, target)
        if bracketed:
            if not (note["Plain Sentence"] or "").strip():
                note["Plain Sentence"] = sentence
            note["Sentence"] = bracketed
    except Exception:
        _log(f"hook crash:\n{traceback.format_exc()}")


note_will_be_added.append(on_note_will_be_added)
_log(f"=== addon loaded, hook registered (total hooks: {len(note_will_be_added._hooks)}) ===")
