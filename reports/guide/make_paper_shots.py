"""Cut the paper into one screenshot per part (paragraph, table or figure).

Positions are in PDF points measured from the top of the page, found from the text layer of the compiled paper
(`paper/Automated_Design_....pdf`, 8 pages). A part that continues into the next column or page is several
segments stitched top to bottom. Writes reports/guide/paper_shots/<name>.png.

    python reports/guide/make_paper_shots.py
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
PDF = next((ROOT / "paper").glob("Automated_Design_*.pdf"))
OUT = Path(__file__).resolve().parent / "paper_shots"
SCALE = 200 / 72  # pixels per point
COLS = {"L": (42, 305), "R": (307, 572), "F": (40, 574)}
TOP, BOTTOM = 48, 752

pdf = pdfium.PdfDocument(str(PDF))
pages = [pdf[i].render(scale=SCALE).to_pil().convert("RGB") for i in range(len(pdf))]


def blank(img: Image.Image, y_pt: float, col: str) -> bool:
    x0, x1 = (int(v * SCALE) for v in COLS[col])
    y = int(y_pt * SCALE)
    row = img.crop((x0, y, x1, y + 1)).convert("L")
    return min(row.tobytes()) > 235


def scan(page: int, col: str, start: float, step: float, gap: float = 9.0) -> float:
    """From ``start`` move up (step < 0) or down until ``gap`` points of blank rows are passed."""
    img, y, run = pages[page - 1], start, 0.0
    while TOP - 10 < y < BOTTOM + 30:
        run = run + abs(step) if blank(img, y, col) else 0.0
        if run >= gap:
            return y - step * (gap / abs(step))
        y += step
    return y


def table_box(page: int, col: str, caption_top: float) -> tuple[float, float]:
    """A table: caption on top, the table below, ending at the first big blank gap."""
    y = caption_top + 30  # past the caption lines
    return caption_top - 3, scan(page, col, y, 1)


def figure_box(page: int, col: str, caption_top: float) -> tuple[float, float]:
    """A figure: image above the caption, caption below; stop at blank gaps on both sides."""
    return scan(page, col, caption_top - 12, -1), scan(page, col, caption_top + 2, 1, gap=7)


def segment(page: int, col: str, y0: float, y1: float) -> Image.Image:
    img = pages[page - 1]
    x0, x1 = COLS[col]
    # Positions are written 3 pt above the first line of a part; a line's text starts about 1.2 pt
    # below that mark, so start just inside it and stop just above the next part's first line.
    y0 += 1.2
    y1 += 1.2
    # trim blank rows at both ends
    while y0 < y1 and blank(img, y0, col):
        y0 += 0.5
    while y1 > y0 and blank(img, y1, col):
        y1 -= 0.5
    return img.crop((int((x0 - 2) * SCALE), int(y0 * SCALE), int((x1 + 2) * SCALE), int((y1 + 1) * SCALE)))


def stitch(parts: list[Image.Image]) -> Image.Image:
    width = max(p.width for p in parts)
    sep = 18
    height = sum(p.height for p in parts) + sep * (len(parts) - 1)
    out = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(out)
    y = 0
    for i, p in enumerate(parts):
        out.paste(p, (0, y))
        y += p.height
        if i < len(parts) - 1:  # a dashed line marks where the text continues in the next column
            for x in range(0, width, 16):
                draw.line((x, y + sep // 2, x + 8, y + sep // 2), fill=(150, 150, 150), width=2)
            y += sep
    return out


# Float boxes found from their captions.
T1 = table_box(4, "F", 54)
# Figures 1 and 2 have white margins inside the image, so their top is set from what lies above them:
# Table I for Figure 1, the top of the column for Figure 2.
F1 = (T1[1] + 3, scan(4, "F", 404, 1, gap=7))
T2 = table_box(5, "R", 54)
T3 = table_box(7, "F", 54)
F2 = (TOP, scan(6, "R", 242, 1, gap=7))
F3 = figure_box(6, "R", 444)
T4 = table_box(7, "R", 240)
T5 = table_box(8, "L", 54)
after = lambda box: box[1] + 2  # noqa: E731  text that resumes below a float

SHOTS: dict[str, list[tuple]] = {
    "title": [(1, "F", 40, 270)],
    "abstract": [(1, "L", 276, 514)],
    "intro1": [(1, "L", 517, 664)],
    "intro2": [(1, "L", 664, 730), (1, "R", 276, 408)],
    "intro3": [(1, "R", 408, 515)],
    "contrib": [(1, "R", 515, BOTTOM), (2, "L", TOP, 116)],
    "s_massive": [(2, "L", 116, 288)],
    "s_larson": [(2, "L", 288, 372)],
    "s_chen": [(2, "L", 372, 468)],
    "s_conneau": [(2, "L", 468, 548)],
    "s_brown": [(2, "L", 548, 647)],
    "s_liu": [(2, "L", 647, BOTTOM), (2, "R", TOP, 80)],
    "s_zhou": [(2, "R", 80, 181)],
    "s_pryzant": [(2, "R", 181, 289)],
    "s_yang": [(2, "R", 289, 372)],
    "s_khattab": [(2, "R", 372, 488)],
    "s_prompt2model": [(2, "R", 488, 595)],
    "s_madaan": [(2, "R", 595, 695)],
    "s_yao": [(2, "R", 695, BOTTOM), (3, "L", TOP, 128)],
    "s_bergstra": [(3, "L", 128, 240)],
    "s_he": [(3, "L", 240, 331)],
    "gap": [(3, "L", 331, 532)],
    "table1": [(4, "F", *T1)],
    "formulation": [(3, "L", 532, BOTTOM), (3, "R", TOP, 82)],
    "fig1": [(4, "F", *F1)],
    "design_space": [(3, "R", 82, 316)],
    "rejection": [(3, "R", 316, 487)],
    "phase1": [(3, "R", 487, 667)],
    "phase2": [(3, "R", 667, BOTTOM), (4, "L", after(F1), 630)],
    "phase3": [(4, "L", 630, BOTTOM), (4, "R", after(F1), 438)],
    "phase4": [(4, "R", 438, 617)],
    "phase5": [(4, "R", 617, BOTTOM), (5, "L", TOP, 201)],
    "phase6": [(5, "L", 201, 395)],
    "span_rule": [(5, "L", 395, 510)],
    "metrics": [(5, "L", 510, BOTTOM), (5, "R", after(T2), 192)],
    "dataset": [(5, "R", 192, 412)],
    "table2": [(5, "R", *T2)],
    "heldout_lock": [(5, "R", 412, 503)],
    "model": [(5, "R", 503, 656)],
    "baselines": [(5, "R", 656, BOTTOM), (6, "L", TOP, 213)],
    "stats": [(6, "L", 213, 404)],
    "table3": [(7, "F", *T3)],
    "overall": [(6, "L", 404, 515)],
    "fig2": [(6, "R", *F2)],
    "success": [(6, "L", 515, 623)],
    "significance": [(6, "L", 623, BOTTOM), (6, "R", after(F3), 524)],
    "fig3": [(6, "R", *F3)],
    "vs_random": [(6, "R", 524, 659)],
    "vs_human": [(6, "R", 659, BOTTOM), (7, "L", after(T3), 265)],
    "vs_xlmr": [(7, "L", 265, 429)],
    "why": [(7, "L", 429, 659)],
    "table4": [(7, "R", *T4)],
    "honesty": [(7, "L", 659, BOTTOM)],
    "p3": [(7, "R", 376, 556)],
    "ablations": [(7, "R", 556, BOTTOM)],
    "table5": [(8, "L", *T5)],
    "cost": [(8, "L", 172, 341)],
    "conclusion": [(8, "L", 341, 533)],
    "ack": [(8, "L", 533, 629)],
    "refs": [(8, "L", 629, BOTTOM), (8, "R", TOP, BOTTOM)],
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    for name, segs in SHOTS.items():
        stitch([segment(*s) for s in segs]).save(OUT / f"{name}.png")
    print(f"wrote {len(SHOTS)} screenshots to {OUT.relative_to(ROOT)}")
    print("floats:", {k: tuple(round(v) for v in b) for k, b in
                      {"T1": T1, "F1": F1, "T2": T2, "T3": T3, "F2": F2, "F3": F3, "T4": T4, "T5": T5}.items()})


if __name__ == "__main__":
    main()
