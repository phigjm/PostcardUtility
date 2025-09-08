import argparse

from pypdf import PdfReader, PdfWriter
import sys
import os
import fitz  # PyMuPDF
import numpy as np


def mm_to_points(mm):
    """Convert millimeters to points (PDF units)"""
    return mm * 2.834645669


def points_to_mm(points):
    """Convert points to millimeters"""
    return points / 2.834645669


def get_page_dimensions(page):
    """Get page dimensions in points"""
    if hasattr(page, "mediabox"):
        box = page.mediabox
    elif hasattr(page, "mediaBox"):
        box = page.mediaBox
    else:
        raise ValueError("Cannot find media box")

    width = float(box.width)
    height = float(box.height)
    return width, height


def calculate_scale_factor(current_width, current_height, target_width, target_height):
    """Calculate scale factor to fit content within target dimensions"""
    scale_x = target_width / current_width
    scale_y = target_height / current_height
    return min(scale_x, scale_y)  # Use smaller scale to ensure content fits


def should_rotate(width, height, target_width, target_height):
    """Check if rotating the page would result in a better fit"""
    # Calculate how much area we lose with current orientation
    scale_normal = calculate_scale_factor(width, height, target_width, target_height)
    area_normal = (width * scale_normal) * (height * scale_normal)

    # Calculate how much area we lose with rotated orientation
    scale_rotated = calculate_scale_factor(height, width, target_width, target_height)
    area_rotated = (height * scale_rotated) * (width * scale_rotated)

    return area_rotated > area_normal


def detect_white_border(
    pdf_path, page_number=0, white_threshold=240, min_border_mm=5.0, dpi=150
):
    """
    Detect white borders in a PDF page and calculate their size.

    Args:
        pdf_path: Path to the PDF file
        page_number: Page number to analyze (0-based)
        white_threshold: Grayscale value above which pixels are considered white (0-255)
        min_border_mm: Minimum border size in mm to be considered significant
        dpi: DPI for PDF to image conversion (higher = more accurate but slower)

    Returns:
        dict: {
            'has_large_border': bool,  # True if any border > min_border_mm
            'border_sizes_mm': {       # Border sizes in mm
                'top': float,
                'bottom': float,
                'left': float,
                'right': float
            },
            'needs_bleed': bool,       # True if colored content reaches edges
            'page_size_mm': tuple      # (width_mm, height_mm)
        }
    """
    try:
        # Open PDF with PyMuPDF
        pdf_doc = fitz.open(pdf_path)

        if page_number >= len(pdf_doc):
            raise ValueError(
                f"Page {page_number} not found in PDF (has {len(pdf_doc)} pages)"
            )

        page = pdf_doc[page_number]

        # Get page dimensions in points and convert to mm
        page_rect = page.rect
        page_width_mm = points_to_mm(page_rect.width)
        page_height_mm = points_to_mm(page_rect.height)

        # Convert PDF page to image
        # Calculate matrix for desired DPI
        zoom = dpi / 72.0  # 72 DPI is default
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)

        # Convert to numpy array
        img_data = np.frombuffer(pix.samples, dtype=np.uint8)
        img_array = img_data.reshape(pix.height, pix.width)

        pdf_doc.close()

        # Calculate pixels per mm for this resolution
        pixels_per_mm = dpi / 25.4
        min_border_pixels = int(min_border_mm * pixels_per_mm)

        height, width = img_array.shape

        # Find white borders by scanning from edges inward
        border_sizes_pixels = {"top": 0, "bottom": 0, "left": 0, "right": 0}

        # Top border
        for row in range(height):
            if np.all(img_array[row, :] >= white_threshold):
                border_sizes_pixels["top"] = row + 1
            else:
                break

        # Bottom border
        for row in range(height - 1, -1, -1):
            if np.all(img_array[row, :] >= white_threshold):
                border_sizes_pixels["bottom"] = height - row
            else:
                break

        # Left border
        for col in range(width):
            if np.all(img_array[:, col] >= white_threshold):
                border_sizes_pixels["left"] = col + 1
            else:
                break

        # Right border
        for col in range(width - 1, -1, -1):
            if np.all(img_array[:, col] >= white_threshold):
                border_sizes_pixels["right"] = width - col
            else:
                break

        # Convert pixel measurements to mm
        border_sizes_mm = {
            side: pixels / pixels_per_mm for side, pixels in border_sizes_pixels.items()
        }

        # Check if any border is larger than minimum threshold
        has_large_border = any(
            size >= min_border_mm for size in border_sizes_mm.values()
        )

        # Determine if content needs bleed (colored content reaches edges)
        # If borders are very small, content likely reaches edges
        needs_bleed = any(
            size < 1.0 for size in border_sizes_mm.values()
        )  # Less than 1mm border

        result = {
            "has_large_border": has_large_border,
            "border_sizes_mm": border_sizes_mm,
            "needs_bleed": needs_bleed,
            "page_size_mm": (page_width_mm, page_height_mm),
        }

        return result

    except Exception as e:
        print(f"Error detecting white borders: {str(e)}")
        return None


