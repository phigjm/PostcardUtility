import argparse

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Rectangle
import sys
import os
import fitz  # PyMuPDF
import numpy as np


from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
import tempfile
import io


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
        # todo difference to page_rect = page.rect

    width = float(box.width)
    height = float(box.height)
    return width, height


def get_page_dimensions_in_mm(page):
    """Get page dimensions in millimeters"""
    width, height = get_page_dimensions(page)
    return points_to_mm(width), points_to_mm(height)


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


def get_min_border_size(border_sizes):
    return min(size for size in border_sizes.values())


def detect_border(np_image, tolerance=10, skip=1):
    """
    Detect if an image has a border, what the border color is, and the border thickness.
    Assumes np_image is a numpy array of shape (H, W, C) or (H, W) for grayscale.
    Tolerance is for color variation within the border.

    Returns:
        minsize (float): Minimal border size detected
        border_color (tuple or int): Color of the border (RGB tuple or grayscale int)
        border_sizes (dict): Thickness of border on each side: {'top', 'bottom', 'left', 'right'}
    """

    def is_uniform_color(arr, tol):
        """Check if all colors in arr are within tol of the median color"""
        if len(arr.shape) == 1:  # Grayscale
            median_color = np.median(arr)
            return np.all(np.abs(arr - median_color) <= tol)
        else:  # Color image
            # Use median color as reference (more robust than first pixel)
            median_color = np.median(arr, axis=0)
            # Calculate color distance for each pixel
            distances = np.linalg.norm(arr - median_color, axis=1)
            # Allow up to 10% of pixels to be outliers
            outlier_threshold = len(arr) * 0.1
            within_tolerance = np.sum(distances <= tol)
            return within_tolerance >= (len(arr) - outlier_threshold)

    h, w = np_image.shape[:2]
    channels = 1 if np_image.ndim == 2 else np_image.shape[2]

    border_sizes = {"top": 0, "bottom": 0, "left": 0, "right": 0}
    border_color = None

    # Ignore the outermost 3 pixel rows/columns

    # Check Top border thickness
    for i in range(skip, h):
        line = np_image[i, :, :] if channels > 1 else np_image[i, :]
        if not is_uniform_color(line, tolerance):
            break
        border_sizes["top"] = i + 1 - skip

    # Check Bottom border thickness
    for i in range(skip, h):
        line = np_image[h - i - 1, :, :] if channels > 1 else np_image[h - i - 1, :]
        if not is_uniform_color(line, tolerance):
            break
        border_sizes["bottom"] = i + 1 - skip

    # Check Left border thickness
    for i in range(skip, w):
        line = np_image[:, i, :] if channels > 1 else np_image[:, i]
        if not is_uniform_color(line, tolerance):
            break
        border_sizes["left"] = i + 1 - skip

    # Check Right border thickness
    for i in range(skip, w):
        line = np_image[:, w - i - 1, :] if channels > 1 else np_image[:, w - i - 1]
        if not is_uniform_color(line, tolerance):
            break
        border_sizes["right"] = i + 1 - skip

    # Clamp to zero if negative (in case border is thinner than skip)
    for side in border_sizes:
        if border_sizes[side] < 0:
            border_sizes[side] = 0

    minsize = get_min_border_size(border_sizes)

    # todo border_color average over border area
    def average_color(border_sizes, np_image, channels, skip):
        colors = []
        if border_sizes["top"] > 0:
            colors.append(np_image[skip : skip + border_sizes["top"], skip : w - skip])
        if border_sizes["bottom"] > 0:
            colors.append(
                np_image[h - skip - border_sizes["bottom"] : h - skip, skip : w - skip]
            )
        if border_sizes["left"] > 0:
            colors.append(np_image[skip : h - skip, skip : skip + border_sizes["left"]])
        if border_sizes["right"] > 0:
            colors.append(
                np_image[skip : h - skip, w - skip - border_sizes["right"] : w - skip]
            )
        if not colors:
            return None
        all_border_pixels = np.vstack([c.reshape(-1, channels) for c in colors])
        if channels == 1:
            return int(np.mean(all_border_pixels))
        else:
            return tuple(map(int, np.mean(all_border_pixels, axis=0)))

    # If border detected, determine border color: take the first pixel of top border or fallback

    border_color = average_color(border_sizes, np_image, channels, skip)
    return border_color, border_sizes
    if minsize > 0:
        if border_sizes["top"] > 0:
            border_color = (
                tuple(np_image[skip, skip])
                if channels > 1
                else int(np_image[skip, skip])
            )
        elif border_sizes["bottom"] > 0:
            border_color = (
                tuple(np_image[h - skip - 1, skip])
                if channels > 1
                else int(np_image[h - skip - 1, skip])
            )
        elif border_sizes["left"] > 0:
            border_color = (
                tuple(np_image[skip, skip])
                if channels > 1
                else int(np_image[skip, skip])
            )
        else:
            border_color = (
                tuple(np_image[skip, w - skip - 1])
                if channels > 1
                else int(np_image[skip, w - skip - 1])
            )
    else:
        border_color = None


