# /// script
# requires-python = ">=3.10"
# dependencies = ["jieba", "pypinyin"]
# ///
"""
Convert Yomitan-created Anki cards to Migaku bracket-pinyin format so the
hover-pinyin in the [CURRENT] Yomitan template lights up.

- Reads `Sentence` from every note tagged `yomitan` in `[CURRENT] Yomitan`.
- Segments with jieba.posseg, tones with pypinyin (Style.TONE3 + neutral=5).
- Rewrites `Sentence` as `汉字[pinyin;pos]`, wrapping the target word in <t>.
- Copies the raw sentence into `Plain Sentence` so HyperTTS / lookups still work.
- Idempotent: skips notes whose `Sentence` already has brackets.

Run:   uv run yomitan_stylized_migaku.py
"""

import json
import re
import urllib.request

import jieba.posseg as pseg
from pypinyin import lazy_pinyin, Style

ANKICONNECT = "http://localhost:8765"
NOTE_TYPE = "[CURRENT] Yomitan"
TAG = "yomitan"

CHINESE_RE = re.compile(r"[一-鿿]+")


def anki(action, **params):
    req = json.dumps({"action": action, "version": 6, "params": params}).encode()
    with urllib.request.urlopen(ANKICONNECT, req) as r:
        result = json.loads(r.read())
    if result.get("error"):
        raise RuntimeError(f"{action}: {result['error']}")
    return result["result"]


def to_bracket(sentence: str, target_word: str) -> str:
    out = []
    for word, pos in pseg.cut(sentence):
        if CHINESE_RE.fullmatch(word):
            py = " ".join(
                lazy_pinyin(word, style=Style.TONE3, neutral_tone_with_five=True)
            )
            token = f"{word}[{py};{pos}]"
            if target_word and word == target_word:
                token = f"<t>{token}</t>"
            out.append(token)
        else:
            out.append(word)
    return "".join(out)


def main():
    ids = anki("findNotes", query=f'note:"{NOTE_TYPE}" tag:{TAG}')
    notes = anki("notesInfo", notes=ids) if ids else []
    converted = skipped = 0
    for n in notes:
        f = n["fields"]
        sentence = f["Sentence"]["value"]
        if not sentence.strip() or ("[" in sentence and "]" in sentence):
            skipped += 1
            continue
        target = f["Target Word"]["value"].strip()
        fields = {"Sentence": to_bracket(sentence, target)}
        if not f["Plain Sentence"]["value"].strip():
            fields["Plain Sentence"] = sentence
        anki("updateNoteFields", note={"id": n["noteId"], "fields": fields})
        converted += 1
    print(f"converted {converted}, skipped {skipped}")


if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="Sentence to bracketize; prints to stdout. "
                                   "If omitted, runs AnkiConnect backfill.")
    ap.add_argument("--target", default="", help="Target word to wrap in <t>")
    args = ap.parse_args()
    if args.text is not None:
        sys.stdout.write(to_bracket(args.text, args.target))
    else:
        main()
