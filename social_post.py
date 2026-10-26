"""Deterministic square graphics for rescheduled waste collections.

The event data comes exclusively from ``data/svoz_exceptions.json``. This
renderer is independent of the OpenGraph cards in ``social_preview.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from svoz_exceptions import LOCATION_GROUPS, SvozException, load_svoz_exceptions


ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "resources" / "fonts"
LOGO_PATH = ROOT / "resources" / "branding" / "litovle_logo_current.png"
POST_SIZE = (1080, 1080)
SIDE_MARGIN = 70
SAFE_BOTTOM = 1040
INK = "#17191d"
BLUE = "#0f46ab"  # Litovle.cz --brand-blue
MUTED = "#777f87"
DIVIDER = "#c7e0f3"
MONTHS_GENITIVE = (
    "ledna", "února", "března", "dubna", "května", "června",
    "července", "srpna", "září", "října", "listopadu", "prosince",
)
WASTE_GENITIVE = {
    "PAPIR": "papíru",
    "PLAST": "plastu",
    "SMES": "směsného odpadu",
    "BIO": "bioodpadu",
}


@dataclass(frozen=True)
class PostElement:
    kind: str
    bounds: tuple[int, int, int, int]
    font_size: int | None = None


@dataclass(frozen=True)
class RenderedPost:
    image: Image.Image
    elements: tuple[PostElement, ...]


def format_czech_day(value: date) -> str:
    return f"{value.day}. {MONTHS_GENITIVE[value.month - 1]}"


def waste_name_genitive(waste_type: str) -> str:
    try:
        return WASTE_GENITIVE[waste_type]
    except KeyError as error:
        raise ValueError(f"Unsupported waste type for social post: {waste_type}") from error


def find_exception(event_id: str, exceptions: tuple[SvozException, ...] | None = None) -> SvozException:
    candidates = exceptions if exceptions is not None else load_svoz_exceptions()
    for exception in candidates:
        if exception.id == event_id:
            return exception
    raise ValueError(f"Waste collection exception not found: {event_id}")


def affected_location_names(exception: SvozException) -> tuple[str, ...]:
    """Read the effective locations from the same groups used by exceptions."""
    if exception.affected_location_group == "all_streets_litovel":
        return ()
    if exception.affected_location_group:
        return LOCATION_GROUPS[exception.affected_location_group]
    return exception.affected_locations


def render_post(
    exception: SvozException,
    *,
    font_dir: Path = FONT_DIR,
    logo_path: Path = LOGO_PATH,
) -> RenderedPost:
    if exception.action != "reschedule":
        raise ValueError(
            f"Social post supports action 'reschedule'; {exception.id} has {exception.action!r}"
        )
    if exception.original_date is None or exception.new_date is None:
        raise ValueError(f"Reschedule {exception.id} needs original_date and new_date")

    waste_name = waste_name_genitive(exception.waste_type)
    fonts = _load_fonts(font_dir)
    logo = _load_logo(logo_path)
    image = Image.new("RGB", POST_SIZE, "#ffffff")
    draw = ImageDraw.Draw(image)
    elements: list[PostElement] = []

    _text(draw, elements, "LITOVEL", (SIDE_MARGIN, 70), fonts["regular"](31), MUTED)
    locations = affected_location_names(exception)
    location_rows = _draw_locations(draw, elements, locations, fonts["semibold"]) if locations else 0
    vertical_offset = {0: -28, 1: -15, 2: 0}[location_rows]

    # Fit one shared font size to every main line so dates and status have the
    # same visual weight while even the longest waste label stays in bounds.
    headline = f"Svoz {waste_name}"
    if draw.textlength(headline, font=fonts["black"](132)) > POST_SIZE[0] - 2 * SIDE_MARGIN:
        first_line, second_line = headline.rsplit(" ", 1)
        lines = (
            (first_line, 198, INK),
            (second_line, 305, INK),
            (format_czech_day(exception.original_date), 425, INK),
            ("přesunut na", 540, BLUE),
            (format_czech_day(exception.new_date), 655, BLUE),
        )
        maximum_size = 115
    else:
        lines = (
            (headline, 198, INK),
            (format_czech_day(exception.original_date), 340, INK),
            ("přesunut na", 500, BLUE),
            (format_czech_day(exception.new_date), 640, BLUE),
        )
        maximum_size = 132
    main_size = min(
        _fit_font(draw, text, fonts["black"], maximum_size, POST_SIZE[0] - 2 * SIDE_MARGIN).size
        for text, _, _ in lines
    )
    main_font = fonts["black"](main_size)
    for text, top, color in lines:
        _text(draw, elements, text, (SIDE_MARGIN, top + vertical_offset), main_font, color, kind="main_text")

    divider_y = 803 + vertical_offset
    draw.line((SIDE_MARGIN, divider_y, POST_SIZE[0] - SIDE_MARGIN, divider_y), fill=DIVIDER, width=2)
    elements.append(PostElement("divider", (SIDE_MARGIN, divider_y, POST_SIZE[0] - SIDE_MARGIN, divider_y + 2)))

    _text(draw, elements, "Aktuální informace najdete", (SIDE_MARGIN, 828 + vertical_offset), fonts["regular"](33), INK)
    _rich_text(
        draw,
        elements,
        (SIDE_MARGIN, 873 + vertical_offset),
        (
            ("v aplikaci ", "regular", INK),
            ("Svoz odpadu Litovel", "semibold", INK),
            (" nebo na ", "regular", INK),
            ("svoz.litovle.cz", "semibold", BLUE),
        ),
        fonts,
        30,
    )

    # The original PNG is pasted as supplied, after proportional scaling.
    logo.thumbnail((470, 100), Image.Resampling.LANCZOS)
    logo_x = SIDE_MARGIN
    logo_y = SAFE_BOTTOM - logo.height
    image.paste(logo, (logo_x, logo_y), logo)
    elements.append(PostElement("logo", (logo_x, logo_y, logo_x + logo.width, logo_y + logo.height)))

    for element in elements:
        left, top, right, bottom = element.bounds
        if not (SIDE_MARGIN <= left < right <= POST_SIZE[0] - SIDE_MARGIN and
                55 <= top < bottom <= SAFE_BOTTOM):
            raise ValueError(f"Social post element outside safe bounds: {element}")
    return RenderedPost(image, tuple(elements))


def save_post(rendered: RenderedPost, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered.image.save(output_path, format="PNG", optimize=True)


def _load_fonts(font_dir: Path):
    paths = {
        "regular": font_dir / "Inter-Regular.ttf",
        "semibold": font_dir / "Inter-SemiBold.ttf",
        "black": font_dir / "Inter-Black.ttf",
    }
    for weight, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required Inter {weight} font is missing: {path}")
    def family(weight: str):
        def at_size(size: int) -> ImageFont.FreeTypeFont:
            try:
                return ImageFont.truetype(str(paths[weight]), size)
            except OSError as error:
                raise ValueError(f"Cannot read Inter font: {paths[weight]}") from error
        return at_size
    return {weight: family(weight) for weight in paths}


def _load_logo(path: Path) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Required Litovle.cz logo PNG is missing: {path}")
    try:
        with Image.open(path) as source:
            if source.format != "PNG":
                raise ValueError(f"Litovle.cz logo must be a PNG: {path}")
            return source.convert("RGBA")
    except OSError as error:
        raise ValueError(f"Cannot read Litovle.cz logo PNG: {path}") from error


def _fit_font(draw: ImageDraw.ImageDraw, text: str, font_at_size, maximum: int, width: int, *, minimum: int = 30):
    for size in range(maximum, minimum - 1, -1):
        font = font_at_size(size)
        if draw.textlength(text, font=font) <= width:
            return font
    raise ValueError(f"Text cannot fit inside social post: {text!r}")


def _text(draw, elements, value, xy, font, color, *, kind="text") -> None:
    bounds = draw.textbbox(xy, value, font=font, anchor="lt")
    draw.text(xy, value, font=font, fill=color, anchor="lt")
    elements.append(PostElement(kind, bounds, font.size))


def _rich_text(draw, elements, xy, segments, fonts, size) -> None:
    x, y = xy
    for value, weight, color in segments:
        font = fonts[weight](size)
        _text(draw, elements, value, (round(x), y), font, color)
        x += draw.textlength(value, font=font)


def _draw_locations(draw, elements, locations, font_at_size) -> int:
    width = POST_SIZE[0] - 2 * SIDE_MARGIN
    for size in range(22, 15, -1):
        font = font_at_size(size)
        lines = _wrap_locations(draw, locations, font, width)
        if len(lines) <= 2:
            break
    else:
        # Very large route groups cannot be listed legibly in the header.
        # State their scope and count without pretending the change is citywide.
        lines = [f"{len(locations)} VYBRANÝCH LOKALIT LITOVLE"]
        font = font_at_size(22)
    for index, line in enumerate(lines):
        _text(draw, elements, line, (SIDE_MARGIN, 111 + index * 27), font, MUTED)
    return len(lines)


def _wrap_locations(draw, locations, font, width) -> list[str]:
    lines: list[str] = []
    current = ""
    for location in locations:
        name = location.upper()
        if draw.textlength(name, font=font) > width:
            raise ValueError(f"Affected location cannot fit on social post: {location!r}")
        candidate = name if not current else f"{current} · {name}"
        if current and draw.textlength(candidate, font=font) > width:
            lines.append(current)
            current = name
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines
