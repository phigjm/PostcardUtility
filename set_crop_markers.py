from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import io


def generate_crop_marks_pdf(
    page_width, page_height, bleed_area_width_mm, bleed_area_height_mm, mark_distance_mm
):
    """
    Generate crop marks that start from the edge of the PDF and extend inward by bleed_area distance.
    The marks stop mark_distance_mm before reaching the content area.
    """
    # Convert bleed area to points
    bleed_area_width_pt = bleed_area_width_mm * mm
    bleed_area_height_pt = bleed_area_height_mm * mm

    # Mark length is the bleed area minus the distance from content
    mark_length_x = (bleed_area_width_mm - mark_distance_mm) * mm
    mark_length_y = (bleed_area_height_mm - mark_distance_mm) * mm

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    def draw_crop_mark_line(x1, y1, x2, y2):
        """Draw a crop mark line with white background and black foreground."""
        # White line (background)
        c.setStrokeColorRGB(1, 1, 1)
        c.setLineWidth(0.6 * 3)
        c.line(x1, y1, x2, y2)
        # Black line (foreground)
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.6)
        c.line(x1, y1, x2, y2)

    # Top-left corner - marks start from edge (0, page_height) and extend inward
    draw_crop_mark_line(
        bleed_area_width_pt,
        page_height,
        bleed_area_width_pt,
        page_height - mark_length_y,
    )  # vertical down from top edge
    draw_crop_mark_line(
        0,
        page_height - bleed_area_height_pt,
        mark_length_x,
        page_height - bleed_area_height_pt,
    )  # horizontal right from left edge

    # Bottom-left corner - marks start from edge (0,0) and extend inward
    draw_crop_mark_line(
        bleed_area_width_pt,
        0,
        bleed_area_width_pt,
        mark_length_y,
    )  # vertical up from bottom edge
    draw_crop_mark_line(
        0,
        bleed_area_height_pt,
        mark_length_x,
        bleed_area_height_pt,
    )  # horizontal right from left edge

    # Bottom-right corner - marks start from edge (page_width, 0) and extend inward
    draw_crop_mark_line(
        page_width - bleed_area_width_pt,
        0,
        page_width - bleed_area_width_pt,
        mark_length_y,
    )  # vertical up from bottom edge
    draw_crop_mark_line(
        page_width,
        bleed_area_height_pt,
        page_width - mark_length_x,
        bleed_area_height_pt,
    )  # horizontal left from right edge

    # Top-right corner - marks start from edge (page_width, page_height) and extend inward
    draw_crop_mark_line(
        page_width - bleed_area_width_pt,
        page_height,
        page_width - bleed_area_width_pt,
        page_height - mark_length_y,
    )  # vertical down from top edge
    draw_crop_mark_line(
        page_width,
        page_height - bleed_area_height_pt,
        page_width - mark_length_x,
        page_height - bleed_area_height_pt,
    )  # horizontal left from right edge

    c.save()
    packet.seek(0)
    reader = PdfReader(packet)
    return reader.pages[0]


def add_crop_marks_to_pdf(
    input_pdf_path,
    output_pdf_path=None,
    bleed_area_width_mm=3,
    bleed_area_height_mm=None,
    mark_distance_mm=1,
    page_numbers=None,
):
    """
    Add crop marks to the PDF file on specified pages or all pages by default.
    """
    if output_pdf_path is None:
        output_pdf_path = input_pdf_path.replace(".pdf", "_with_crop_marks.pdf")
    if bleed_area_height_mm is None:
        bleed_area_height_mm = bleed_area_width_mm

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    num_pages = len(reader.pages)
    for i in range(num_pages):
        if (page_numbers is not None) and (i + 1 not in page_numbers):
            writer.add_page(reader.pages[i])
            continue

        page = reader.pages[i]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        # Get crop mark page for this page size
        crop_marks_page = generate_crop_marks_pdf(
            width,
            height,
            bleed_area_width_mm,
            bleed_area_height_mm,
            mark_distance_mm,
        )

        # Merge crop marks onto the page
        page.merge_page(crop_marks_page)
        writer.add_page(page)

    with open(output_pdf_path, "wb") as f:
        writer.write(f)


if __name__ == "__main__":

    add_crop_marks_to_pdf(
        "C:/Users/gjm/Projecte/PostCard/Examples/postcard.pdf",
        "C:/Users/gjm/Projecte/PostCard/Examples/postcard_with_crop_marks.pdf",
        bleed_area_width_mm=3,
        bleed_area_height_mm=3,
        mark_distance_mm=1,
    )
    print("Crop marks added successfully.")
