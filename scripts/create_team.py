#!/usr/bin/env python3
"""Create one team with a generated password; run once per team or from a roster loop."""
import argparse
import csv
import io
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arena.service import APIError, Service
from arena.storage import Database


def credential_pdf(username, name, password):
    """Render one private A4 credential sheet with shaped Persian text."""
    try:
        import cairo
        import gi
        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import Pango, PangoCairo
    except (ImportError, ValueError) as exc:
        raise RuntimeError("PDF export requires python3-gi, python3-cairo and gir1.2-pango-1.0") from exc
    output = io.BytesIO()
    surface = cairo.PDFSurface(output, 595.28, 841.89)
    ctx = cairo.Context(surface)
    surface.set_metadata(cairo.PDF_METADATA_TITLE, "Monster Draft Duel - team credentials")

    def draw(text, y, size=14, rtl=False, bold=False):
        layout = PangoCairo.create_layout(ctx)
        PangoCairo.context_set_resolution(layout.get_context(), 72)
        layout.set_width(483 * Pango.SCALE)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_font_description(Pango.FontDescription(
            ("DejaVu Sans" if rtl else "DejaVu Sans Mono")
            + (" Bold" if bold else "") + f" {size}"))
        layout.get_context().set_base_dir(Pango.Direction.RTL if rtl else Pango.Direction.LTR)
        layout.set_auto_dir(False)
        layout.set_alignment(Pango.Alignment.RIGHT if rtl else Pango.Alignment.LEFT)
        layout.set_text(text, -1)
        ctx.move_to(56, y)
        PangoCairo.show_layout(ctx, layout)

    ctx.set_source_rgb(.22, .15, .34)
    draw("نبرد هیولاها", 58, 25, rtl=True, bold=True)
    draw("اطلاعات ورود تیم", 103, 15, rtl=True)
    ctx.set_source_rgb(.91, .89, .95)
    ctx.rectangle(56, 147, 483, 2)
    ctx.fill()
    ctx.set_source_rgb(.15, .15, .19)
    draw(name, 178, 20, rtl=True, bold=True)
    draw("Username", 280, 11)
    draw(username, 308, 20, bold=True)
    draw("Password", 380, 11)
    draw(password, 408, 20, bold=True)
    draw("این برگه را فقط در اختیار اعضای تیم قرار دهید.", 550, 12, rtl=True)
    draw("Keep this sheet private. Passwords are case-sensitive.", 600, 10)
    ctx.show_page()
    surface.finish()
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="3..32 ASCII letters, digits, dots, underscores or hyphens")
    parser.add_argument("name", help="Team display name, 1..60 characters")
    parser.add_argument("--data", type=Path, help="Defaults to ARENA_DATA or repository var/")
    parser.add_argument("--output", type=Path, required=True, help="New private CSV file; never overwritten")
    parser.add_argument("--pdf", type=Path, help="Also export a new private PDF credential sheet")
    args = parser.parse_args()
    db = Database(args.data)
    admin = db.one("SELECT * FROM users WHERE role='admin' AND active=1 LIMIT 1")
    if not admin:
        parser.error("Initialize an administrator with python3 -m arena init first")
    password = secrets.token_urlsafe(18)
    # Render before creating files/accounts, so missing PDF dependencies are harmless.
    try:
        pdf = credential_pdf(args.username.strip(), args.name.strip(), password) if args.pdf else None
    except RuntimeError as exc:
        parser.error(str(exc))
    created = []
    try:
        # Write both artifacts before the database mutation; never overwrite files.
        for path, binary in [(args.output, False)] + ([(args.pdf, True)] if args.pdf else []):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created.append(path)
            with os.fdopen(fd, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8", "newline": ""})) as handle:
                if binary:
                    handle.write(pdf)
                else:
                    writer = csv.writer(handle)
                    writer.writerow(["username", "name", "password"])
                    writer.writerow([args.username.strip(), args.name.strip(), password])
                handle.flush()
                os.fsync(handle.fileno())
    except OSError as exc:
        for path in created:
            path.unlink(missing_ok=True)
        parser.error(f"Cannot write credential files: {exc}")
    try:
        Service(db).create_team(admin, {"username": args.username, "name": args.name, "password": password})
    except APIError as exc:
        for path in created:
            path.unlink(missing_ok=True)
        parser.error(str(exc))
    print("Team created. Credentials saved to the requested private files.")


if __name__ == "__main__":
    main()