def detect_pdf_border(pdf_path, page_number=0, tolerance=10, dpi=150, skip=1):
    """
    Detect borders in a PDF page (color-independent) and calculate their size using detect_border.

    Args:
        pdf_path: Path to the PDF file
        page_number: Page number to analyze (0-based)
        tolerance: Color tolerance for border detection
        min_border_mm: Minimum border size in mm to be considered significant
        dpi: DPI for PDF to image conversion (higher = more accurate but slower)

    Returns:
        dict: {
            'border_sizes_mm': {       # Border sizes in mm
                'top': float,
                'bottom': float,
                'left': float,
                'right': float
            },
            'border_color': tuple or int,  # Detected border color
            'page_size_mm': tuple      # (width_mm, height_mm)
        }
    """
    try:
        pdf_doc = fitz.open(pdf_path)
        if page_number >= len(pdf_doc):
            raise ValueError(
                f"Page {page_number} not found in PDF (has {len(pdf_doc)} pages)"
            )
        page = pdf_doc[page_number]
        page_width_mm, page_height_mm = get_page_dimensions_in_mm(page)

        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to numpy array
        img_data = np.frombuffer(pix.samples, dtype=np.uint8)
        if pix.n >= 3:
            img_array = img_data.reshape(pix.height, pix.width, pix.n)
        else:
            img_array = img_data.reshape(pix.height, pix.width)

        pdf_doc.close()

        # save image for debugging
        if False:
            from PIL import Image

            img = Image.fromarray(img_array)
            img.save("debug_page_image.png")

        pixels_per_mm = dpi / 25.4

        # Use detect_border to get border sizes and color
        border_color, border_sizes_pixels = detect_border(
            img_array, tolerance=tolerance, skip=skip
        )

        # print("Detected border sizes (pixels):", border_sizes_pixels)

        # Convert pixel measurements to mm
        border_sizes_mm = {
            side: pixels / pixels_per_mm for side, pixels in border_sizes_pixels.items()
        }

        result = {
            "border_sizes_mm": border_sizes_mm,
            "border_color": border_color,
            "page_size_mm": (page_width_mm, page_height_mm),
        }
        return result
    except Exception as e:
        print(f"Error detecting borders: {str(e)}")
        return None


def scaled_borders_to_target_size(target_width_mm, target_height_mm, results):
    """Scale detected border sizes to target dimensions"""

    border_sizes_mm = results["border_sizes_mm"]

    smallest_scaling = get_scaling_to_fit_results(
        target_width_mm, target_height_mm, results
    )

    scaled_borders = {
        "top": border_sizes_mm["top"] * smallest_scaling,
        "bottom": border_sizes_mm["bottom"] * smallest_scaling,
        "left": border_sizes_mm["left"] * smallest_scaling,
        "right": border_sizes_mm["right"] * smallest_scaling,
    }
    return scaled_borders


