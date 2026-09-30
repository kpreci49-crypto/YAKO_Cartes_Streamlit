"""YAKO business cards using the user's original artwork and contact icons."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import quote


from PIL import Image
from reportlab.lib.colors import CMYKColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
FONTS = ROOT / "fonts"
MM = 72 / 25.4
WIDTH_MM, HEIGHT_MM = 85.0, 55.0

# DeviceCMYK values calibrated to render the requested sRGB references
# (#076633, #F9B233) in the PDF preview. A printer ICC profile may differ.
GREEN_CMYK = CMYKColor(.952, 0, .91, .45)
GOLD_CMYK = CMYKColor(0, .295, .805, .005)
WHITE_CMYK = CMYKColor(0, 0, 0, 0)
LINE_CMYK = CMYKColor(.30, 0, .33, .24)

FONT_REG = "Poppins"
FONT_BOLD = "PoppinsBold"
FONT_ITALIC = "PoppinsItalic"


@dataclass(frozen=True)
class Card:
    name: str
    role: str
    phone: str
    mobile: str
    email: str
    address: str = "Immeuble pacifique, Rue du commerce"
    company_email: str = "infos@yakoafricassur.com"
    qr_png: bytes | None = None
    kind: str = "Employé"
    def __post_init__(self) -> None:
        object.__setattr__(self, "role", self.role.strip().upper())
    qr_png: bytes | None = None
    kind: str = "Employé"

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", self.role.strip().upper())


def _register_fonts() -> None:
    if FONT_REG not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_REG, str(FONTS / "Poppins-Regular.ttf")))
    if FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONTS / "Poppins-Bold.ttf")))
    if FONT_ITALIC not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_ITALIC, str(FONTS / "Poppins-Italic.ttf")))


def _mm(value: float) -> float:
    return value * MM


def _top(value: float) -> float:
    return _mm(HEIGHT_MM - value)


def _background(pdf: Canvas) -> None:
    pdf.setFillColor(GREEN_CMYK)
    pdf.rect(0, 0, _mm(WIDTH_MM), _mm(HEIGHT_MM), stroke=0, fill=1)


def _fit_text(pdf: Canvas, value: str, x: float, baseline: float,
              max_width: float, font: str, preferred_pt: float,
              min_pt: float, color=WHITE_CMYK, centered=False) -> None:
    value = value.strip()
    size = preferred_pt
    while size >= min_pt and pdfmetrics.stringWidth(value, font, size) > _mm(max_width):
        size -= .15
    if size < min_pt:
        raise ValueError(f"Texte trop long pour la carte : {value[:65]}")
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    if centered:
        pdf.drawCentredString(_mm(x), _top(baseline), value)
    else:
        pdf.drawString(_mm(x), _top(baseline), value)


def _vcard(card: Card) -> str:
    def escaped(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{escaped(card.name)}",
             "ORG:YAKO AFRICA ASSURANCES VIE", f"TITLE:{escaped(card.role)}",
             f"TEL;TYPE=WORK:{escaped(card.phone)}"]
    if card.mobile and card.mobile != card.phone:
        lines.append(f"TEL;TYPE=CELL:{escaped(card.mobile)}")
    lines += [f"EMAIL:{escaped(card.email)}", f"ADR;TYPE=WORK:;;{escaped(card.address)};;;;", "END:VCARD"]
    return "\r\n".join(lines)


def _qr_image(card: Card) -> ImageReader:
    if card.qr_png:
        im = Image.open(BytesIO(card.qr_png)).convert("RGB")
        return ImageReader(im)
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("Installe les dépendances avec pip install -r requirements.txt") from exc
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                         box_size=14, border=3)
    url = f"https://e-card.yakoafricassur.com/qrcode/{quote(card.email.strip(), safe='')}"
    code.add_data(url)
    code.make(fit=True)
    return ImageReader(code.make_image(fill_color="black", back_color="white").convert("RGB"))


def _source_icons() -> list[ImageReader]:
    """Phone, mobile, mail, place and mail from the original 512 px PNGs."""
    names = ("icon_tel.png", "icon_mobile.png", "icon_mail.png",
             "icon_lieu.png", "icon_mail.png")
    return [ImageReader(str(ASSETS / name)) for name in names]


def _draw_arm(pdf: Canvas) -> None:
    # Align the original high-resolution art to the user's lower-right crop.
    # Its 211 x 78 reference window corresponds to the card's 37.6 x 15.5 mm.
    window_x, window_top, window_w, window_h = 47.4, 39.5, 37.6, 15.5
    scale, offset_x, offset_y = .25, -68, -43
    art_x = window_x + offset_x / 211 * window_w
    art_top = window_top + offset_y / 78 * window_h
    art_w = 1376 * scale / 211 * window_w
    art_h = 954 * scale / 78 * window_h
    pdf.saveState()
    clip = pdf.beginPath()
    clip.rect(_mm(window_x), _top(window_top + window_h),
              _mm(window_w), _mm(window_h))
    pdf.clipPath(clip, stroke=0, fill=0)
    pdf.drawImage(ImageReader(str(ASSETS / "bras_design_hd.png")),
                  _mm(art_x), _top(art_top + art_h),
                  width=_mm(art_w), height=_mm(art_h), mask="auto")
    pdf.restoreState()


def _front(pdf: Canvas, card: Card, icons: list[ImageReader]) -> None:
    _background(pdf)
    _draw_arm(pdf)

    commercial = card.kind == "Commercial"
    icon_x = 12.5 if commercial else 25.15
    text_x = 17.85 if commercial else 30.5

    if not commercial:
        pdf.drawImage(
            _qr_image(card), _mm(2.7), _top(36.8),
            width=_mm(16.5), height=_mm(16.5),
        )
        pdf.setStrokeColor(LINE_CMYK)
        pdf.setLineWidth(_mm(.08))
        pdf.setDash(_mm(.25), _mm(.22))
        pdf.line(_mm(21.35), _top(16.6), _mm(21.35), _top(40.9))
        pdf.setDash()

    _fit_text(
        pdf, card.name, 42.5, 6.7, 70, FONT_BOLD, 8.4, 6.8,
        color=GOLD_CMYK, centered=True,
    )
    _fit_text(
        pdf, card.role.upper(), 42.5, 10.95, 74,
        FONT_ITALIC, 5.65, 4.8, centered=True,
    )

    fields = [
        (card.phone, icons[0]),
        (card.mobile or card.phone, icons[1]),
        (card.email, icons[2]),
        (card.address, icons[3]),
        (card.company_email, icons[4]),
    ]

    row = 0
    for value, icon in fields:
        if not value or not value.strip():
            continue

        pdf.drawImage(
            icon,
            _mm(icon_x + .4),
            _top(19.55 + 5.05 * row),
            width=_mm(2.9),
            height=_mm(2.9),
            mask="auto",
        )
        _fit_text(
            pdf, value, text_x, 18.9 + 5.05 * row,
            66.0 if commercial else 53.5,
            FONT_BOLD, 5.18, 4.1,
        )
        row += 1

    pdf.showPage()

def _back(pdf: Canvas) -> None:
    _background(pdf)
    # The user's exact logo drawing, with its black canvas made transparent.
    pdf.saveState()
    clip = pdf.beginPath()
    clip.rect(_mm(27.2), _top(33.3), _mm(31.6), _mm(17.5))
    pdf.clipPath(clip, stroke=0, fill=0)
    pdf.drawImage(ImageReader(str(ASSETS / "logo_yako_blanc_transparent.png")),
                  _mm(7.24), _mm(5.75), width=_mm(70.46), height=_mm(49.69),
                  mask="auto")
    pdf.restoreState()

    first = "YAKO AFRICA, l’"
    highlighted = "A"
    last = "ssureur qui protège votre bonheur"
    font, size = FONT_BOLD, 6.15
    total = sum(pdfmetrics.stringWidth(s, font, size) for s in (first, highlighted, last))
    x = (_mm(WIDTH_MM) - total) / 2
    y = _top(47.2)
    for fragment, color in ((first, WHITE_CMYK), (highlighted, GOLD_CMYK), (last, WHITE_CMYK)):
        pdf.setFillColor(color)
        pdf.setFont(font, size)
        pdf.drawString(x, y, fragment)
        x += pdfmetrics.stringWidth(fragment, font, size)
    pdf.showPage()


def create_pdf(cards: list[Card]) -> bytes:
    if not cards:
        raise ValueError("Ajoute au moins une personne.")
    _register_fonts()
    stream = BytesIO()
    pdf = Canvas(stream, pagesize=(_mm(WIDTH_MM), _mm(HEIGHT_MM)), pageCompression=1)
    icons = _source_icons()
    for card in cards:
        if card.kind not in ("Employé", "Commercial"):
            raise ValueError(f"Type de carte inconnu : {card.kind}")
        if not all((card.name.strip(), card.role.strip(), card.phone.strip(), card.email.strip())):
            raise ValueError("Chaque carte doit avoir un nom, une fonction, un téléphone et un e-mail.")
        _front(pdf, card, icons)
        _back(pdf)
    pdf.setTitle("Cartes YAKO AFRICA - 85 x 55 mm - CMJN")
    pdf.save()
    return stream.getvalue()