def analyze_pdf_for_printing(pdf_path, min_border_mm=5.0, white_threshold=240):
    """
    Analyze a PDF to determine printing requirements.

    Args:
        pdf_path: Path to the PDF file
        min_border_mm: Minimum border size in mm to be considered significant
        white_threshold: Grayscale value above which pixels are considered white

    Returns:
        dict: Analysis results for printing decisions
    """
    border_info = detect_white_border(pdf_path, 0, white_threshold, min_border_mm)

    if not border_info:
        return None

    # Determine printing recommendation
    if border_info["needs_bleed"]:
        recommendation = "BLEED_REQUIRED"
        message = "Colored content reaches edges - requires 3mm bleed for printing"
    elif border_info["has_large_border"]:
        recommendation = "SAFE_TO_PRINT"
        message = f"Has sufficient white borders (min: {min(border_info['border_sizes_mm'].values()):.1f}mm)"
    else:
        recommendation = "CHECK_MANUALLY"
        message = "Borders are small but may be sufficient - manual review recommended"

    return {
        "recommendation": recommendation,
        "message": message,
        "border_info": border_info,
    }


def crop_and_scale_page(
    page, target_width_mm, target_height_mm, enable_rotation=False, crop_to_fill=True
):
    """Crop and scale a PDF page to target dimensions

    Args:
        page: PDF page object to process
        target_width_mm: Target width in millimeters
        target_height_mm: Target height in millimeters
        enable_rotation: Whether to enable automatic rotation for better fit
        crop_to_fill: If True (default), crop content to fill entire area without borders.
                     If False, fit content within area and add white borders if needed.
    """
    target_width = mm_to_points(target_width_mm)
    target_height = mm_to_points(target_height_mm)

    # Get current page dimensions
    current_width, current_height = get_page_dimensions(page)

    print(
        f"Original page size: {points_to_mm(current_width):.1f}x{points_to_mm(current_height):.1f}mm"
    )

    # Check if rotation would be beneficial
    rotate = False
    if enable_rotation and should_rotate(
        current_width, current_height, target_width, target_height
    ):
        rotate = True
        current_width, current_height = current_height, current_width
        page.rotate(90)
        print("Rotated page 90 degrees for better fit")

    # Calculate scale factor based on crop_to_fill setting
    scale_x = target_width / current_width
    scale_y = target_height / current_height

    if crop_to_fill:
        # Use larger scale to fill entire area (may crop content)
        scale_factor = max(scale_x, scale_y)
        print(f"Scale factor (crop-to-fill): {scale_factor:.3f}")
    else:
        # Use smaller scale to fit content within area (may add borders)
        scale_factor = min(scale_x, scale_y)
        print(f"Scale factor (fit-with-borders): {scale_factor:.3f}")

    # Scale the page
    page.scale(scale_factor, scale_factor)

    # Calculate the dimensions after scaling
    scaled_width = current_width * scale_factor
    scaled_height = current_height * scale_factor

    print(
        f"Scaled size: {points_to_mm(scaled_width):.1f}x{points_to_mm(scaled_height):.1f}mm"
    )

    if crop_to_fill:
        # Calculate how much to crop from each side to center the content
        crop_x = (scaled_width - target_width) / 2
        crop_y = (scaled_height - target_height) / 2

        print(
            f"Cropping: {points_to_mm(crop_x):.1f}mm from left/right, {points_to_mm(crop_y):.1f}mm from top/bottom"
        )

        # Set the media box to the exact target size
        # The crop values determine which part of the scaled content is visible
        page.mediabox.lower_left = (crop_x, crop_y)
        page.mediabox.upper_right = (crop_x + target_width, crop_y + target_height)

        # Set crop box to match media box for proper display in all viewers
        page.cropbox.lower_left = (crop_x, crop_y)
        page.cropbox.upper_right = (crop_x + target_width, crop_y + target_height)

        # Also set trim box and bleed box if they exist to ensure compatibility
        if hasattr(page, "trimbox"):
            page.trimbox.lower_left = (crop_x, crop_y)
            page.trimbox.upper_right = (crop_x + target_width, crop_y + target_height)

        if hasattr(page, "bleedbox"):
            page.bleedbox.lower_left = (crop_x, crop_y)
            page.bleedbox.upper_right = (crop_x + target_width, crop_y + target_height)
    else:
        # Calculate how much white border to add on each side to center the content
        border_x = (target_width - scaled_width) / 2
        border_y = (target_height - scaled_height) / 2

        print(
            f"Adding borders: {points_to_mm(border_x):.1f}mm left/right, {points_to_mm(border_y):.1f}mm top/bottom"
        )

        # Set the media box to the exact target size with content centered
        page.mediabox.lower_left = (-border_x, -border_y)
        page.mediabox.upper_right = (scaled_width + border_x, scaled_height + border_y)

        # Set crop box to show only the target area
        page.cropbox.lower_left = (-border_x, -border_y)
        page.cropbox.upper_right = (target_width - border_x, target_height - border_y)

        # Also set trim box and bleed box if they exist
        if hasattr(page, "trimbox"):
            page.trimbox.lower_left = (-border_x, -border_y)
            page.trimbox.upper_right = (
                target_width - border_x,
                target_height - border_y,
            )

        if hasattr(page, "bleedbox"):
            page.bleedbox.lower_left = (-border_x, -border_y)
            page.bleedbox.upper_right = (
                target_width - border_x,
                target_height - border_y,
            )

    print(f"Final page size: {target_width_mm}x{target_height_mm}mm")

    return page


