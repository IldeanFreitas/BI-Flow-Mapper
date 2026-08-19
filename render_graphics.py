"""G12: geracao de imagens/SVG (ERD, arquitetura, banners) para o export
DOCX/HTML, extraido de backend.py.

Possui SEU PROPRIO lazy-loading de Pillow/cairosvg (load_pillow()/
load_cairosvg() + o estado PIL_AVAILABLE/_PILImage/.../CAIROSVG_AVAILABLE/
_cairosvg), separado do lazy-loading de pbixray/python-docx (que fica em
backend.py/doc_export.py). Cada bloco de estado mutavel por cache de import
mora no MESMO modulo que o consome como nome bare, para nao reintroduzir o
bug classico de "from modulo import NOME_MUTAVEL" (isso copiaria o valor
None/False NO MOMENTO do import, sem nunca ver a reatribuicao feita depois
por load_pillow()/load_cairosvg() -- Python nao acompanha reassign de nomes
importados por valor). Ver BACKLOG.md G12.

doc_export.py (add_cover) e o UNICO consumidor externo do estado PIL daqui;
ele acessa via `import render_graphics` + `render_graphics.PIL_AVAILABLE`/
`render_graphics._PILImage`/`render_graphics._PILDraw` qualificados (nunca
`from render_graphics import PIL_AVAILABLE`), pelo mesmo motivo acima.
"""
from __future__ import annotations

from logging_setup import logger


PIL_AVAILABLE = False
_PIL_IMPORT_ATTEMPTED = False
_PILImage = _PILDraw = _PILFont = None

CAIROSVG_AVAILABLE = False
_CAIROSVG_IMPORT_ATTEMPTED = False
_cairosvg = None


def load_pillow() -> bool:
    global PIL_AVAILABLE, _PIL_IMPORT_ATTEMPTED
    global _PILImage, _PILDraw, _PILFont
    if not _PIL_IMPORT_ATTEMPTED:
        _PIL_IMPORT_ATTEMPTED = True
        try:
            from PIL import Image, ImageDraw, ImageFont
            _PILImage, _PILDraw, _PILFont = Image, ImageDraw, ImageFont
            PIL_AVAILABLE = True
        except Exception:
            PIL_AVAILABLE = False
            logger.info("Pillow indisponivel -- banners/ERD/arquitetura do DOCX serao omitidos.", exc_info=True)
    return PIL_AVAILABLE


def load_cairosvg() -> bool:
    global CAIROSVG_AVAILABLE, _CAIROSVG_IMPORT_ATTEMPTED, _cairosvg
    if not _CAIROSVG_IMPORT_ATTEMPTED:
        _CAIROSVG_IMPORT_ATTEMPTED = True
        try:
            import cairosvg
            _cairosvg = cairosvg
            CAIROSVG_AVAILABLE = True
        except Exception:
            CAIROSVG_AVAILABLE = False
            logger.info("cairosvg indisponivel -- fallback de renderizacao SVG->PNG desativado.", exc_info=True)
    return CAIROSVG_AVAILABLE


def svg_to_png_bytes(svg_string: str, scale: float = 2.0) -> bytes | None:
    """Convert SVG to PNG via cairosvg if available (best quality)."""
    if not svg_string:
        return None
    if load_cairosvg():
        try:
            return _cairosvg.svg2png(bytestring=svg_string.encode("utf-8"), scale=scale)
        except Exception:
            logger.warning("cairosvg.svg2png falhou -- imagem SVG sera omitida do DOCX.", exc_info=True)
    return None


def _hex(color: str) -> tuple:
    """Parse #RRGGBB or #RGB to (R,G,B)."""
    c = color.lstrip("#")
    if len(c) == 3:
        c = c[0]*2 + c[1]*2 + c[2]*2
    return (int(c[0:2],16), int(c[2:4],16), int(c[4:6],16))


