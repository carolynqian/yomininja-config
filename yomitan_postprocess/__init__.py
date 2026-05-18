"""
Yomitan Post-Process

Fires synchronously on note add (Add Cards dialog OR AnkiConnect) via
`anki.hooks.note_will_be_added`. For [CURRENT] Yomitan notes tagged `yomitan`:

  1. Generates sentence audio with macOS `say -v Tingting` → m4a → writes to
     `Sentence Audio`. Uses the raw sentence (pre-bracketize).
  2. Shells out to yomitan_stylized_migaku.py --text "..." --target "..." to
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
VOICE = "Tingting"
LOG_PATH = "/tmp/yomitan_postprocess.log"


def _log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line)
    except Exception:
        pass
    print(f"[yomitan_postprocess] {msg}")


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
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    aiff = f"/tmp/yomitan_pp_{h}.aiff"
    m4a = f"/tmp/yomitan_pp_{h}.m4a"
    try:
        subprocess.run(["say", "-v", VOICE, "-o", aiff, text],
                       check=True, capture_output=True, timeout=30)
        subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", aiff, m4a],
                       check=True, capture_output=True, timeout=30)
        os.unlink(aiff)
        return m4a
    except Exception as e:
        _log(f"audio gen failed for {text[:30]!r}: {e}")
        return None


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

        # 1. Audio from raw sentence
        if not (note["Sentence Audio"] or "").strip():
            path = _make_audio(sentence)
            if path:
                fname = col.media.add_file(path)
                note["Sentence Audio"] = f"[sound:{fname}]"
                try: os.unlink(path)
                except OSError: pass

        # 2. Bracketize
        target = (note["Target Word"] or "").strip()
        bracketed = _bracketize(sentence, target)
        if bracketed:
            if not (note["Plain Sentence"] or "").strip():
                note["Plain Sentence"] = sentence
            note["Sentence"] = bracketed
    except Exception:
        _log(f"hook crash:\n{traceback.format_exc()}")


note_will_be_added.append(on_note_will_be_added)
_log(f"=== addon loaded, hook registered (total hooks: {len(note_will_be_added._hooks)}) ===")
