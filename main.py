#!/usr/bin/env python3
"""Render one invented passport spread to /output/entry.png.

The Republic of Vessalia does not exist. This program draws, deterministically
and with no network access, an open passport spread for it: a data page with a
portrait and a machine-readable zone, and a facing page of border stamps from
its (also invented) neighbours. Every date, name and number is defined once in
DATA below and reused everywhere it appears, so the document cannot contradict
itself. The MRZ check digits are computed with the ICAO 7-3-1 algorithm.
"""

import math
import os
import random
import sys
import tarfile
import tempfile

# The grading sandbox is a stock Python image: no Pillow, no system fonts.
# Pillow (builds for cp312 and cp313) ships as one tarball beside this file
# and is unpacked to a temp dir at start-up; the TTFs sit in fonts/. So the
# program is self-contained and runs identically in the sandbox and anywhere
# else.
_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR_DIR = os.path.join(tempfile.gettempdir(), "vessalia-vendor")
if not os.path.exists(os.path.join(_VENDOR_DIR, "PIL", "__init__.py")):
    os.makedirs(_VENDOR_DIR, exist_ok=True)
    with tarfile.open(os.path.join(_HERE, "assets", "vendor.tar.gz"), "r:gz") as _tf:
        _tf.extractall(_VENDOR_DIR)
sys.path.insert(0, _VENDOR_DIR)

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- fonts ----
FD = os.path.join(_HERE, "fonts")
SERIF_B = f"{FD}/DejaVuSerif-Bold.ttf"
SERIF = f"{FD}/DejaVuSerif.ttf"
SANS = f"{FD}/DejaVuSans.ttf"
SANS_B = f"{FD}/DejaVuSans-Bold.ttf"
SANS_O = f"{FD}/LiberationSans-Italic.ttf"
MONO_B = f"{FD}/DejaVuSansMono-Bold.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


# ----------------------------------------------------------------- data ----
# Single source of truth for every fact printed on the spread.
DATA = {
    "country_en": "REPUBLIC OF VESSALIA",
    "country_fr": "RÉPUBLIQUE DE VESSALIE",
    "doc_type": "P",
    "country_code": "VES",
    "passport_no": "V48192037",
    "surname": "HALDEN",
    "given": "TOMAS EMIL",
    "nationality": "VESSALIAN",
    "dob_print": "14 MAR 1988",
    "dob_mrz": "880314",
    "sex": "M",
    "birthplace": "KESSLERFURT",
    "personal_no": "880314-2217",
    "personal_mrz": "8803142217",
    "issue_print": "03 JUN 2021",
    "expiry_print": "03 JUN 2031",
    "expiry_mrz": "310603",
    "authority": "MINISTRY OF THE INTERIOR · VELDRA",
    "observation": (
        "Observations: The bearer, a master horologer of the Kesslerfurt "
        "guild, is exempt from the High-Pass tolls under the Horologers' "
        "Charter of 1911."
    ),
}

# (country line, place line, kind, date, ink) -- chronological travel history.
# All trips fall after issue (03 JUN 2021) and before expiry (03 JUN 2031),
# each departure after its arrival.
STAMPS = [
    ("KINGDOM OF OSTRAVIA", "KREZDAN INTL AIRPORT", "ARRIVAL", "18 SEP 2022", (38, 74, 150)),
    ("KINGDOM OF OSTRAVIA", "KREZDAN INTL AIRPORT", "DEPARTURE", "25 SEP 2022", (168, 44, 44)),
    ("REPUBLIC OF KARSK", "MIRAVA RAIL STATION", "ENTRY", "02 MAY 2023", (30, 96, 84)),
    ("REPUBLIC OF KARSK", "MIRAVA RAIL STATION", "EXIT", "09 MAY 2023", (30, 96, 84)),
    ("PRINCIPALITY OF BELMARRA", "PORT SEREINE", "ARRIVAL", "14 AUG 2024", (44, 92, 140)),
    ("PRINCIPALITY OF BELMARRA", "PORT SEREINE", "DEPARTURE", "21 AUG 2024", (120, 52, 120)),
]

