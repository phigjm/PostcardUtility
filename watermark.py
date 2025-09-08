import io
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


def create_watermark_diagonal(text, pagesize=A4):
    """
    Erzeugt ein PDF im Speicher mit einem Text-Wasserzeichen.
    """
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=pagesize)

    # Text gestalten
    can.setFont("Helvetica", 40)
    can.setFillGray(0.7, 0.5)  # Grau, leicht transparent
    can.saveState()
    can.translate(
        pagesize[0] / 2, pagesize[1] / 2
    )  # <-- hier beide Koordinaten korrekt
    can.rotate(45)
    can.drawCentredString(0, 0, text)
    can.restoreState()

    can.save()
    packet.seek(0)
    return PdfReader(packet)


def create_watermark_top_center(text, pagesize=A4):
    """
    Erzeugt ein PDF im Speicher mit einem Text-Wasserzeichen oben mittig.
    """
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=pagesize)
    # Schrift kleiner und oben mittig
    can.setFont("Helvetica", 8)
    can.setFillGray(0.7, 0.5)
    can.saveState()
    x = pagesize[0] / 2
    y = pagesize[1] - 20  # 30 Punkte vom oberen Rand
    can.drawCentredString(x, y, text)
    can.restoreState()
    can.save()
    packet.seek(0)
    return PdfReader(packet)


def create_watermark_bottom_Left(text, pagesize=A4):
    """
    Erzeugt ein PDF im Speicher mit einem Text-Wasserzeichen oben mittig.
    """
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=pagesize)
    # Schrift kleiner und oben mittig
    can.setFont("Helvetica", 5)
    can.setFillGray(0, 0.5)
    can.saveState()
    x = 20
    y = 0 + 20  # 30 Punkte vom oberen Rand
    # can.drawCentredString(x, y, text)
    can.drawString(
        x, y, text
    )  # Fallback für PDF-Reader, die drawCentredString nicht unterstützen
    can.restoreState()
    can.save()
    packet.seek(0)
    return PdfReader(packet)


def add_watermark(input_pdf, output_pdf, watermark_text, page_number=2):
    """
    Input-PDF mit Wasserzeichen auf ausgewählten Seiten versehen und ins Output-PDF schreiben.
    """
    # Standard: alle Seiten
    if isinstance(watermark_text, tuple):
        watermark_text, page_number = watermark_text
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    num_pages = len(reader.pages)
    # Seitenwahl: 0 = keine, -1 = alle, sonst bestimmte Seite (1-basiert)
    for idx, page in enumerate(reader.pages):
        apply = False
        if page_number == -1:
            apply = True
        elif page_number == 0:
            apply = False
        elif idx == (page_number - 1):
            apply = True
        if apply:
            wmark_pdf = create_watermark_bottom_Left(
                watermark_text,
                pagesize=(float(page.mediabox.width), float(page.mediabox.height)),
            )
            watermark_page = wmark_pdf.pages[0]
            page.merge_page(watermark_page)
        writer.add_page(page)

    with open(output_pdf, "wb") as f_out:
        writer.write(f_out)


if __name__ == "__main__":
    input_file = "Examples/postcard.pdf"
    output_file = "Examples/output2.pdf"
    watermark_text = "ServiceCard.de"

    add_watermark(input_file, output_file, watermark_text)
