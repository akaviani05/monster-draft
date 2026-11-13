"""Shared print-and-cut login PDF layout; no account or database access."""
import io
from pathlib import Path

CREDENTIAL_DIR = Path(__file__).resolve().parents[1] / "output/pdf/team-credentials"

# A4 points: 30-point printer margins, shared cut lines, ten equal cards.
PAGE_WIDTH, PAGE_HEIGHT = 595.28, 841.89
CARD_MARGIN = 30
CARD_WIDTH = (PAGE_WIDTH - 2 * CARD_MARGIN) / 2
CARD_HEIGHT = (PAGE_HEIGHT - 2 * CARD_MARGIN) / 5


def render_login_cards(teams):
    """Print-and-cut credentials: five rows by two columns per portrait A4 page."""
    try:
        import cairo
    except ImportError as exc:
        raise RuntimeError("PDF export requires python3-cairo (sudo apt install python3-cairo)") from exc
    output = io.BytesIO()
    surface = cairo.PDFSurface(output, PAGE_WIDTH, PAGE_HEIGHT)
    surface.set_metadata(cairo.PDF_METADATA_TITLE, "Monster Draft Duel - team login cards")
    ctx = cairo.Context(surface)

    def text(value, x, y, size, mono=False, bold=False):
        ctx.select_font_face("DejaVu Sans Mono" if mono else "DejaVu Sans",
                             cairo.FONT_SLANT_NORMAL,
                             cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(size)
        width = ctx.text_extents(value).width
        if width > CARD_WIDTH - 32:
            ctx.set_font_size(size * (CARD_WIDTH - 32) / width)
        ctx.move_to(x, y)
        ctx.show_text(value)

    for start in range(0, len(teams), 10):
        # One shared boundary per cut, including blank cells on a partial sheet.
        ctx.set_source_rgb(.65, .65, .65)
        ctx.set_line_width(.5)
        ctx.set_dash([3, 3])
        for column in range(3):
            x = CARD_MARGIN + column * CARD_WIDTH
            ctx.move_to(x, CARD_MARGIN)
            ctx.line_to(x, PAGE_HEIGHT - CARD_MARGIN)
        for row in range(6):
            y = CARD_MARGIN + row * CARD_HEIGHT
            ctx.move_to(CARD_MARGIN, y)
            ctx.line_to(PAGE_WIDTH - CARD_MARGIN, y)
        ctx.stroke()
        ctx.set_dash([])
        for offset, team in enumerate(teams[start:start + 10]):
            x = CARD_MARGIN + (offset % 2) * CARD_WIDTH + 16
            y = CARD_MARGIN + (offset // 2) * CARD_HEIGHT
            ctx.set_source_rgb(.13, .13, .17)
            text("Monster Draft Duel", x, y + 23, 12, bold=True)
            text("Team login card", x, y + 38, 9)
            text("Username", x, y + 61, 9)
            text(team["username"], x, y + 81, 16, mono=True, bold=True)
            text("Password", x, y + 103, 9)
            text(team["password"], x, y + 126, 20, mono=True, bold=True)
            text("Keep private - for your team only.", x, y + 144, 8)
        ctx.show_page()
    surface.finish()
    return output.getvalue()