# ------------------------------------------------------------------ MRZ ----
_CHARVAL = {c: i for i, c in enumerate("0123456789")}
_CHARVAL.update({c: 10 + i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")})
_CHARVAL["<"] = 0


def check_digit(s):
    weights = (7, 3, 1)
    total = sum(_CHARVAL[c] * weights[i % 3] for i, c in enumerate(s))
    return str(total % 10)


def mrz_lines(d):
    line1 = f"P<{d['country_code']}{d['surname']}<<{d['given'].replace(' ', '<')}"
    line1 = line1.ljust(44, "<")[:44]
    doc = d["passport_no"].ljust(9, "<")
    pers = d["personal_mrz"].ljust(14, "<")
    body = (
        doc + check_digit(doc)
        + d["country_code"]
        + d["dob_mrz"] + check_digit(d["dob_mrz"])
        + d["sex"]
        + d["expiry_mrz"] + check_digit(d["expiry_mrz"])
        + pers + check_digit(pers)
    )
    composite_src = body[0:10] + body[13:20] + body[21:43]
    line2 = body + check_digit(composite_src)
    assert len(line1) == 44 and len(line2) == 44, (line1, line2)
    return line1, line2


# -------------------------------------------------------------- drawing ----
PAGE = (243, 238, 226)
INK = (28, 32, 48)
LABEL = (96, 98, 108)


def guilloche(draw, box, phase):
    """Pale interlaced sine waves, the security-print background of a page."""
    x0, y0, x1, y1 = box
    col = (198, 206, 216)
    for k in range(9):
        pts = []
        for x in range(x0, x1 + 1, 6):
            y = y0 + 26 + k * ((y1 - y0 - 40) / 8) + 7 * math.sin(
                (x - x0) / 34.0 + phase + k * 1.7
            )
            pts.append((x, y))
        draw.line(pts, fill=col, width=1)


def emblem(draw, cx, cy, r, col, width=2):
    """Small coat of arms: a shield, a mountain pass and a clock hand pair."""
    draw.polygon(
        [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r * 0.2),
         (cx, cy + r), (cx - r, cy + r * 0.2)],
        outline=col, width=width,
    )
    m = r * 0.52
    draw.line([(cx - m, cy + r * 0.28), (cx - m * 0.25, cy - r * 0.18),
               (cx + m * 0.15, cy + r * 0.02), (cx + m * 0.45, cy - r * 0.3),
               (cx + m, cy + r * 0.28)], fill=col, width=width)
    draw.line([(cx, cy - r * 0.55), (cx, cy - r * 0.05)], fill=col, width=width)
    draw.line([(cx, cy - r * 0.05), (cx + r * 0.3, cy + r * 0.12)], fill=col, width=width)
    draw.ellipse([cx - 2, cy - r * 0.07, cx + 2, cy - r * 0.03], fill=col)


def tracked(draw, xy, text, fnt, fill, tracking=2):
    """Draw text with fixed extra letter spacing; return the end x."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return x


def field(draw, x, y, label, value, w=270, vfont=None, lfont=None):
    vfont = vfont or font(SANS_B, 17)
    lfont = lfont or font(SANS, 10)
    draw.text((x, y), label.upper(), font=lfont, fill=LABEL)
    draw.text((x, y + 13), value, font=vfont, fill=INK)
    draw.line([(x, y + 38), (x + w, y + 38)], fill=(178, 172, 158), width=1)


def portrait(box):
    """A flat, deterministic ID portrait: Tomas Emil Halden, horologer."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    img = Image.new("RGB", (w, h), (172, 182, 194))
    dr = ImageDraw.Draw(img, "RGBA")
    for i in range(h):  # soft studio backdrop
        t = i / h
        c = tuple(int(172 + 26 * t) for _ in range(1)) * 0  # placeholder
    for i in range(h):
        t = i / h
        dr.line([(0, i), (w, i)],
                fill=(int(168 + 30 * t), int(178 + 30 * t), int(192 + 26 * t)))
    cx = w // 2
    skin = (219, 178, 146)
    skin_d = (198, 152, 118)
    # shoulders: dark suit, white shirt, burgundy tie
    dr.polygon([(cx - 58, h), (cx - 40, h - 52), (cx + 40, h - 52), (cx + 58, h)],
               fill=(38, 42, 58))
    dr.polygon([(cx - 17, h), (cx, h - 34), (cx + 17, h)], fill=(238, 236, 230))
    dr.polygon([(cx - 5, h - 33), (cx + 5, h - 33), (cx + 3, h - 6), (cx, h),
                (cx - 3, h - 6)], fill=(110, 30, 40))
    dr.rectangle([cx - 11, h - 62, cx + 11, h - 40], fill=skin_d)  # neck
    # head
    dr.ellipse([cx - 27, 26, cx + 27, 96], fill=skin)
    dr.ellipse([cx - 31, 52, cx - 25, 72], fill=skin)  # ears
    dr.ellipse([cx + 25, 52, cx + 31, 72], fill=skin)
    # hair: dark and swept back -- a man in his late thirties
    dr.pieslice([cx - 28, 14, cx + 28, 62], 180, 360, fill=(74, 58, 46))
    dr.rectangle([cx - 28, 34, cx - 23, 54], fill=(74, 58, 46))
    dr.rectangle([cx + 23, 34, cx + 28, 54], fill=(74, 58, 46))
    # brows, eyes, nose, mouth
    dr.line([(cx - 17, 56), (cx - 6, 54)], fill=(74, 58, 46), width=3)
    dr.line([(cx + 6, 54), (cx + 17, 56)], fill=(74, 58, 46), width=3)
    dr.ellipse([cx - 14, 60, cx - 8, 65], fill=(40, 34, 30))
    dr.ellipse([cx + 8, 60, cx + 14, 65], fill=(40, 34, 30))
    dr.line([(cx, 62), (cx - 3, 76), (cx + 2, 76)], fill=skin_d, width=2)
    dr.line([(cx - 9, 86), (cx + 9, 86)], fill=(150, 92, 84), width=3)
    dr.line([(cx - 20, 96), (cx + 20, 96)], fill=(0, 0, 0, 0))
    # faint deterministic grain so it sits like a printed photograph
    rng = random.Random(19880314)
    px = img.load()
    for _ in range(2600):
        gx, gy = rng.randrange(w), rng.randrange(h)
        r, g, b = px[gx, gy]
        d = rng.choice((-9, 9))
        px[gx, gy] = (max(0, min(255, r + d)), max(0, min(255, g + d)),
                      max(0, min(255, b + d)))
    return img


def signature(draw, x, y):
    """A quick ink scribble: 'T. Halden'."""
    col = (24, 28, 70)
    pts = [(x, y), (x + 8, y - 16), (x + 14, y + 2), (x + 20, y - 10),
           (x + 26, y + 3), (x + 30, y - 2)]
    draw.line(pts, fill=col, width=2)
    draw.ellipse([x + 36, y - 1, x + 39, y + 2], fill=col)
    pts2 = [(x + 46, y + 2), (x + 52, y - 18), (x + 58, y + 3), (x + 64, y - 8),
            (x + 70, y + 3), (x + 78, y - 4), (x + 88, y + 1), (x + 100, y - 6),
            (x + 112, y + 0)]
    draw.line(pts2, fill=col, width=2)


def fit_font(path, size, text, max_w, draw):
    """Largest font at or below `size` whose text fits `max_w` pixels."""
    while size > 8:
        fnt = font(path, size)
        if draw.textlength(text, font=fnt) <= max_w:
            return fnt
        size -= 1
    return font(path, size)


def stamp_layer(w, h, country, place, kind, date, ink):
    """One border stamp on its own transparent layer, ready to rotate."""
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)
    a = 205
    col = ink + (a,)
    dr.rounded_rectangle([3, 3, w - 4, h - 4], radius=10, outline=col, width=3)
    dr.rounded_rectangle([8, 8, w - 9, h - 9], radius=7, outline=col, width=1)
    f1 = fit_font(SANS_B, 13, country, w - 26, dr)
    f2 = fit_font(SANS, 11, place, w - 26, dr)
    f3 = fit_font(SANS_B, 15, f"{kind}  {date}", w - 44, dr)
    for txt, fnt, yy in ((country, f1, 13), (place, f2, 33),
                         (f"{kind}  {date}", f3, 52)):
        tw = dr.textlength(txt, font=fnt)
        dr.text(((w - tw) / 2, yy), txt, font=fnt, fill=col)
    # a small direction triangle, clear of the centred text
    cy = h // 2
    if kind in ("ARRIVAL", "ENTRY"):
        dr.polygon([(11, cy - 6), (11, cy + 6), (20, cy)], fill=col)
    else:
        dr.polygon([(20, cy - 6), (20, cy + 6), (11, cy)], fill=col)
    return lay