def rotate_page_for_optimal_fit(
    page, target_width, target_height, enable_rotation=False
):
    # TODO
    """Rotate page if it would result in better fit to target dimensions

    Args:
        page: PDF page object to process
        target_width: Target width in points
        target_height: Target height in points
        enable_rotation: Whether to enable automatic rotation for better fit

    Returns:
        tuple: (rotated_flag, current_width, current_height) after potential rotation
    """
    current_width, current_height = get_page_dimensions(page)

    rotate = False
    if enable_rotation and should_rotate(
        current_width, current_height, target_width, target_height
    ):
        rotate = True
        current_width, current_height = current_height, current_width
        rotated_page = page.rotate(90)
        print("Rotated page 90 degrees for better fit")
    else:
        rotated_page = page
        print("No rotation applied")

    return rotated_page, rotate, current_width, current_height


def scale_page_to_fit(
    page, current_width, current_height, target_width, target_height, crop_to_fill=True
):
    """Scale page to fit target dimensions

    Args:
        page: PDF page object to process
        current_width: Current page width in points
        current_height: Current page height in points
        target_width: Target width in points
        target_height: Target height in points
        crop_to_fill: If True, scale to fill (may crop). If False, scale to fit (may add borders)

    Returns:
        tuple: (scale_factor, scaled_width, scaled_height)
    """
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

    return scale_factor, scaled_width, scaled_height


def crop_page_to_target(page, scaled_width, scaled_height, target_width, target_height):
    """Crop page to exact target dimensions by setting media and crop boxes

    Args:
        page: PDF page object to process
        scaled_width: Current scaled width in points
        scaled_height: Current scaled height in points
        target_width: Target width in points
        target_height: Target height in points
    """
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


def add_border_to_page(
    page,
    scaled_width,
    scaled_height,
    target_width,
    target_height,
):
    """Add colored borders to center content within target dimensions

    Args:
        page: PDF page object to process
        scaled_width: Current scaled width in points
        scaled_height: Current scaled height in points
        target_width: Target width in points
        target_height: Target height in points
        border_color: RGB color tuple for border (default: white = (1, 1, 1))
    """
    # Calculate how much border to add on each side to center the content
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
    return page


def add_border_with_reportlab(
    path,
    page_width,
    page_height,
    border_x,
    border_y,
    border_sizes_mm,
    border_color,
    overlapping_factor=0.5,
    overdue_border=1,  # in points
):
    """Add colored border rectangles using ReportLab"""
    # Convert border_sizes_mm to points for proper calculation
    border_sizes_points = {
        side: mm_to_points(size_mm) for side, size_mm in border_sizes_mm.items()
    }

    # Apply overlapping factor (now unitless)
    overlapping_factor = overlapping_factor

    # Create canvas with same dimensions as original page
    c = canvas.Canvas(path, pagesize=(page_width, page_height))

    border_color = "000000"  # for debugging
    # Convert border color from hex string to ReportLab color
    if isinstance(border_color, str):
        if len(border_color) == 8:  # RRGGBBAA format
            hex_color = border_color[:6]  # Remove alpha for now
        else:
            hex_color = border_color
        fill_color = HexColor(
            "#" + hex_color if not hex_color.startswith("#") else hex_color
        )
    else:
        fill_color = border_color

    c.setFillColor(fill_color)

    def rect(x, y, width, height, fill=1, stroke=0):
        if width > 0 and height > 0:
            c.rect(x, y, width, height, fill=fill, stroke=stroke)
        else:
            print(f"Skipping rectangle with non-positive dimensions: {width}x{height}")

    # left
    print("left")
    rect(
        -overdue_border,
        -overdue_border,
        (border_x) + overlapping_factor * border_sizes_points["left"] + overdue_border,
        page_height + 2 * overdue_border,
        fill=1,
        stroke=0,
    )

    # top
    print("top")
    rect(
        -overdue_border,
        page_height - (border_y) - overlapping_factor * border_sizes_points["top"],
        page_width + 2 * overdue_border,
        (border_y) + overlapping_factor * border_sizes_points["top"] + overdue_border,
        fill=1,
        stroke=0,
    )

    # right
    print("right")
    rect(
        page_width - (border_x) - overlapping_factor * border_sizes_points["right"],
        -overdue_border,
        (border_x) + overlapping_factor * border_sizes_points["right"] + overdue_border,
        page_height + 2 * overdue_border,
        fill=1,
        stroke=0,
    )
    # bottom
    print("bottom")
    rect(
        -overdue_border,
        -overdue_border,
        page_width + 2 * overdue_border,
        (border_y)
        + overlapping_factor * border_sizes_points["bottom"]
        + overdue_border,
        fill=1,
        stroke=0,
    )

    c.save()

    print(f"Added border rectangles using ReportLab")


