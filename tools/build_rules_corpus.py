"""Turn official LOTR LCG rules PDFs into searchable markdown in `research/rules/`.

The corpus this writes is the primary-source half of CLAUDE.md's rule 4: the
compiled card data answers "which scenario prints what", and this answers "what
does the rulebook actually say". Before it existed, every rules claim in UI copy
was checked against the DragnCards step labels and community guides, which is
how "highest engagement cost first" sat on screen for months marked
*unverified* - it turned out to be exactly right (Rules Reference 6.2), but
nothing local could show it.

**Gitignored, like `research/votp/`.** This is verbatim FFG text, so it never
ships and is never committed (CLAUDE.md's data policy: verbatim vs derived).
It lives vault-side so it can be read in Obsidian next to `quests/` and
`rules/`, and it is indexed by qmd for semantic search - see `rules/README.md`.

## Why liteparse and not pdftotext

The rulebooks are two-column. `pdftotext` without `-layout` runs the columns
together in reading order; with `-layout` it keeps them side by side on one
line, so every line holds a fragment of two unrelated sentences:

    5.2 Optional engagement          Deal one card from the encounter deck,

Either way sentences are shredded - fine for grep, useless for semantic search,
since an embedding of that line means nothing. LiteParse reconstructs the
columns from the PDF's own geometry and emits real markdown, turning each
numbered rule step ("6.4a Next enemy attack initiates") into an `##` heading.
Those headings are what make a qmd hit land on the step rather than mid-page.

Needs `lit` (`npm i -g @llamaindex/liteparse`). No Python dependencies.
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "research", "rules")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build(path, title=None, dpi=150, ocr=True):
    title = title or os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join(OUT_DIR, slugify(title) + ".md")

    cmd = ["lit", "parse", path, "--format", "markdown", "-o", dest,
           "--dpi", str(dpi), "--image-mode", "off", "-q"]
    if not ocr:
        cmd.append("--no-ocr")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise SystemExit("lit not found - npm i -g @llamaindex/liteparse")
    except subprocess.CalledProcessError as e:
        print("  FAILED %s: %s" % (os.path.basename(path),
                                   e.stderr.strip()[-300:]), file=sys.stderr)
        return None

    with open(dest) as f:
        body = f.read()
    # Front matter: qmd shows it in results, and it keeps the provenance
    # attached to the text rather than only in this script.
    head = ("---\ntitle: %s\nsource_pdf: %s\nkind: rules-primary\n---\n\n"
            "> Verbatim FFG rules text, parsed locally for search. Not for "
            "redistribution.\n\n" % (title, os.path.basename(path)))
    with open(dest, "w") as f:
        f.write(head + body)

    print("  %-44s %6d words" % (os.path.basename(dest), len(body.split())))
    return dest


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdfs", nargs="+", help="rules PDFs to parse")
    ap.add_argument("--title", help="title for a single PDF (default: filename)")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--no-ocr", action="store_true",
                    help="skip OCR (much faster; text-based PDFs only)")
    args = ap.parse_args()

    if args.title and len(args.pdfs) > 1:
        raise SystemExit("--title takes a single PDF")

    os.makedirs(OUT_DIR, exist_ok=True)
    print("writing to %s" % OUT_DIR)
    for p in args.pdfs:
        if not os.path.exists(p):
            print("  SKIP (missing): %s" % p, file=sys.stderr)
            continue
        build(p, args.title, args.dpi, ocr=not args.no_ocr)


if __name__ == "__main__":
    main()