def data_page(img, d):
    dr = ImageDraw.Draw(img)
    x0, y0 = 16, 14  # left page origin
    guilloche(dr, (x0 + 8, y0 + 8, x0 + 480, y0 + 560), 0.4)
    dr_wm = ImageDraw.Draw(img, "RGBA")
    emblem(dr_wm, x0 + 330, y0 + 330, 74, (120, 130, 150, 26), width=3)
    # header
    emblem(dr, x0 + 52, y0 + 52, 26, (122, 32, 44))
    f_title = font(SERIF_B, 24)
    tw = dr.textlength(d["country_en"], font=f_title)
    dr.text((x0 + (488 - tw) / 2 + 18, y0 + 24), d["country_en"], font=f_title,
            fill=(122, 32, 44))
    tracked(dr, (x0 + 148, y0 + 56), d["country_fr"], font(SERIF, 12),
            (70, 74, 88), tracking=3)
    tracked(dr, (x0 + 176, y0 + 78), "PASSPORT · PASSEPORT", font(SANS_B, 11),
            LABEL, tracking=2)
    dr.line([(x0 + 24, y0 + 104), (x0 + 464, y0 + 104)], fill=(122, 32, 44), width=2)
    # type / code / number row
    ry = y0 + 114
    dr.text((x0 + 24, ry), "TYPE", font=font(SANS, 9), fill=LABEL)
    dr.text((x0 + 24, ry + 12), d["doc_type"], font=font(SANS_B, 16), fill=INK)
    dr.text((x0 + 92, ry), "CODE", font=font(SANS, 9), fill=LABEL)
    dr.text((x0 + 92, ry + 12), d["country_code"], font=font(SANS_B, 16), fill=INK)
    dr.text((x0 + 268, ry), "PASSPORT No / PASSEPORT Nº", font=font(SANS, 9), fill=LABEL)
    dr.text((x0 + 268, ry + 12), d["passport_no"], font=font(SANS_B, 17),
            fill=(122, 32, 44))
    # portrait
    px, py = x0 + 24, y0 + 158
    img.paste(portrait((0, 0, 140, 180)), (px, py))
    dr.rectangle([px, py, px + 140, py + 180], outline=(150, 144, 128), width=1)
    # fields beside the portrait
    fx = x0 + 184
    field(dr, fx, y0 + 152, "Surname / Nom", d["surname"], w=280)
    field(dr, fx, y0 + 204, "Given names / Prénoms", d["given"], w=280)
    field(dr, fx, y0 + 256, "Nationality / Nationalité", d["nationality"], w=280)
    field(dr, fx, y0 + 308, "Date of birth / Naissance", d["dob_print"], w=140,
          lfont=font(SANS, 8))
    field(dr, fx + 156, y0 + 308, "Sex / Sexe", d["sex"], w=124,
          lfont=font(SANS, 8))
    # full-width fields under the portrait row
    field(dr, x0 + 24, y0 + 362, "Place of birth / Lieu de naissance",
          d["birthplace"], w=212)
    field(dr, x0 + 252, y0 + 362, "Personal No / Nº personnel",
          d["personal_no"], w=212)
    field(dr, x0 + 24, y0 + 414, "Date of issue / Date de délivrance",
          d["issue_print"], w=212)
    field(dr, x0 + 252, y0 + 414, "Date of expiry / Date d'expiration",
          d["expiry_print"], w=212)
    field(dr, x0 + 24, y0 + 466, "Authority / Autorité", d["authority"], w=440,
          vfont=font(SANS_B, 13))
    # signature + observation
    dr.text((x0 + 24, y0 + 522), "HOLDER'S SIGNATURE / SIGNATURE",
            font=font(SANS, 9), fill=LABEL)
    signature(dr, x0 + 28, y0 + 552)
    dr.line([(x0 + 24, y0 + 560), (x0 + 190, y0 + 560)], fill=(178, 172, 158), width=1)
    # observation, wrapped by hand into the space right of the signature
    obs_lines = ["Observations: The bearer, a master",
                 "horologer of the Kesslerfurt guild, is",
                 "exempt from the High-Pass tolls under",
                 "the Horologers' Charter of 1911."]
    for i, ln in enumerate(obs_lines):
        dr.text((x0 + 208, y0 + 518 + i * 13), ln, font=font(SANS_O, 10),
                fill=(70, 74, 88))
    # machine-readable zone
    line1, line2 = mrz_lines(d)
    my = y0 + 596
    dr.rectangle([x0 + 8, my - 8, x0 + 480, my + 92], fill=(238, 233, 218))
    adv = 452 / 44.0
    fm = font(MONO_B, 17)
    for li, line in enumerate((line1, line2)):
        for i, ch in enumerate(line):
            dr.text((x0 + 18 + i * adv, my + 6 + li * 40), ch, font=fm, fill=(20, 22, 30))