def expand_page_centric(
    page,
    target_width,
    target_height,
):
    """Add borders to expand page to target dimensions
    Args:
        page: PDF page object to process
        target_width: Target width in points
        target_height: Target height in points

    Returns:
        page: Modified page object

    Raises:
        ValueError: If page is already larger than target dimensions
    """
    page_width, page_height = get_page_dimensions(page)

    print("pagesizte", page_width, page_height, target_width, target_height)

    # Check if page is already larger than target dimensions
    if page_width > target_width + 0.1:
        raise ValueError(
            f"Page width ({points_to_mm(page_width):.1f}mm) is larger than target width "
            f"({points_to_mm(target_width):.1f}mm). Cannot expand to smaller size."
        )

    if page_height > target_height + 0.1:
        raise ValueError(
            f"Page height ({points_to_mm(page_height):.5f}mm) is larger than target height "
            f"({points_to_mm(target_height):.5f}mm). Cannot expand to smaller size."
        )

    # Warn if page is already the target size
    if abs(page_width - target_width) < 0.1 and abs(page_height - target_height) < 0.1:
        print("Warning: Page is already at target dimensions, no expansion needed.")
        return page, (0, 0)

    # Calculate how much border to add on each side to center the content
    border_x = (target_width - page_width) / 2
    border_y = (target_height - page_height) / 2

    print(
        f"Adding borders: {points_to_mm(border_x):.1f}mm left/right, {points_to_mm(border_y):.1f}mm top/bottom"
    )

    # Translate the page content to account for the new borders
    # This moves the content so it's centered in the new larger page
    try:
        # Try the newer pypdf approach first
        from pypdf.generic import Transformation

        page.add_transformation(Transformation().translate(tx=border_x, ty=border_y))
    except ImportError:
        # Fallback for older pypdf versions
        try:
            from pypdf import Transformation

            page.add_transformation(
                Transformation().translate(tx=border_x, ty=border_y)
            )
        except ImportError:
            # Manual transformation matrix for older versions
            import pypdf.generic as generic

            # Create transformation matrix for translation
            transformation_matrix = [1, 0, 0, 1, border_x, border_y]
            page.add_transformation(transformation_matrix)

    # Set the media box to the exact target size starting from (0,0)
    page.mediabox.lower_left = (0, 0)
    page.mediabox.upper_right = (target_width, target_height)

    # Set crop box to match media box
    page.cropbox.lower_left = (0, 0)
    page.cropbox.upper_right = (target_width, target_height)

    # Also set trim box and bleed box if they exist
    if hasattr(page, "trimbox"):
        page.trimbox.lower_left = (0, 0)
        page.trimbox.upper_right = (target_width, target_height)

    if hasattr(page, "bleedbox"):
        page.bleedbox.lower_left = (0, 0)
        page.bleedbox.upper_right = (target_width, target_height)

    return page, (border_x, border_y)


def get_scaling_to_fit_results(target_width_mm, target_height_mm, results):

    page_width_mm, page_height_mm = results["page_size_mm"]

    return get_scaling_to_fit(
        target_width_mm, target_height_mm, page_width_mm, page_height_mm
    )


def get_scaling_to_fit(
    target_width_mm, target_height_mm, page_width_mm, page_height_mm
):

    scale_x = target_width_mm / page_width_mm
    scale_y = target_height_mm / page_height_mm
    smallest_scaling = min(scale_x, scale_y)
    return smallest_scaling


