"""Parse the liteparse markdown of the Rules Reference into docs/data/rules_text.json.

The corpus (research/rules/, gitignored, built by build_rules_corpus.py) is
verbatim FFG text and never ships as a corpus; this tool ships EXCERPTS as a
build artifact under docs/data/ - the same gitignored, regenerated posture as
the compiled card DB (CLAUDE.md, "What may be committed"). Every numbered
turn step ("###### 6.4a Next enemy attack initiates") becomes a section keyed
by its id; glossary entries ("##### Player Elimination") become glossary
records. liteparse sometimes merges two consecutive steps onto one heading
("###### 1.3 Draw cards 1.4 Resource phase ends"); both ids then share one
record (plan ruling R2). No third-party fetch happens here: the PDF pin in
tools/data/rules.SOURCE.txt is checked, never downloaded, by this tool.
"""
import argparse, datetime, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DEFAULT_CORPUS = os.path.join(ROOT, "research", "rules")
DEFAULT_NAME = "rules-reference.md"
DEFAULT_OUT = os.path.join(ROOT, "docs", "data", "rules_text.json")
SOURCE = os.path.join(HERE, "data", "rules.SOURCE.txt")

STEP_RE = re.compile(r"(\d+\.\d+(?:[ab]|\.\d+)?)\s+(.+?)(?=\s+\d+\.\d+(?:[ab]|\.\d+)?\s+|$)")
SEE_ALSO_RE = re.compile(r"^#{2,6}\s*See also:\s*(.+?)\s*$", re.I)

def _clean(lines):
    text = "\n".join(lines).strip()
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def parse(md):
    sections, glossary, cur, body = {}, {}, None, []
    def flush():
        if cur is None: return
        rec = cur["rec"]; rec["text"] = _clean(body); body.clear()
    for line in md.splitlines():
        m = SEE_ALSO_RE.match(line)
        if m and cur is not None:
            cur["rec"]["see_also"] = [t.strip() for t in m.group(1).split(",") if t.strip()]
            continue
        if line.startswith("###### "):
            flush(); head = line[7:].strip()
            steps = STEP_RE.findall(head)
            if not steps: cur = None; continue
            rec = {"ids": [i for i, _ in steps], "title": " · ".join(t.strip() for _, t in steps), "text": "", "see_also": []}
            for i, _ in steps: sections[i] = rec
            cur = {"rec": rec}; continue
        if line.startswith("##### "):
            flush(); term = line[6:].strip()
            rec = {"title": term, "text": "", "see_also": []}; glossary[term] = rec; cur = {"rec": rec}; continue
        if line.startswith("#"):
            flush(); cur = None; continue
        if cur is not None: body.append(line)
    flush()
    return {"sections": sections, "glossary": glossary, "faq": []}

def _pin():
    if not os.path.exists(SOURCE): return {}
    return dict(l.strip().split("=", 1) for l in open(SOURCE) if "=" in l)

def build(corpus_dir, out_path=DEFAULT_OUT, corpus_name=DEFAULT_NAME):
    path = os.path.join(corpus_dir, corpus_name)
    if not os.path.exists(path):
        raise SystemExit("rules corpus not found at %s - build it with tools/build_rules_corpus.py (see rules/README.md; research/rules is gitignored and lives in the main checkout)" % path)
    md = open(path, encoding="utf-8").read()
    doc = parse(md)
    doc.update({"generated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "book": "Rules Reference",
                "source": {"sha256": hashlib.sha256(md.encode("utf-8")).hexdigest(), "page": _pin().get("page", ""), "pin": _pin().get("sha256", "")}})
    # ids that alias one record must serialise once each - JSON has no shared refs, so emit per id.
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print("wrote %s: %d sections, %d glossary entries" % (out_path, len(set(map(id, doc["sections"].values()))), len(doc["glossary"])))

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS); ap.add_argument("--corpus-name", default=DEFAULT_NAME)
    ap.add_argument("--out", default=DEFAULT_OUT); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    if os.path.exists(a.out) and not a.force:
        print("%s already exists - nothing to do (--force to rebuild)" % a.out); return 0
    build(a.corpus, a.out, a.corpus_name); return 0

if __name__ == "__main__":
    sys.exit(main())
