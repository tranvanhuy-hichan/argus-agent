#!/usr/bin/env python3
"""Turn Markdown into a self-contained HTML slide deck (arrow keys / swipe to navigate, F = fullscreen,
Ctrl+P prints one slide per page, so it also exports to PDF). Standard library only.

Usage: md2slides.py deck.md deck.html [--title "Deck title"]
Markdown format:
  # Deck title            -> title slide (the next lines are the subtitle)
  ## Slide title          -> starts a new slide
  - bullet / 1. numbered  -> list (indent two spaces for sub-bullets)
  ![caption](image.png)   -> image (embedded into the file)
  > text                  -> large highlighted quote or key number
  Notes: text             -> speaker notes (press N to show)
"""
import base64
import mimetypes
import re
import sys
from html import escape
from pathlib import Path

CSS = """
:root{--bg:#fff;--fg:#14213d;--muted:#5b6475;--accent:#2563eb;--panel:#f1f5f9}
@media (prefers-color-scheme:dark){:root{--bg:#0b1020;--fg:#eef2ff;--muted:#a3adc2;--accent:#6ea8ff;--panel:#161d33}}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.slide{display:none;position:absolute;inset:0;padding:6vh 8vw;flex-direction:column;justify-content:center;gap:2.2vh}
.slide.on{display:flex}
h1{font-size:6vw;margin:0;line-height:1.1}h2{font-size:3.6vw;margin:0 0 1vh;color:var(--accent);line-height:1.15}
.sub{font-size:2.2vw;color:var(--muted)}
ul,ol{font-size:2.5vw;line-height:1.5;margin:0;padding-left:2.2em}ul ul,ol ul{font-size:2.1vw;color:var(--muted)}
li{margin:.4vh 0}
blockquote{margin:0;padding:3vh 3vw;font-size:3.4vw;font-weight:600;background:var(--panel);border-left:.6vw solid var(--accent);border-radius:.8vw}
img{max-width:100%;max-height:52vh;object-fit:contain;border-radius:.8vw;align-self:center}
figure{margin:0;display:flex;flex-direction:column;align-items:center;gap:1vh}figcaption{font-size:1.6vw;color:var(--muted)}
.notes{display:none;position:fixed;left:0;right:0;bottom:0;background:var(--panel);padding:2vh 4vw;font-size:1.8vw;border-top:2px solid var(--accent)}
body.notes-on .slide.on .notes{display:block}
.count{position:fixed;right:2vw;bottom:1.5vh;font-size:1.3vw;color:var(--muted)}
.bar{position:fixed;left:0;top:0;height:.6vh;background:var(--accent);transition:width .2s}
@media print{@page{size:landscape;margin:0}.slide{display:flex!important;position:relative;height:100vh;page-break-after:always}.count,.bar{display:none}.notes{display:none!important}}
"""
JS = """
const S=[...document.querySelectorAll('.slide')];let i=0;
const go=n=>{i=Math.max(0,Math.min(S.length-1,n));S.forEach((s,k)=>s.classList.toggle('on',k===i));
document.getElementById('c').textContent=(i+1)+' / '+S.length;document.getElementById('b').style.width=((i+1)/S.length*100)+'%';location.hash=i+1};
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' ','Enter'].includes(e.key))go(i+1);
if(['ArrowLeft','PageUp','Backspace'].includes(e.key))go(i-1);if(e.key==='Home')go(0);if(e.key==='End')go(S.length);
if(e.key==='f')document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
if(e.key==='n')document.body.classList.toggle('notes-on')});
let x0=null;addEventListener('touchstart',e=>x0=e.touches[0].clientX);addEventListener('touchend',e=>{if(x0===null)return;const d=e.changedTouches[0].clientX-x0;if(Math.abs(d)>40)go(i+(d<0?1:-1));x0=null});
addEventListener('click',e=>{if(e.target.tagName!=='A')go(i+(e.clientX<innerWidth/4?-1:1))});
go((parseInt(location.hash.slice(1))||1)-1);
"""


def inline(t):
    t = escape(t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)


def image(alt, src, base):
    p = (base / src)
    if src.startswith(("http://", "https://", "data:")):
        url = src
    elif p.is_file():
        url = f"data:{mimetypes.guess_type(p.name)[0] or 'image/png'};base64,{base64.b64encode(p.read_bytes()).decode()}"
    else:
        return f"<p class='sub'>[missing image: {escape(src)}]</p>"
    return f"<figure><img src='{url}' alt='{escape(alt)}'>" + (f"<figcaption>{escape(alt)}</figcaption>" if alt else "") + "</figure>"


def render(md, base, title):
    slides, cur = [], None
    for ln in md.splitlines():
        if ln.startswith("# ") and cur is None:
            cur = {"kind": "title", "title": ln[2:].strip(), "lines": []}
            slides.append(cur)
        elif ln.startswith("## ") or (ln.startswith("# ") and cur):
            cur = {"kind": "slide", "title": ln.lstrip("# ").strip(), "lines": []}
            slides.append(cur)
        elif cur is not None:
            cur["lines"].append(ln)
    out = []
    for s in slides:
        body, notes, lst = [], [], None

        def close():
            nonlocal lst
            if lst:
                body.append(f"</{lst}>")
                lst = None
        for ln in s["lines"]:
            raw = ln.rstrip()
            if not raw.strip():
                continue
            if raw.lower().startswith("notes:"):
                notes.append(raw[6:].strip())
                continue
            im = re.match(r"^!\[(.*?)\]\((.*?)\)", raw.strip())
            li = re.match(r"^(\s*)([-*]|\d+[.)])\s+(.*)", raw)
            if im:
                close()
                body.append(image(im.group(1), im.group(2), base))
            elif li:
                kind = "ol" if li.group(2)[0].isdigit() else "ul"
                if lst != kind and not li.group(1):
                    close()
                    body.append(f"<{kind}>")
                    lst = kind
                pad = " style='margin-left:2em'" if li.group(1) else ""
                body.append(f"<li{pad}>{inline(li.group(3))}</li>")
            elif raw.startswith(">"):
                close()
                body.append(f"<blockquote>{inline(raw.lstrip('> '))}</blockquote>")
            else:
                close()
                body.append(f"<p class='sub'>{inline(raw.strip())}</p>")
        close()
        head = f"<h1>{inline(s['title'])}</h1>" if s["kind"] == "title" else f"<h2>{inline(s['title'])}</h2>"
        n = f"<div class='notes'>{inline(' '.join(notes))}</div>" if notes else ""
        out.append(f"<section class='slide'>{head}{''.join(body)}{n}</section>")
    first = re.search(r"^# (.*)", md, re.M)
    t = title or (first.group(1) if first else "Presentation")
    return (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{escape(t)}</title>"
            f"<style>{CSS}</style></head><body><div class='bar' id='b'></div>{''.join(out)}<div class='count' id='c'></div><script>{JS}</script></body></html>")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 2:
        sys.exit(__doc__)
    ttl = sys.argv[sys.argv.index("--title") + 1] if "--title" in sys.argv else ""
    Path(a[1]).write_text(render(Path(a[0]).read_text(encoding="utf-8"), Path(a[0]).resolve().parent, ttl), encoding="utf-8")
    print(f"Wrote {a[1]}")