def rgb_to_hex(rgb):
    return "{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])


def scale_page_with_padding(
    page,
    target_width_mm,
    target_height_mm,
    border_color,
    borders_sizes_mm={"top": 0, "bottom": 0, "left": 0, "right": 0},
    overlapping_factor=0,
):
    # Convert target dimensions to points
    target_width_points = mm_to_points(target_width_mm)
    target_height_points = mm_to_points(target_height_mm)

    # Get current page dimensions in points
    current_width_points, current_height_points = get_page_dimensions(page)

    # Calculate scaling factor
    smallest_scaling = get_scaling_to_fit(
        target_width_mm,
        target_height_mm,
        points_to_mm(current_width_points),
        points_to_mm(current_height_points),
    )

    page.scale(smallest_scaling, smallest_scaling)

    # add padding around center to match target size
    page, (border_x, border_y) = expand_page_centric(
        page, target_width_points, target_height_points
    )
    current_width, current_height = get_page_dimensions(page)

    packet = io.BytesIO()

    page_width, page_height = get_page_dimensions(page)
    # Use ReportLab instead of pypdf annotations
    add_border_with_reportlab(
        packet,
        page_width,
        page_height,
        border_x,
        border_y,
        borders_sizes_mm,
        border_color,
        overlapping_factor,
    )

    # Read the temporary PDF and merge with original
    border_reader = PdfReader(packet)
    border_page = border_reader.pages[0]

    # Merge the border page with the original page
    page.merge_page(border_page)
    return page


def crop_and_scale_page(
    page,
    target_width_mm,
    target_height_mm,
    enable_rotation=False,
    crop_to_fill=None,
    border_color=(1, 1, 1),
):
    """Crop and scale a PDF page to target dimensions using modular approach

    Args:
        page: PDF page object to process
        target_width_mm: Target width in millimeters
        target_height_mm: Target height in millimeters
        enable_rotation: Whether to enable automatic rotation for better fit
        crop_to_fill: If True (default), crop content to fill entire area without borders.
                     If False, fit content within area and add colored borders if needed.
        border_color: RGB color tuple for border when crop_to_fill=False (default: white)
    """
    target_width = mm_to_points(target_width_mm)
    target_height = mm_to_points(target_height_mm)

    print(f"Target size: {target_width_mm}x{target_height_mm}mm")
    current_height = page.mediabox.height
    current_width = page.mediabox.width
    print(
        f"Current page size: {points_to_mm(page.mediabox.width):.1f}x{points_to_mm(page.mediabox.height):.1f}mm"
    )

    # Step 1: Rotate page if beneficial
    if False:
        page, rotated, current_width2, current_height2 = rotate_page_for_optimal_fit(
            page, target_width, target_height, enable_rotation
        )

    if enable_rotation and should_rotate(
        current_width, current_height, target_width, target_height
    ):
        target_height, target_width = target_width, target_height
        page = page.rotate(90)  # TODO ask if nescessary

    # safe page to file

    # generate a random path for a temp file
    temp_pdf_buffer = io.BytesIO()
    temp_writer = PdfWriter()
    temp_writer.add_page(page)
    temp_writer.write(temp_pdf_buffer)
    temp_pdf_buffer.seek(0)

    # Write buffer to temporary file for fitz (PyMuPDF) compatibility # TODO requires fix later...
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_file.write(temp_pdf_buffer.getvalue())
        temp_pdf_path = temp_file.name

    results = detect_pdf_border(temp_pdf_path, tolerance=10, dpi=150, skip=3)

    os.remove(temp_pdf_path)

    #

    if results:

        scaled_borders = scaled_borders_to_target_size(
            target_width_mm, target_height_mm, results
        )
        print("Scaled border Size:", scaled_borders)
        min_border_size = get_min_border_size(scaled_borders)
        if min_border_size >= 3.0:
            # add coloured padding
            print(
                f"Significant border detected (min {min_border_size:.1f}mm). Consider printing without cropping."
            )

            # todo write a function, that scales the pdf to smalest target size

            smallest_scaling = get_scaling_to_fit_results(
                target_width_mm, target_height_mm, results
            )
            print(f"Scaling page by {smallest_scaling:.3f} to fit target size")
            # page.scale(smallest_scaling, smallest_scaling)
            non_uniform_scaling = False
            if non_uniform_scaling:
                # todo dosnt work well.
                # throw not implemented message
                raise NotImplementedError("Non-uniform scaling not implemented")
                page.scale(
                    target_width_mm / results["page_size_mm"][0],
                    target_height_mm / results["page_size_mm"][1],
                )
            else:
                get_page_dimensions_in_mm(page)

                page = scale_page_with_padding(
                    page,
                    target_width_mm,
                    target_height_mm,
                    results["border_color"],
                    results["border_sizes_mm"],
                    overlapping_factor=0.5,
                )
                return page

            # todo increas pdf

            # scale page up
            scale_factor, scaled_width, scaled_height = scale_page_to_fit(
                page, current_width, current_height, target_width, target_height, False
            )
            # add borders in right color
            # todo add skip area to border
            # return page
            print("####################### still used##########################")
            newPage = add_border_to_page(
                page,
                scaled_width,
                scaled_height,
                target_width,
                target_height,
                # results["border_color"],
            )
            return newPage

        else:
            print("No significant border detected.")

    # todo: scale page to fit A6 and add borders if needed. Also override the skip area with the boarder.

    # detect_pdf_border(page, border_sizes_A6_mm)

    # if no boarder detected, skale to A6+ and crop.

    # Step 2: Scale page to fit or overfill
    scale_factor, scaled_width, scaled_height = scale_page_to_fit(
        page, current_width, current_height, target_width, target_height, crop_to_fill
    )

    # Step 3 & 4: Either crop or add borders based on mode
    if crop_to_fill:
        crop_page_to_target(
            page, scaled_width, scaled_height, target_width, target_height
        )
    else:

        add_border_to_page(
            page=page,
            scaled_width=scaled_width,
            scaled_height=scaled_height,
            target_width=target_width,
            target_height=target_height,
            border_color=border_color,
        )

    print(f"Final page size: {target_width_mm}x{target_height_mm}mm")

    return page


