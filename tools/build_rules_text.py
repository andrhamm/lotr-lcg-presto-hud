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

# Assumes a step's title text never itself contains an N.N-shaped token (a
# card cost, a page number, a quoted rule id) - such a token would be read as
# a second merged step id splitting the title in the wrong place.
STEP_RE = re.compile(r"(\d+\.\d+(?:[ab]|\.\d+)?)\s+(.+?)(?=\s+\d+\.\d+(?:[ab]|\.\d+)?\s+|$)")
# The corpus writes "See also:" cross-references two ways - as a "######"
# subheading (most entries) and, less often, bolded inline ("**See also:
# ...**"); both are matched here so neither leaks into `text`. A long list
# wraps onto a second markdown line (a blank line, then the remaining terms)
# before the entry's separator or the next heading - see parse()'s handling
# of cur["collecting_see_also"].
SEE_ALSO_RE = re.compile(r"^(?:#{2,6}|\*\*)\s*See also:\s*(.+?)\*{0,2}\s*$", re.I)
# The corpus separates glossary entries (and, less often, marks a two-column
# page break mid-paragraph) with a bare "-----" line - never real body text.
SEP_RE = re.compile(r"^-{3,}\s*$")

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
        # (a) a separator is never body text, in any state - it marks either
        # an entry boundary or, mid-paragraph, a two-column page break.
        if SEP_RE.match(line):
            continue
        # (b) once a "See also:" line has matched, a wrapped continuation
        # (the remaining terms, one blank line down) still needs to land in
        # see_also rather than body. The blank line right after the match is
        # tolerated rather than ending collection - the corpus always puts
        # exactly one before the wrapped terms - and collection only really
        # ends at the next heading (handled below) or separator (above).
        if cur is not None and cur.get("collecting_see_also"):
            if line.strip() == "":
                continue
            if not line.startswith("#"):
                cur["rec"]["see_also"].extend(t.strip() for t in line.split(",") if t.strip())
                continue
            cur["collecting_see_also"] = False  # a heading: fall through and end it below
        m = SEE_ALSO_RE.match(line)
        if m and cur is not None:
            cur["rec"]["see_also"] = [t.strip() for t in m.group(1).split(",") if t.strip()]
            cur["collecting_see_also"] = True
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
    pin = _pin()
    generated = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    doc.update({"generated": generated, "book": "Rules Reference",
                "source": {"sha256": hashlib.sha256(md.encode("utf-8")).hexdigest(), "page": pin.get("page", ""), "pin": pin.get("sha256", "")}})
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
