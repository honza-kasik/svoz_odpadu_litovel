from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from meta_builder import config
from utils import slugify


CARD_WIDTH = 1200
CARD_HEIGHT = 630
CARD_DIR = Path("resources/social")
BASE_IMAGE_URL = f"{config.base_url}/resources/social"
PRAGUE_TZ = ZoneInfo("Europe/Prague")

WASTE_COLORS = {
    "bio": ("#7c3f00", "#fff7ed"),
    "generic": ("#111827", "#f8fafc"),
    "plastics": ("#facc15", "#111827"),
    "paper": ("#2563eb", "#eff6ff"),
}


@dataclass(frozen=True)
class SocialImage:
    url: str
    alt: str


def build_social_images(generator, streets: list[str], today: date | None = None) -> dict[str, SocialImage]:
    """Generate social preview images and return metadata keyed by page."""

    reference_date = today or datetime.now(PRAGUE_TZ).date()
    _reset_card_dir()

    images = {
        "index": _save_card(
            _draw_home_card(reference_date),
            "home",
            f"Svoz odpadu Litovel {config.year} - kalendář podle ulic",
        )
    }

    for street in streets:
        slug = slugify(street)
        events = _upcoming_events(generator.get_events_for_street(street), reference_date, 3)
        images[slug] = _save_card(
            _draw_street_card(street, events, reference_date),
            slug,
            f"Svoz odpadu {street}, Litovel - nejbližší termíny",
        )

    return images


def _reset_card_dir() -> None:
    CARD_DIR.mkdir(parents=True, exist_ok=True)
    for path in CARD_DIR.glob("*.png"):
        path.unlink()


def _upcoming_events(events, reference_date: date, limit: int):
    return [event for event in events if event.date.date() >= reference_date][:limit]


def _save_card(image: Image.Image, prefix: str, alt: str) -> SocialImage:
    with NamedTemporaryFile(dir=CARD_DIR, suffix=".png", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        image.save(temp_path, "PNG", optimize=True)
        digest = sha256(temp_path.read_bytes()).hexdigest()[:12]
        filename = f"{prefix}-{digest}.png"
        final_path = CARD_DIR / filename
        temp_path.replace(final_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    return SocialImage(url=f"{BASE_IMAGE_URL}/{filename}", alt=alt)


def _draw_home_card(reference_date: date) -> Image.Image:
    image, draw = _base_card()
    fonts = _fonts()

    _draw_brand(draw, fonts)
    _draw_text(draw, "Svoz odpadu Litovel", (72, 118), fonts["title"], "#111827", max_width=700)
    _draw_text(
        draw,
        f"Aktuální kalendář svozu pro rok {config.year}",
        (76, 210),
        fonts["subtitle"],
        "#475569",
        max_width=660,
    )
    _draw_text(
        draw,
        "Zadejte ulici a zjistěte nejbližší svozy odpadu.",
        (76, 286),
        fonts["body"],
        "#1f2937",
        max_width=650,
    )

    _draw_waste_badges(draw, fonts, 76, 386)
    _draw_footer(draw, fonts, f"Aktualizováno {format_czech_date(reference_date)}")
    _draw_calendar_preview(draw, fonts)

    return image


def _draw_street_card(street: str, events, reference_date: date) -> Image.Image:
    image, draw = _base_card()
    fonts = _fonts()

    _draw_brand(draw, fonts)
    _draw_text(draw, "Nejbližší svozy", (76, 132), fonts["eyebrow"], "#2563eb", max_width=600)
    _draw_text(draw, street, (72, 174), fonts["title"], "#111827", max_width=690)
    _draw_text(draw, f"Litovel - {config.year}", (76, 260), fonts["subtitle"], "#475569", max_width=650)

    if events:
        y = 330
        for event in events:
            _draw_event_row(draw, event, 76, y, fonts)
            y += 72
    else:
        _draw_text(
            draw,
            f"Pro tuto lokaci nejsou po {format_czech_date(reference_date)} v datech další svozy.",
            (76, 340),
            fonts["body"],
            "#475569",
            max_width=660,
        )

    _draw_footer(draw, fonts, f"Aktualizováno {format_czech_date(reference_date)}")
    _draw_street_visual(draw, events)

    return image


def _base_card() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), "#f1f5f9")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((42, 42, CARD_WIDTH - 42, CARD_HEIGHT - 42), radius=28, fill="#ffffff")
    draw.rectangle((CARD_WIDTH - 365, 42, CARD_WIDTH - 42, CARD_HEIGHT - 42), fill="#eef2ff")
    draw.rounded_rectangle((CARD_WIDTH - 365, 42, CARD_WIDTH - 42, CARD_HEIGHT - 42), radius=28, outline="#eef2ff", width=1)
    return image, draw


