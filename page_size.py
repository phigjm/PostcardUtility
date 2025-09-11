"""
Helper functions for PDF page size operations.
"""

from pypdf import PdfReader


def mm_to_points(mm):
    """Convert millimeters to points (PDF units)"""
    return mm * 2.834645669


def points_to_mm(points):
    """Convert points to millimeters"""
    return points / 2.834645669


def get_page_size_mm(pdf_path, page_number=0):
    """
    Get page size in millimeters for a specific page.

    Args:
        pdf_path: Path to the PDF file
        page_number: Page number (0-based)

    Returns:
        tuple: (width_mm, height_mm)
    """
    try:
        with open(pdf_path, "rb") as file:
            reader = PdfReader(file)
            if page_number >= len(reader.pages):
                raise IndexError(f"Page {page_number} does not exist")

            page = reader.pages[page_number]

            # Get page dimensions in points
            if hasattr(page, "mediabox"):
                box = page.mediabox
            elif hasattr(page, "mediaBox"):
                box = page.mediaBox
            else:
                raise ValueError("Cannot find media box")

            width_points = float(box.width)
            height_points = float(box.height)

            # Convert to millimeters
            width_mm = points_to_mm(width_points)
            height_mm = points_to_mm(height_points)

            return (width_mm, height_mm)
    except Exception as e:
        raise Exception(f"Error getting page size: {str(e)}")


def get_pdf_page_count(pdf_path):
    """
    Get the total number of pages in a PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        int: Number of pages
    """
    try:
        with open(pdf_path, "rb") as file:
            reader = PdfReader(file)
            return len(reader.pages)
    except Exception as e:
        raise Exception(f"Error getting page count: {str(e)}")