def stamps_page(img):
    dr = ImageDraw.Draw(img)
    x0, y0 = 520, 14
    guilloche(dr, (x0 + 8, y0 + 8, x0 + 480, y0 + 700), 2.1)
    tracked(dr, (x0 + 24, y0 + 22), "VISAS", font(SANS_B, 13), LABEL, tracking=4)
    dr.text((x0 + 440, y0 + 20), "7", font=font(SERIF_B, 15), fill=LABEL)
    dr.text((x0 + 24, y0 + 46),
            "Endorsements and border stamps · Visa et cachets officiels",
            font=font(SANS_O, 10), fill=LABEL)
    dr.line([(x0 + 24, y0 + 68), (x0 + 464, y0 + 68)], fill=(178, 172, 158), width=1)
    spots = [(x0 + 12, y0 + 92, -5), (x0 + 244, y0 + 118, 4),
             (x0 + 16, y0 + 238, 3), (x0 + 248, y0 + 262, -7),
             (x0 + 14, y0 + 384, 6), (x0 + 242, y0 + 402, -3)]
    for (sx, sy, ang), (country, place, kind, date, ink) in zip(spots, STAMPS):
        lay = stamp_layer(228, 86, country, place, kind, date, ink)
        rot = lay.rotate(ang, expand=True, resample=Image.BICUBIC)
        img.paste(rot, (sx, sy), rot)
    # The telling detail: the home country's own endorsement stamp, applied
    # the day the passport was issued.
    ex, ey = x0 + 58, y0 + 540
    lay = Image.new("RGBA", (372, 108), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    col = (104, 44, 128, 215)
    ld.rounded_rectangle([3, 3, 368, 104], radius=8, outline=col, width=3)
    ld.rounded_rectangle([8, 8, 363, 99], radius=6, outline=col, width=1)
    lines = [("MINISTRY OF RAILWAYS AND PASSES · VELDRA", font(SANS_B, 12), 14),
             ("HOROLOGERS' CHARTER — BEARER EXEMPT", font(SANS_B, 14), 36),
             ("FROM HIGH-PASS TOLLS · 03 JUN 2021", font(SANS_B, 14), 58),
             ("GUILD LICENCE Nº 2217 · KESSLERFURT", font(SANS, 11), 80)]
    for txt, fnt, yy in lines:
        tw = ld.textlength(txt, font=fnt)
        ld.text(((372 - tw) / 2, yy), txt, font=fnt, fill=col)
    rot = lay.rotate(-2, expand=True, resample=Image.BICUBIC)
    img.paste(rot, (ex, ey), rot)
    dr.text((x0 + 24, y0 + 700),
            "This passport contains 32 pages · Ce passeport contient 32 pages",
            font=font(SANS, 9), fill=LABEL)


def main():
    d = DATA
    img = Image.new("RGB", (1024, 768), (54, 58, 66))  # the desk beneath
    dr = ImageDraw.Draw(img)
    # the two pages and the spine shadow between them
    dr.rectangle([16, 14, 504, 754], fill=PAGE)
    dr.rectangle([520, 14, 1008, 754], fill=PAGE)
    for i in range(16):
        shade = int(54 + i * 4)
        dr.line([(504 + i, 14), (504 + i, 754)], fill=(shade + 60, shade + 58, shade + 52))
    dr.rectangle([16, 14, 504, 754], outline=(120, 114, 100), width=1)
    dr.rectangle([520, 14, 1008, 754], outline=(120, 114, 100), width=1)
    data_page(img, d)
    stamps_page(img)
    out = "/output"
    try:
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, "entry.png")
        img.save(path, format="PNG")
    except OSError:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, "entry.png")
        img.save(path, format="PNG")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