def _fonts() -> dict[str, ImageFont.FreeTypeFont]:
    return {
        "brand": _font(28),
        "eyebrow": _font(32),
        "title": _font(58),
        "subtitle": _font(30),
        "body": _font(30),
        "small": _font(22),
        "badge": _font(24),
        "event": _font(28),
        "event_small": _font(22),
    }


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("resources/Caladea-Regular.ttf"),
        Path("/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def _draw_brand(draw: ImageDraw.ImageDraw, fonts: dict[str, ImageFont.FreeTypeFont]) -> None:
    favicon = _load_favicon()
    draw._image.paste(favicon, (76, 72), favicon)
    draw.text((138, 77), config.base_domain, font=fonts["brand"], fill="#1f2937")


def _load_favicon() -> Image.Image:
    source = Image.open("resources/favicon_source.png").convert("RGBA")
    return source.resize((48, 48), Image.Resampling.LANCZOS)


def _draw_waste_badges(draw, fonts, x: int, y: int) -> None:
    labels = [
        ("Směsný", "generic"),
        ("Plast", "plastics"),
        ("Papír", "paper"),
        ("Bio", "bio"),
    ]
    current_x = x
    for label, key in labels:
        bg, fg = WASTE_COLORS[key]
        width = int(draw.textlength(label, font=fonts["badge"])) + 34
        draw.rounded_rectangle((current_x, y, current_x + width, y + 44), radius=8, fill=bg)
        draw.text((current_x + 17, y + 9), label, font=fonts["badge"], fill=fg)
        current_x += width + 14


def _draw_calendar_preview(draw, fonts) -> None:
    x0, y0 = 905, 136
    cell = 54
    gap = 8
    for row in range(5):
        for col in range(4):
            x = x0 + col * (cell + gap)
            y = y0 + row * (cell + gap)
            fill = "#ffffff" if (row + col) % 3 else "#dbeafe"
            draw.rounded_rectangle((x, y, x + cell, y + cell), radius=10, fill=fill)
    draw.rounded_rectangle((x0 + 2 * (cell + gap), y0 + 2 * (cell + gap), x0 + 3 * (cell + gap), y0 + 3 * (cell + gap)), radius=10, fill="#86cb7c")
    draw.text((900, 500), "Kalendář podle ulic", font=fonts["body"], fill="#1f2937")


def _draw_street_visual(draw, events) -> None:
    x0, y0 = 900, 148
    cell = 52
    gap = 10
    highlighted = {index: event.waste_type.key for index, event in enumerate(events[:3])}

    for row in range(5):
        for col in range(4):
            index = row * 4 + col
            x = x0 + col * (cell + gap)
            y = y0 + row * (cell + gap)
            if index in highlighted:
                bg, _ = WASTE_COLORS[highlighted[index]]
                fill = bg
            else:
                fill = "#ffffff" if index % 3 else "#dbeafe"
            draw.rounded_rectangle((x, y, x + cell, y + cell), radius=10, fill=fill)

    draw.rounded_rectangle((898, 486, 1100, 498), radius=6, fill="#c7d2fe")
    draw.rounded_rectangle((898, 514, 1056, 526), radius=6, fill="#dbeafe")


def _draw_event_row(draw, event, x: int, y: int, fonts) -> None:
    key = event.waste_type.key
    bg, fg = WASTE_COLORS[key]
    draw.rounded_rectangle((x, y, 716, y + 54), radius=10, fill=bg)
    draw.text((x + 18, y + 13), event.waste_type.label, font=fonts["event"], fill=fg)
    draw.text((474, y + 13), format_czech_date(event.date.date()), font=fonts["event"], fill=fg)
    if event.is_override:
        draw.rounded_rectangle((598, y + 13, 700, y + 43), radius=7, fill="#f97316")
        draw.text((617, y + 16), "Změna", font=fonts["event_small"], fill="#ffffff")


def _draw_footer(draw, fonts, text: str) -> None:
    draw.text((76, 548), text, font=fonts["small"], fill="#64748b")


def _draw_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: str,
    max_width: int,
    line_spacing: int = 8,
) -> None:
    x, y = xy
    for line in _wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y += bbox[3] - bbox[1] + line_spacing


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def format_czech_date(value: date) -> str:
    return f"{value.day}. {value.month}. {value.year}"
