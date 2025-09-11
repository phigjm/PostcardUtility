from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
import io


def draw_bleed_area(pdf_input, pdf_output, bleed_mm=3):
    """# add transparent gray border of bleed_mm to ontop of the existing pdf."""

    # Read the existing PDF
    reader = PdfReader(pdf_input)
    writer = PdfWriter()
    bleed_pts = bleed_mm * mm

    for page in reader.pages:
        # Get page width and height in points
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        # Create an in-memory PDF with the bleed border
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_width, page_height))

        # Set transparent gray color (e.g., 50% gray with 30% opacity)
        can.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.7)

        # Draw four rectangles around the edges to simulate a border bleed area
        # Top border
        can.rect(0, page_height - bleed_pts, page_width, bleed_pts, fill=1, stroke=0)
        # Bottom border
        can.rect(0, 0, page_width, bleed_pts, fill=1, stroke=0)
        # Left border
        can.rect(0, 0, bleed_pts, page_height, fill=1, stroke=0)
        # Right border
        can.rect(page_width - bleed_pts, 0, bleed_pts, page_height, fill=1, stroke=0)

        can.save()

        # Move to the beginning of the StringIO buffer
        packet.seek(0)

        # Read the overlay PDF created with ReportLab
        overlay_pdf = PdfReader(packet)
        overlay_page = overlay_pdf.pages[0]

        # Merge the overlay (with bleed border) on top of the original page
        page.merge_page(overlay_page)

        # Add the merged page to the writer
        writer.add_page(page)

    # Write to output PDF
    with open(pdf_output, "wb") as output_file:
        writer.write(output_file)


def draw_cutting_area(
    pdf_input, pdf_output, cut_edge_x_mm=3, cut_edge_y_mm=3, tolerances_mm=3
):
    """adds a dashed line to indicate the cutting area and a transparent gray border of bleed_mm centered on the cutting line to ontop of the existing pdf."""

    reader = PdfReader(pdf_input)
    writer = PdfWriter()

    cut_edge_x_pts = cut_edge_x_mm * mm
    cut_edge_y_pts = cut_edge_y_mm * mm
    tolerances_pts = tolerances_mm / 2 * mm
    border_width_pts = 2 * tolerances_pts

    for page in reader.pages:
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(page_width, page_height))

        # Draw transparent gray borders centered at the cut edge - top/bottom
        can.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.3)
        # Top border centered on cut edge
        y_top = page_height - cut_edge_y_pts - tolerances_pts
        can.rect(0, y_top, page_width, border_width_pts, fill=1, stroke=0)

        # Bottom border centered on cut edge
        y_bottom = cut_edge_y_pts - tolerances_pts
        can.rect(0, y_bottom, page_width, border_width_pts, fill=1, stroke=0)

        # Left and right borders centered on cut edge
        x_left = cut_edge_x_pts - tolerances_pts
        can.rect(x_left, 0, border_width_pts, page_height, fill=1, stroke=0)

        x_right = page_width - cut_edge_x_pts - tolerances_pts
        can.rect(x_right, 0, border_width_pts, page_height, fill=1, stroke=0)

        # Draw dashed cutting lines on the cut edges
        can.setStrokeColorRGB(0, 0, 0)
        can.setLineWidth(0.5)
        can.setDash(3, 3)  # 3 points dash, 3 points gap

        # Horizontal dashed lines (top and bottom cut edge)
        can.line(
            0, page_height - cut_edge_y_pts, page_width, page_height - cut_edge_y_pts
        )
        can.line(0, cut_edge_y_pts, page_width, cut_edge_y_pts)

        # Vertical dashed lines (left and right cut edge)
        can.line(cut_edge_x_pts, 0, cut_edge_x_pts, page_height)
        can.line(
            page_width - cut_edge_x_pts, 0, page_width - cut_edge_x_pts, page_height
        )

        can.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        overlay_page = overlay_pdf.pages[0]

        page.merge_page(overlay_page)
        writer.add_page(page)

    with open(pdf_output, "wb") as output_file:
        writer.write(output_file)


if __name__ == "__main__":
    input_pdf = "Examples/postcard.pdf"
    output_pdf = "Examples/postcard_with_bleed.pdf"
    output_pdf = "Examples/postcard_with_cutting.pdf"
    draw_bleed_area(input_pdf, output_pdf)
    draw_cutting_area(input_pdf, output_pdf)
    print(f"Bleed area added and saved to {output_pdf}")