def process_pdf(
    input_path,
    output_path,
    target_width_mm=148,
    target_height_mm=105,
    enable_rotation=False,
    crop_to_fill=None,
    border_color=(1, 1, 1),
):
    """Process PDF file and crop/scale all pages

    Args:
        input_path: Path to input PDF file
        output_path: Path to output PDF file
        target_width_mm: Target width in millimeters
        target_height_mm: Target height in millimeters
        enable_rotation: Whether to enable automatic rotation for better fit
        crop_to_fill: TODO If True (default), crop content to fill area. If False, add borders.
        border_color: RGB color tuple for border when crop_to_fill=False (default: white)
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
                    border_color,
                )
                # processed_page.rotate(90)
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
        # print stacktrace
        import traceback

        traceback.print_exc()
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


def test_scaling():
    from millimeter_paper_generator import create_test_pdf

    pdf_path = create_test_pdf(100, 100, border_width_mm=6.0, border_color=(0, 1, 0))
    print(pdf_path)
    # result = detect_pdf_border(pdf_path, tolerance=20)
    # crop_and_scale_page(pdf_path, target_width=80, target_height=80, border_color=
    # convert to a6+

    if True:
        process_pdf(
            input_path=pdf_path,
            output_path="test_output_scaling.pdf",
            target_width_mm=148 + 3,
            target_height_mm=105 + 3,
            crop_to_fill=False,
            enable_rotation=True,
            # border_color=(black),
        )
    else:
        process_pdf(
            input_path=pdf_path,
            output_path="test_output_scaling.pdf",
            target_width_mm=105 + 3,
            target_height_mm=148 + 3,
            crop_to_fill=False,
            enable_rotation=False,
            # border_color=(black),
        )


if __name__ == "__main__":
    test_scaling()
    # main()