def process_pdf(
    input_path,
    output_path,
    target_width_mm=148,
    target_height_mm=105,
    enable_rotation=False,
    crop_to_fill=True,
):
    """Process PDF file and crop/scale all pages

    Args:
        input_path: Path to input PDF file
        output_path: Path to output PDF file
        target_width_mm: Target width in millimeters
        target_height_mm: Target height in millimeters
        enable_rotation: Whether to enable automatic rotation for better fit
        crop_to_fill: If True (default), crop content to fill area. If False, add borders.
    """
    try:
        # Read the input PDF
        with open(input_path, "rb") as input_file:
            reader = PdfReader(input_file)
            writer = PdfWriter()

            print(f"Processing {len(reader.pages)} page(s)...")
            print(f"Mode: {'Crop-to-fill' if crop_to_fill else 'Fit-with-borders'}")

            # Process each page
            for i, page in enumerate(reader.pages):
                print(f"\nProcessing page {i + 1}:")
                processed_page = crop_and_scale_page(
                    page,
                    target_width_mm,
                    target_height_mm,
                    enable_rotation,
                    crop_to_fill,
                )
                writer.add_page(processed_page)

            # Write the output PDF
            with open(output_path, "wb") as output_file:
                writer.write(output_file)

        print(f"\nSuccessfully processed PDF: {output_path}")

    except FileNotFoundError:
        print(f"Error: Input file '{input_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        sys.exit(1)


def main():
    # If no arguments provided, run with hardcoded values for testing
    if len(sys.argv) == 1:
        print("No arguments provided, running with test values...")

        # Test border detection
        test_pdf = r"C:\Users\gjm\Projecte\PostCard\data\D12EE6D3\D12EE6D3.pdf"
        print("\n=== Testing Border Detection ===")
        analysis = analyze_pdf_for_printing(test_pdf, min_border_mm=5.0)
        if analysis:
            print(f"Recommendation: {analysis['recommendation']}")
            print(f"Message: {analysis['message']}")
            print(f"Border sizes: {analysis['border_info']['border_sizes_mm']}")
            print(f"Page size: {analysis['border_info']['page_size_mm']}")

        print("\n=== Processing PDF ===")
        process_pdf(
            test_pdf,
            r"Examples/postcard_cropped2.pdf",
            148,
            105,
            False,
            False,  # crop_to_fill=True (default behavior)
        )
        return

    parser = argparse.ArgumentParser(
        description="Crop and scale PDF to specified dimensions"
    )
    parser.add_argument("input_path", help="Path to input PDF file")
    parser.add_argument("output_path", help="Path to output PDF file")
    parser.add_argument(
        "--width", type=float, default=148, help="Target width in mm (default: 148)"
    )
    parser.add_argument(
        "--height", type=float, default=105, help="Target height in mm (default: 105)"
    )
    parser.add_argument(
        "--rotate", action="store_true", help="Enable automatic rotation for better fit"
    )
    parser.add_argument(
        "--add-borders",
        action="store_true",
        help="Fit content with white borders instead of cropping (default: crop to fill)",
    )
    parser.add_argument(
        "--check-borders",
        action="store_true",
        help="Analyze white borders and printing requirements before processing",
    )
    parser.add_argument(
        "--min-border",
        type=float,
        default=5.0,
        help="Minimum border size in mm to be considered significant (default: 5.0)",
    )
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=240,
        help="Grayscale threshold for white detection 0-255 (default: 240)",
    )

    args = parser.parse_args()

    # Check borders if requested
    if args.check_borders:
        print("=== Analyzing PDF for printing requirements ===")
        analysis = analyze_pdf_for_printing(
            args.input_path, args.min_border, args.white_threshold
        )
        if analysis:
            print(f"Recommendation: {analysis['recommendation']}")
            print(f"Message: {analysis['message']}")
            print(f"Border sizes (mm): {analysis['border_info']['border_sizes_mm']}")
            print(f"Page size (mm): {analysis['border_info']['page_size_mm']}")
            print()
        else:
            print("Failed to analyze borders.")
            return

    # Convert --add-borders to crop_to_fill (inverse logic)
    crop_to_fill = not args.add_borders

    process_pdf(
        args.input_path,
        args.output_path,
        args.width,
        args.height,
        args.rotate,
        crop_to_fill,
    )


if __name__ == "__main__":
    main()