def _pil_png(img) -> bytes:
    from io import BytesIO as _B
    buf = _B()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_banner_png(text: str, color: str = "#0078D4", icon: str = "",
                    width: int = 1388, height: int = 56) -> bytes | None:
    """Draw a section banner using Pillow. No SVG needed."""
    if not PIL_AVAILABLE:
        return None
    try:
        img = _PILImage.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = _PILDraw.Draw(img)
        r, g, b = _hex(color)
        # Tinted background
        bg = _PILImage.new("RGBA", (width, height), (r, g, b, 28))
        img = _PILImage.alpha_composite(img, bg)
        draw = _PILDraw.Draw(img)
        # Left accent bar
        draw.rectangle([0, 0, 8, height], fill=(r, g, b, 255))
        # Text (icon + label)
        label = (icon + "  " + text) if icon else text
        # Try to use a system font; fall back gracefully
        font = None
        if not font:
            try:
                font = _PILFont.truetype("arial.ttf", 24)
            except Exception:
                pass
        if not font:
            try:
                import os
                for p in ["C:/Windows/Fonts/segoeui.ttf",
                          "C:/Windows/Fonts/arial.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                          "/System/Library/Fonts/Helvetica.ttc"]:
                    if os.path.exists(p):
                        font = _PILFont.truetype(p, 24)
                        break
            except Exception:
                pass
        if not font:
            font = _PILFont.load_default()
        draw.text((24, height // 2 - 12), label, font=font, fill=(r, g, b, 255))
        return _pil_png(img)
    except Exception:
        logger.warning("make_banner_png falhou -- banner de secao sera omitido do DOCX.", exc_info=True)
        return None


def make_erd_png(relationships: list, scale: int = 2) -> bytes | None:
    """Draw the ERD diagram using Pillow. No SVG needed."""
    if not PIL_AVAILABLE or not relationships:
        return None
    try:
        table_names = []
        seen_t: set = set()
        for rel in relationships:
            for t in [rel.get("fromTable",""), rel.get("toTable","")]:
                if t and t not in seen_t:
                    seen_t.add(t); table_names.append(t)
        table_names.sort()
        count  = len(table_names)
        NODE_W = 190; NODE_H = 48
        COLS   = min(count, max(2, int((count * 1.6) ** 0.5)))
        ROWS   = (count + COLS - 1) // COLS
        CELL_W = 270; CELL_H = 130
        PAD    = 50
        W      = max(800, COLS * CELL_W + PAD * 2)
        H      = max(340, ROWS * CELL_H + PAD * 2) + 50

        img = _PILImage.new("RGB", (W * scale, H * scale), (243, 242, 241))
        draw = _PILDraw.Draw(img)
        S = scale

        # Font
        font_sm = font_md = font_bold = None
        try:
            import os
            for p in ["C:/Windows/Fonts/segoeui.ttf",
                      "C:/Windows/Fonts/arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "/System/Library/Fonts/Helvetica.ttc"]:
                if os.path.exists(p):
                    font_sm   = _PILFont.truetype(p, 18 * S // 2)
                    font_md   = _PILFont.truetype(p, 20 * S // 2)
                    font_bold = _PILFont.truetype(p, 22 * S // 2)
                    break
        except Exception:
            pass
        if not font_sm:
            font_sm = font_md = font_bold = _PILFont.load_default()

        pos = {}
        for i, name in enumerate(table_names):
            col = i % COLS; row = i // COLS
            x = PAD + col * CELL_W + (CELL_W - NODE_W) // 2
            y = PAD + row * CELL_H + (CELL_H - NODE_H) // 2
            pos[name] = {"x": x, "y": y, "cx": x + NODE_W//2, "cy": y + NODE_H//2}

        # Draw edges first
        for rel in relationships:
            fp = pos.get(rel.get("fromTable",""))
            tp = pos.get(rel.get("toTable",""))
            if not fp or not tp: continue
            active = rel.get("active", True)
            lc = (0, 120, 212) if active else (161, 159, 157)
            x1, y1 = fp["cx"] * S, fp["cy"] * S
            x2, y2 = tp["cx"] * S, tp["cy"] * S
            # Draw line
            draw.line([(x1, y1), (x2, y2)], fill=lc, width=2 * S // 2)
            # Cardinality label at midpoint
            mx, my = (x1 + x2) // 2, (y1 + y2) // 2
            card = rel.get("cardinality", "")
            if card:
                tw = len(card) * 8 * S // 2
                draw.rectangle([mx - tw - 4, my - 10 * S // 2,
                                 mx + tw + 4, my + 10 * S // 2],
                                fill=(239, 246, 255), outline=lc, width=1)
                draw.text((mx - tw, my - 8 * S // 2), card, font=font_sm, fill=lc)

        # Draw table cards
        col_by_table: dict = {t: [] for t in table_names}
        for rel in relationships:
            for tbl, col in [(rel.get("fromTable",""), rel.get("fromColumn","")),
                             (rel.get("toTable",""),   rel.get("toColumn",""))]:
                if tbl and col and col not in col_by_table.get(tbl, []):
                    col_by_table.setdefault(tbl, []).append(col)

        for name in table_names:
            p = pos[name]
            cols = col_by_table.get(name, [])[:4]
            card_h = NODE_H + len(cols) * 20 + (8 if cols else 0)
            x, y = p["x"] * S, p["y"] * S
            w, h = NODE_W * S, card_h * S

            # Shadow
            draw.rounded_rectangle([x+3, y+3, x+w+3, y+h+3], radius=7*S//2,
                                    fill=(210, 210, 210))
            # Card body
            draw.rounded_rectangle([x, y, x+w, y+h], radius=7*S//2,
                                    fill=(255,255,255), outline=(200,198,196), width=1)
            # Header
            draw.rounded_rectangle([x, y, x+w, y+NODE_H*S], radius=7*S//2,
                                    fill=(16, 124, 16))
            draw.rectangle([x, y+(NODE_H-8)*S, x+w, y+NODE_H*S], fill=(16,124,16))

            # Table name
            short = name if len(name) <= 22 else name[:20] + "…"
            draw.text((x + 40*S//2, y + 14*S//2), short,
                      font=font_bold, fill=(255,255,255))

            # Column rows
            for ci, col in enumerate(cols):
                cy2 = y + (NODE_H + 8 + ci * 20) * S
                draw.line([(x, cy2), (x+w, cy2)], fill=(225,223,221), width=1)
                is_key = "id" in col.lower() or "key" in col.lower()
                tc = (0, 120, 212) if is_key else (59, 58, 57)
                prefix = "# " if is_key else "  "
                draw.text((x + 10*S//2, cy2 + 3*S//2),
                          prefix + col[:25], font=font_sm, fill=tc)

        # Legend
        ly = (H - 24) * S
        draw.line([(PAD*S, ly), ((PAD+26)*S, ly)], fill=(0,120,212), width=2)
        draw.text(((PAD+32)*S, ly - 6*S//2), "Ativo",   font=font_sm, fill=(96,94,92))
        draw.line([((PAD+72)*S, ly), ((PAD+98)*S, ly)], fill=(161,159,157), width=2)
        draw.text(((PAD+104)*S, ly - 6*S//2), "Inativo", font=font_sm, fill=(96,94,92))

        return _pil_png(img)
    except Exception:
        logger.warning("make_erd_png falhou -- diagrama ERD sera omitido do DOCX.", exc_info=True)
        return None


def make_arch_png(sources: list, queries: list, graph_edges: list, scale: int = 2) -> bytes | None:
    """Draw the architecture diagram using Pillow. No SVG needed."""
    if not PIL_AVAILABLE or not sources:
        return None
    try:
        CARD_W = 180; CARD_H = 52; GAP_Y = 18
        PBI_W  = 200; PBI_H  = 68; PAD_X = 60; PAD_Y = 40; COL_GAP = 140
        src_count   = len(sources)
        total_src_h = src_count * CARD_H + (src_count - 1) * GAP_Y
        H = max(280, total_src_h + PAD_Y * 2)
        W = PAD_X * 2 + CARD_W + COL_GAP + PBI_W + COL_GAP + CARD_W
        S = scale

        img = _PILImage.new("RGB", (W * S, H * S), (243, 242, 241))
        draw = _PILDraw.Draw(img)

        font_sm = font_bold = None
        try:
            import os
            for p in ["C:/Windows/Fonts/segoeui.ttf",
                      "C:/Windows/Fonts/arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "/System/Library/Fonts/Helvetica.ttc"]:
                if os.path.exists(p):
                    font_sm   = _PILFont.truetype(p, 20 * S // 2)
                    font_bold = _PILFont.truetype(p, 22 * S // 2)
                    break
        except Exception:
            pass
        if not font_sm:
            font_sm = font_bold = _PILFont.load_default()

        SRC_COLORS = {
            "sql": (0,120,212), "excel": (33,115,70), "csv": (33,115,70),
            "postgresql": (51,103,145), "mysql": (0,97,138),
            "json": (242,200,17), "web": (0,120,212), "odata": (0,120,212),
        }
        def src_color(label):
            lbl = label.lower()
            for k, c in SRC_COLORS.items():
                if k in lbl: return c
            return (27,42,56)

        # PBI node position
        pbi_x = (PAD_X + CARD_W + COL_GAP) * S
        pbi_y = ((H - PBI_H) // 2) * S
        pbi_cx = pbi_x + PBI_W * S // 2
        pbi_cy = pbi_y + PBI_H * S // 2

        # Source cards + connection lines
        src_y_start = (H - total_src_h) // 2
        for i, src in enumerate(sources):
            sx = PAD_X * S
            sy = (src_y_start + i * (CARD_H + GAP_Y)) * S
            lbl = src.get("label","Source")
            short = lbl if len(lbl) <= 20 else lbl[:18]+"…"
            r, g, b = src_color(lbl)

            # Card shadow
            draw.rounded_rectangle([sx+3, sy+3, sx+CARD_W*S+3, sy+CARD_H*S+3],
                                    radius=8*S//2, fill=(200,200,200))
            # Card body
            draw.rounded_rectangle([sx, sy, sx+CARD_W*S, sy+CARD_H*S],
                                    radius=8*S//2, fill=(r,g,b))
            # Highlight strip
            draw.rectangle([sx, sy, sx+CARD_W*S, sy+6*S//2],
                            fill=(min(r+40,255), min(g+40,255), min(b+40,255)))
            draw.text((sx + 16*S//2, sy + CARD_H*S//2 - 10*S//2),
                      short, font=font_bold, fill=(255,255,255))

            # Bezier-like connection (straight + elbow)
            src_rx = sx + CARD_W * S
            src_cy2 = sy + CARD_H * S // 2
            mx = (src_rx + pbi_x) // 2
            # Draw polyline: src_right → mid → pbi_left
            draw.line([(src_rx, src_cy2), (mx, src_cy2), (mx, pbi_cy), (pbi_x, pbi_cy)],
                      fill=(0, 120, 212, 160), width=max(1, S//2))

        # PBI Dataset node
        # Gold top/bottom bars
        draw.rounded_rectangle([pbi_x, pbi_y, pbi_x+PBI_W*S, pbi_y+PBI_H*S],
                                radius=10*S//2, fill=(27,42,56))
        draw.rectangle([pbi_x, pbi_y, pbi_x+PBI_W*S, pbi_y+8*S//2],
                        fill=(242,200,17))
        draw.rectangle([pbi_x, pbi_y+(PBI_H-6)*S//2, pbi_x+PBI_W*S, pbi_y+PBI_H*S],
                        fill=(242,200,17))
        draw.text((pbi_x + 16*S//2, pbi_y + 12*S//2),
                  "Power BI Dataset", font=font_bold, fill=(242,200,17))
        draw.text((pbi_x + 40*S//2, pbi_y + 32*S//2),
                  f"{len(sources)} fonte(s)", font=font_sm, fill=(200,200,200))

        return _pil_png(img)
    except Exception:
        logger.warning("make_arch_png falhou -- diagrama de arquitetura sera omitido do DOCX.", exc_info=True)
        return None


def build_erd_svg(relationships: list) -> str:
    """Generate a Power BI–styled ERD SVG from a list of relationship dicts."""
    # Collect unique table names
    table_names = []
    seen_t = set()
    for rel in relationships:
        for t in [rel.get("fromTable", ""), rel.get("toTable", "")]:
            if t and t not in seen_t:
                seen_t.add(t)
                table_names.append(t)
    table_names.sort()

    if not table_names:
        return ""

    count  = len(table_names)
    NODE_W = 190
    NODE_H = 46
    COLS   = min(count, max(2, int((count * 1.6) ** 0.5)))
    ROWS   = (count + COLS - 1) // COLS
    CELL_W = 270
    CELL_H = 120
    PAD_X  = 50
    PAD_Y  = 50
    SVG_W  = max(800, COLS * CELL_W + PAD_X * 2)
    SVG_H  = max(340, ROWS * CELL_H + PAD_Y * 2) + 50

    # Position map
    pos = {}
    for i, name in enumerate(table_names):
        col = i % COLS
        row = i // COLS
        pos[name] = {
            "x":  PAD_X + col * CELL_W + (CELL_W - NODE_W) // 2,
            "y":  PAD_Y + row * CELL_H + (CELL_H - NODE_H) // 2,
            "cx": PAD_X + col * CELL_W + CELL_W // 2,
            "cy": PAD_Y + row * CELL_H + CELL_H // 2,
        }

    # Crow's-foot markers
    defs_parts = []
    edge_parts = []
    label_parts = []

    CARD_MAP = {"1:M": ("one", "many"), "M:1": ("many", "one"),
                "1:1": ("one", "one"), "M:M": ("many", "many")}

    def marker_def(mid, kind, color):
        if kind == "many":
            return (
                f'<marker id="{mid}" viewBox="-2 -6 14 12" refX="11" refY="0"'
                f' markerWidth="14" markerHeight="12" orient="auto">'
                f'<line x1="0" y1="-5" x2="10" y2="0" stroke="{color}" stroke-width="1.8"/>'
                f'<line x1="0" y1="5"  x2="10" y2="0" stroke="{color}" stroke-width="1.8"/>'
                f'<line x1="0" y1="0"  x2="10" y2="0" stroke="{color}" stroke-width="1.8"/>'
                f'</marker>'
            )
        return (
            f'<marker id="{mid}" viewBox="-2 -6 12 12" refX="10" refY="0"'
            f' markerWidth="12" markerHeight="12" orient="auto">'
            f'<line x1="7" y1="-5" x2="7" y2="5" stroke="{color}" stroke-width="1.8"/>'
            f'<line x1="3" y1="-5" x2="3" y2="5" stroke="{color}" stroke-width="1.8"/>'
            f'</marker>'
        )

    for i, rel in enumerate(relationships):
        fp = pos.get(rel.get("fromTable", ""))
        tp = pos.get(rel.get("toTable", ""))
        if not fp or not tp:
            continue

        active = rel.get("active", True)
        color  = "#0078D4" if active else "#A19F9D"
        dash   = 'stroke-dasharray="6,4"' if not active else ""
        card   = rel.get("cardinality", "1:M")
        from_k, to_k = CARD_MAP.get(card, ("one", "many"))

        mid_f = f"mf{i}"
        mid_t = f"mt{i}"
        defs_parts.append(marker_def(mid_f, from_k, color))
        defs_parts.append(marker_def(mid_t, to_k, color))

        dx = tp["cx"] - fp["cx"]
        dy = tp["cy"] - fp["cy"]
        same_row = abs(dy) < CELL_H * 0.5

        if same_row:
            if dx > 0:
                x1, y1 = fp["x"] + NODE_W, fp["y"] + NODE_H // 2
                x2, y2 = tp["x"],           tp["y"] + NODE_H // 2
            else:
                x1, y1 = fp["x"],           fp["y"] + NODE_H // 2
                x2, y2 = tp["x"] + NODE_W,  tp["y"] + NODE_H // 2
            gap = abs(x2 - x1) * 0.45
            cp1x, cp1y = x1 + (gap if dx > 0 else -gap), y1
            cp2x, cp2y = x2 - (gap if dx > 0 else -gap), y2
        else:
            if dy > 0:
                x1, y1 = fp["x"] + NODE_W // 2, fp["y"] + NODE_H
                x2, y2 = tp["x"] + NODE_W // 2, tp["y"]
            else:
                x1, y1 = fp["x"] + NODE_W // 2, fp["y"]
                x2, y2 = tp["x"] + NODE_W // 2, tp["y"] + NODE_H
            gap = abs(y2 - y1) * 0.45
            cp1x, cp1y = x1, y1 + (gap if dy > 0 else -gap)
            cp2x, cp2y = x2, y2 - (gap if dy > 0 else -gap)

        sw = 2 if active else 1.5
        edge_parts.append(
            f'<path d="M {x1} {y1} C {cp1x} {cp1y}, {cp2x} {cp2y}, {x2} {y2}"'
            f' fill="none" stroke="{color}" stroke-width="{sw}" {dash}'
            f' marker-start="url(#{mid_f})" marker-end="url(#{mid_t})"/>'
        )

        # Cardinality pill at midpoint
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        lw = len(card) * 8 + 16
        lh = 20
        cf = rel.get("crossFilter", "")
        cf_icon = "⇄" if "both" in cf.lower() else "→"
        label_parts.append(
            f'<g transform="translate({mx - lw/2:.1f},{my - lh/2 - 2:.1f})">'
            f'<rect width="{lw}" height="{lh}" rx="4"'
            f' fill="{"#EFF6FF" if active else "#F3F2F1"}" stroke="{color}" stroke-width="1" opacity="0.97"/>'
            f'<text x="{lw/2:.1f}" y="{lh/2 + 4.5:.1f}" text-anchor="middle"'
            f' font-family="Consolas,monospace" font-size="10" font-weight="700" fill="{color}">{card}</text>'
            f'</g>'
            f'<text x="{mx:.1f}" y="{my + lh/2 + 11:.1f}" text-anchor="middle"'
            f' font-family="Segoe UI,Arial,sans-serif" font-size="9" fill="{color}" opacity="0.8">{cf_icon}</text>'
        )

    # Table node cards
    col_by_table: dict[str, list[str]] = {t: [] for t in table_names}
    for rel in relationships:
        ft, fc = rel.get("fromTable", ""), rel.get("fromColumn", "")
        tt, tc = rel.get("toTable", ""), rel.get("toColumn", "")
        if ft and fc and fc not in col_by_table.get(ft, []):
            col_by_table.setdefault(ft, []).append(fc)
        if tt and tc and tc not in col_by_table.get(tt, []):
            col_by_table.setdefault(tt, []).append(tc)

    card_parts = []
    for name in table_names:
        p = pos[name]
        cols = col_by_table.get(name, [])[:4]
        card_h = NODE_H + max(0, len(cols)) * 19 + (8 if cols else 0)
        short = name if len(name) <= 22 else name[:20] + "…"

        col_rows_svg = ""
        for ci, col in enumerate(cols):
            cy = NODE_H + 6 + ci * 19
            is_key = "id" in col.lower() or "key" in col.lower()
            key_prefix = "🔑 " if is_key else ""
            col_color = "#0078D4" if is_key else "#3B3A39"
            col_short = col if len(col) <= 25 else col[:23] + "…"
            col_rows_svg += (
                f'<line x1="0" y1="{cy-1}" x2="{NODE_W}" y2="{cy-1}" stroke="#E1DFDD" stroke-width="0.8"/>'
                f'<text x="10" y="{cy+12}" font-family="Segoe UI,Arial,sans-serif" font-size="10" fill="{col_color}">'
                f'{key_prefix}{col_short}</text>'
            )

        card_parts.append(
            f'<g transform="translate({p["x"]},{p["y"]})">'
            # shadow
            f'<rect x="3" y="3" width="{NODE_W}" height="{card_h}" rx="7" fill="rgba(0,0,0,0.10)"/>'
            # white body
            f'<rect width="{NODE_W}" height="{card_h}" rx="7" fill="white" stroke="#C8C6C4" stroke-width="0.8"/>'
            # header fill
            f'<rect width="{NODE_W}" height="{NODE_H}" rx="7" fill="#107C10"/>'
            f'<rect y="{NODE_H-7}" width="{NODE_W}" height="7" fill="#107C10"/>'
            # icon box
            f'<rect x="8" y="9" width="26" height="26" rx="5" fill="rgba(255,255,255,0.18)"/>'
            f'<text x="21" y="27" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="13">🗄</text>'
            # table name
            f'<text x="{NODE_W//2 + 8}" y="29" text-anchor="middle"'
            f' font-family="Segoe UI,Arial,sans-serif" font-size="11" font-weight="700" fill="white">{short}</text>'
            f'{col_rows_svg}'
            f'</g>'
        )

    # Legend
    legend = (
        f'<g transform="translate({PAD_X},{SVG_H - 30})">'
        f'<line x1="0" y1="6" x2="26" y2="6" stroke="#0078D4" stroke-width="2"/>'
        f'<text x="32" y="10" font-family="Segoe UI,Arial,sans-serif" font-size="10" fill="#605E5C">Ativo</text>'
        f'<line x1="72" y1="6" x2="98" y2="6" stroke="#A19F9D" stroke-width="1.5" stroke-dasharray="5,3"/>'
        f'<text x="104" y="10" font-family="Segoe UI,Arial,sans-serif" font-size="10" fill="#605E5C">Inativo</text>'
        f'</g>'
    )

    return (
        f'<svg viewBox="0 0 {SVG_W} {SVG_H}" width="{SVG_W}" height="{SVG_H}"'
        f' xmlns="http://www.w3.org/2000/svg"'
        f' style="background:#F3F2F1;font-family:Segoe UI,Arial,sans-serif">'
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="#F3F2F1"/>'
        f'<defs>{"".join(defs_parts)}</defs>'
        f'{"".join(edge_parts)}'
        f'{"".join(card_parts)}'
        f'{"".join(label_parts)}'
        f'{legend}'
        f'</svg>'
    )


def build_architecture_svg(sources: list, queries: list, edges: list) -> str:
    """Generate an architecture diagram SVG: Sources → [Power Query] → Power BI Dataset."""
    source_nodes = [n for n in sources]
    query_nodes  = [n for n in queries]

    if not source_nodes:
        return ""

    # Map source id → queries
    src_to_q: dict[str, list] = {s["id"]: [] for s in source_nodes}
    for e in edges:
        if e.get("from") in src_to_q:
            q = next((n for n in query_nodes if n["id"] == e.get("to")), None)
            if q:
                src_to_q[e["from"]].append(q)

    CARD_W   = 160
    CARD_H   = 52
    PBI_W    = 180
    PBI_H    = 64
    GAP_Y    = 18
    PAD_X    = 50
    PAD_Y    = 40
    COL_GAP  = 120

    src_count = len(source_nodes)
    total_src_h = src_count * CARD_H + (src_count - 1) * GAP_Y
    SVG_H = max(260, total_src_h + PAD_Y * 2)
    SVG_W = PAD_X * 2 + CARD_W + COL_GAP + PBI_W + COL_GAP + CARD_W

    parts  = []
    lines  = []

    # PBI Dataset node (center-right)
    pbi_x = PAD_X + CARD_W + COL_GAP
    pbi_y = (SVG_H - PBI_H) // 2

    # Source cards (left column)
    src_y_start = (SVG_H - total_src_h) // 2
    SRC_COLORS = {
        "sql": "#0078D4", "excel": "#217346", "csv": "#217346",
        "postgresql": "#336791", "mysql": "#00618A", "sharepoint": "#0078D4",
        "web": "#0078D4", "json": "#F2C811", "odata": "#0078D4",
    }

    def src_color(label):
        lbl = label.lower()
        for k, c in SRC_COLORS.items():
            if k in lbl:
                return c
        return "#1B2A38"

    for i, src in enumerate(source_nodes):
        sx = PAD_X
        sy = src_y_start + i * (CARD_H + GAP_Y)
        lbl = src.get("label", "Source")
        short = lbl if len(lbl) <= 20 else lbl[:18] + "…"
        color = src_color(lbl)

        # card
        parts.append(
            f'<g transform="translate({sx},{sy})">'
            f'<rect x="2" y="2" width="{CARD_W}" height="{CARD_H}" rx="8" fill="rgba(0,0,0,0.10)"/>'
            f'<rect width="{CARD_W}" height="{CARD_H}" rx="8" fill="{color}"/>'
            f'<rect width="{CARD_W}" height="6" rx="0" fill="rgba(255,255,255,0.15)" y="0"/>'
            f'<rect width="4" height="{CARD_H}" rx="0" fill="rgba(255,255,255,0.25)" x="0"/>'
            f'<text x="{CARD_W//2}" y="{CARD_H//2 + 5}" text-anchor="middle"'
            f' font-family="Segoe UI,Arial,sans-serif" font-size="11" font-weight="600" fill="white">{short}</text>'
            f'</g>'
        )

        # connection line: src card right edge → PBI node left edge
        src_cx = sx + CARD_W
        src_cy = sy + CARD_H // 2
        pbi_lx = pbi_x
        pbi_cy = pbi_y + PBI_H // 2

        # bezier
        mid_x = (src_cx + pbi_lx) // 2
        lines.append(
            f'<path d="M {src_cx} {src_cy} C {mid_x} {src_cy}, {mid_x} {pbi_cy}, {pbi_lx} {pbi_cy}"'
            f' fill="none" stroke="#0078D4" stroke-width="1.8" opacity="0.55"'
            f' stroke-dasharray="6,3"/>'
        )

    # PBI Dataset card
    parts.append(
        f'<g transform="translate({pbi_x},{pbi_y})">'
        f'<rect x="3" y="3" width="{PBI_W}" height="{PBI_H}" rx="10" fill="rgba(0,0,0,0.13)"/>'
        f'<rect width="{PBI_W}" height="{PBI_H}" rx="10" fill="#1B2A38"/>'
        f'<rect width="{PBI_W}" height="8" rx="0" fill="#F2C811" y="0"/>'
        f'<rect width="{PBI_W}" height="8" rx="0" fill="#F2C811" y="{PBI_H-8}"/>'
        f'<text x="{PBI_W//2}" y="{PBI_H//2 - 4}" text-anchor="middle"'
        f' font-family="Segoe UI,Arial,sans-serif" font-size="10" font-weight="700" fill="#F2C811">⚡ Power BI</text>'
        f'<text x="{PBI_W//2}" y="{PBI_H//2 + 12}" text-anchor="middle"'
        f' font-family="Segoe UI,Arial,sans-serif" font-size="11" font-weight="600" fill="white">Dataset</text>'
        f'</g>'
    )

    return (
        f'<svg viewBox="0 0 {SVG_W} {SVG_H}" width="{SVG_W}" height="{SVG_H}"'
        f' xmlns="http://www.w3.org/2000/svg"'
        f' style="background:#F3F2F1">'
        f'<rect width="{SVG_W}" height="{SVG_H}" fill="#F3F2F1"/>'
        f'{"".join(lines)}'
        f'{"".join(parts)}'
        f'</svg>'
    )
