from reportlab.lib.pagesizes import A6, A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from PIL import Image
import os
import tempfile
from pypdf import PdfReader, PdfWriter
from typing import List, Union, Literal, Optional
import io



# Try relative import first (when used as module), fall back to direct import (when run standalone)
try:
    from .postcard_generate_text_side import generate_back_side, set_emoji_cache_dir
    from .postprocessor import format_pdf_for_postcard
    from . import postcardformats
except ImportError:
    from postcard_generate_text_side import generate_back_side, set_emoji_cache_dir
    from postprocessor import format_pdf_for_postcard
    import postcardformats


def register_font(font_path):
    """
    Register a font and return the font name to use.

    :param font_path: Path to TTF/OTF font file or name of built-in font
    :return: Font name string
    """
    if font_path.endswith((".ttf", ".otf")):
        try:
            # Check if font file exists
            if not os.path.exists(font_path):
                print(f"WARNING: Font file not found: {font_path}")
                print("Available built-in fonts: Helvetica, Times-Roman, Courier")
                font_name = "Helvetica"  # Fallback to built-in font
            else:
                # Derive font name from filename (without extension)
                font_base_name = os.path.splitext(os.path.basename(font_path))[0]
                pdfmetrics.registerFont(TTFont(font_base_name, font_path))
                font_name = font_base_name
                print(f"Successfully loaded font: {font_path} as '{font_name}'")
        except Exception as e:
            print(f"ERROR loading font {font_path}: {e}")
            print("Falling back to Helvetica")
            font_name = "Helvetica"
    else:
        # Assume it's a built-in font name
        font_name = font_path

    return font_name


def _draw_image_on_canvas(
    c,
    image_path,
    page_size,
    border_thickness=5,
    auto_rotate_image=True,
    compression_quality=85,
):
    """
    Internal helper: Draw an image on an existing canvas.

    :param c: ReportLab canvas object
    :param image_path: Path to the front image
    :param page_size: Page size tuple (width, height)
    :param border_thickness: Border size in points (default=5)
    :param auto_rotate_image: Automatically rotate portrait images to landscape (default=True)
    :param compression_quality: JPEG quality for non-JPEG images (1-100, default=85)
    """
    width, height = page_size

    # Load image metadata to check dimensions and format
    img = Image.open(image_path)
    img_format = img.format
    needs_processing = False

    # Check if rotation is needed
    if auto_rotate_image and img.height > img.width:
        needs_processing = True

    # Check if cropping is needed
    img_ratio = img.width / img.height
    page_ratio = width / height
    if abs(img_ratio - page_ratio) > 0.01:  # Tolerance for aspect ratio difference
        needs_processing = True

    # If image is JPEG and doesn't need processing, use it directly
    if img_format == "JPEG" and not needs_processing:
        # Direct JPEG embedding - keeps compression!
        c.drawImage(
            image_path,
            border_thickness,
            border_thickness,
            width - 2 * border_thickness,
            height - 2 * border_thickness,
            preserveAspectRatio=True,
            anchor="c",
        )
    else:
        # Image needs processing (rotate, crop, or format conversion)

        # Automatically rotate to landscape if image is in portrait
        if auto_rotate_image and img.height > img.width:
            img = img.rotate(90, expand=True)
            img_ratio = img.width / img.height

        # Crop to match aspect ratio
        if img_ratio > page_ratio:
            new_width = int(img.height * page_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        else:
            new_height = int(img.width / page_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))

        # Save processed image as compressed JPEG to temp file
        temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        temp_img.close()

        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if img.mode in ("RGBA", "LA", "P"):
            # Create white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(
                img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
            )
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Save with compression
        img.save(temp_img.name, "JPEG", quality=compression_quality, optimize=True)

        # Draw compressed image
        c.drawImage(
            temp_img.name,
            border_thickness,
            border_thickness,
            width - 2 * border_thickness,
            height - 2 * border_thickness,
        )

        # Clean up temp file
        os.unlink(temp_img.name)

    # Draw white border
    if border_thickness > 0:
        c.setLineWidth(border_thickness)
        c.setStrokeColorRGB(1, 1, 1)  # white border
        c.rect(
            border_thickness / 2,
            border_thickness / 2,
            width - border_thickness,
            height - border_thickness,
        )


def generate_front_side_image(
    image_path,
    output_file,
    page_size=landscape(A4),
    border_thickness=5,
    auto_rotate_image=True,
    compression_quality=85,
):
    """
    Generate the front side (image side) as a standalone PDF.

    :param image_path: Path to the front image
    :param output_file: Output PDF filename
    :param page_size: Page size tuple (width, height)
    :param border_thickness: Border size in points (default=5)
    :param auto_rotate_image: Automatically rotate portrait images to landscape (default=True)
    :param compression_quality: JPEG quality for non-JPEG images (1-100, default=85)
    :return: Path to generated PDF
    """
    c = canvas.Canvas(output_file, pagesize=page_size, compress=True)
    _draw_image_on_canvas(
        c=c,
        image_path=image_path,
        page_size=page_size,
        border_thickness=border_thickness,
        auto_rotate_image=auto_rotate_image,
        compression_quality=compression_quality,
    )
    c.save()
    return output_file


def generate_front_side_pdf(
    image_path,
    output_file,
    page_size=landscape(A4),
):
    """
    Generate front side from existing PDF (just copies first page).

    :param image_path: Path to the front PDF
    :param output_file: Output PDF filename
    :param page_size: Page size tuple (width, height)
    :return: Path to generated PDF
    """
    pdf_writer = PdfWriter()
    with open(image_path, "rb") as pdf_file:
        pdf_reader = PdfReader(pdf_file)
        pdf_writer.add_page(pdf_reader.pages[0])

    with open(output_file, "wb") as output_pdf_file:
        pdf_writer.write(output_pdf_file)

    return output_file


def generate_back_side_pdf(
    message,
    address,
    output_file,
    font_path=r"C:\Users\Gabri\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
    page_size=landscape(A4),
    show_debug_lines=False,
    message_area_ratio=0.5,
    enable_emoji=True,
    text_color="black",
    url=None,
    warnings=None,
    category=None,
    sender_text="",
):
    """
    Generate the back side (text side) as a standalone PDF.

    :param message: Text message for back
    :param address: Address string (multiline)
    :param output_file: Output PDF filename
    :param font_path: Path to TTF/OTF font file or name of built-in font
    :param page_size: Page size tuple (default=A4 landscape)
    :param show_debug_lines: Whether to show debugging boundary lines (default=False)
    :param message_area_ratio: Ratio of message area width (default=0.5 for 50%)
    :param enable_emoji: Enable colored emoji support (default=True)
    :param text_color: Text color for message and address (default='black')
    :param url: Optional URL to display as QR code in bottom right corner (default=None)
    :param warnings: Optional dict to collect warnings
    :return: Path to generated PDF
    """
    if warnings is None:
        warnings = {}
    font_name = register_font(font_path)
    c = canvas.Canvas(output_file, pagesize=page_size, compress=True)
    generate_back_side(
        c=c,
        message=message,
        address=address,
        font_name=font_name,
        page_size=page_size,
        show_debug_lines=show_debug_lines,
        message_area_ratio=message_area_ratio,
        enable_emoji=enable_emoji,
        text_color=text_color,
        url=url,
        warnings=warnings,
        category=category,
        sender_text=sender_text,
    )
    c.save()
    return output_file


def generate_postcard(
    image_path,
    message,
    address,
    output_file="postcard.pdf",
    font_path=r"C:\Users\gjm\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
    page_size=landscape(A4),
    border_thickness=5,
    show_debug_lines=False,
    message_area_ratio=0.5,
    auto_rotate_image=True,
    compression_quality=85,
    enable_emoji=True,
    text_color="black",
    url=None,
    warnings=None,
    category=None,
    sender_text="",
    skip_bleed_border=False,
):
    """
    Generate a complete postcard PDF with front (image/PDF) and back (text) sides.

    :param image_path: Path to the front image or PDF file
    :param message: Text message for back
    :param address: Address string (multiline)
    :param output_file: Output PDF filename
    :param font_path: Path to TTF/OTF font file or name of built-in font
    :param page_size: Page size tuple (default=A4 landscape)
    :param border_thickness: Border size in points (default=5)
    :param show_debug_lines: Whether to show debugging boundary lines (default=False)
    :param message_area_ratio: Ratio of message area width (default=0.5 for 50%)
    :param auto_rotate_image: Automatically rotate portrait images to landscape (default=True)
    :param compression_quality: JPEG quality for non-JPEG images (1-100, default=85)
    :param enable_emoji: Enable colored emoji support (default=True)
    :param text_color: Text color for message and address (default='black')
    :param url: Optional URL to display as QR code in bottom right corner (default=None)
    :param warnings: Optional dict to collect warnings
    :param skip_bleed_border: If True, skip adding bleed border (use when frontend already has bleed area, default=True)
    """
    if warnings is None:
        warnings = {}
    width, height = page_size

    # Set up emoji cache directory if emoji support is enabled
    if enable_emoji:
        emoji_cache_dir = os.path.join(os.path.dirname(__file__), ".emoji_cache")
        set_emoji_cache_dir(emoji_cache_dir)

    # Check if input is a PDF or an image
    is_pdf_input = image_path.lower().endswith(".pdf")

    processed_image_path = image_path
    if is_pdf_input:
        temp_formatted = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_formatted.close()
        format_pdf_for_postcard(image_path, temp_formatted.name)
        processed_image_path = temp_formatted.name

    if is_pdf_input:
        # PDF input: use existing PDF and overlay text annotations
        font_name = register_font(font_path)

        # Check if PDF has multiple pages
        front_pdf_file = open(processed_image_path, "rb")
        try:
            pdf_reader = PdfReader(front_pdf_file)
            num_pages = len(pdf_reader.pages)
            has_second_page = num_pages >= 2
            
            # Keep references to pages before closing
            front_page_ref = pdf_reader.pages[0]
            back_page_ref = pdf_reader.pages[1] if has_second_page else None
        finally:
            # Don't close yet - we'll do it after we finish processing
            pass

        # Create temporary file for text overlay
        temp_text_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_text_pdf.close()

        # Generate text overlay (with compression)
        c = canvas.Canvas(temp_text_pdf.name, pagesize=page_size, compress=True)
        generate_back_side(
            c=c,
            message=message,
            address=address,
            font_name=font_name,
            page_size=page_size,
            show_debug_lines=show_debug_lines,
            message_area_ratio=message_area_ratio,
            enable_emoji=enable_emoji,
            text_color=text_color,
            url=url,
            warnings=warnings,
            category=category,
            sender_text=sender_text,
        )
        c.save()

        # Merge pages
        pdf_writer = PdfWriter()

        # Add the front side from input PDF (first page only)
        pdf_writer.add_page(front_page_ref)

        # Add the back side with text overlay
        if has_second_page:
            # If PDF has second page, use it and overlay text annotations on top
            text_pdf_file = open(temp_text_pdf.name, "rb")
            try:
                text_reader = PdfReader(text_pdf_file)
                text_overlay = text_reader.pages[0]

                # Merge: overlay text on the existing back page
                back_page_ref.merge_page(text_overlay)
                pdf_writer.add_page(back_page_ref)
            finally:
                text_pdf_file.close()
        else:
            # If only one page, just add the generated text side
            text_pdf_file = open(temp_text_pdf.name, "rb")
            try:
                text_reader = PdfReader(text_pdf_file)
                pdf_writer.add_page(text_reader.pages[0])
            finally:
                text_pdf_file.close()

        # Write the merged PDF
        with open(output_file, "wb") as output_pdf_file:
            pdf_writer.write(output_pdf_file)

        # Clean up resources
        front_pdf_file.close()
        if is_pdf_input:
            os.unlink(processed_image_path)
        os.unlink(temp_text_pdf.name)

        if has_second_page:
            print(f"Postcard generated successfully (using existing back page with text overlay): {output_file}")
        else:
            print(f"Postcard generated successfully (PDF merged): {output_file}")

    else:
        # Image input: generate both sides
        font_name = register_font(font_path)
        
        front_side_page_size = page_size

        if( skip_bleed_border ):
            size = postcardformats.get_default_postcard_size_with_bleeding()
            front_side_page_size = (size[0]*mm, size[1]*mm)
            print("Skipping bleed border, using size:", front_side_page_size, "and aspect ratio:", front_side_page_size[0]/front_side_page_size[1])

        # Create canvas with compression enabled
        c = canvas.Canvas(output_file, pagesize=front_side_page_size, compress=True)

        # --- FRONT SIDE ---
        _draw_image_on_canvas(
            c=c,
            image_path=image_path,
            page_size=front_side_page_size,
            border_thickness=border_thickness,
            auto_rotate_image=auto_rotate_image,
            compression_quality=compression_quality,
        )

        c.showPage()

        # --- BACK SIDE ---
        generate_back_side(
            c=c,
            message=message,
            address=address,
            font_name=font_name,
            page_size=page_size,
            show_debug_lines=show_debug_lines,
            message_area_ratio=message_area_ratio,
            enable_emoji=enable_emoji,
            text_color=text_color,
            url=url,
            warnings=warnings,
            category=category,
            sender_text=sender_text,
        )

        # Save PDF
        c.save()
        print(f"Postcard generated successfully: {output_file}")


def generate_postcard_batch(
    image_path,
    messages_and_addresses: List[dict],
    output_file="postcards_batch.pdf",
    mode: Literal["compact", "joined", "splitted"] = "joined",
    output_directory: Optional[str] = None,
    font_path=r"C:\Users\Gabri\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
    page_size=landscape(A4),
    border_thickness=5,
    show_debug_lines=False,
    message_area_ratio=0.5,
    auto_rotate_image=True,
    compression_quality=85,
    enable_emoji=True,
    text_color="black",
    url=None,
    warnings=None,
    category=None,
    sender_text="",
    skip_bleed_border=False,
):
    """
    Generate multiple postcards in batch mode.

    :param image_path: Path to the front image or PDF file (shared for all postcards)
    :param messages_and_addresses: List of dicts with 'message' and 'address' keys
    :param output_file: Output PDF filename or base name for splitted mode
    :param mode: Generation mode:
        - 'compact': Single PDF with one front side and multiple message sides
        - 'joined': Single PDF with alternating front and back sides (front only generated once)
        - 'splitted': Multiple PDFs, one per postcard
    :param output_directory: Directory for splitted mode (default: same as output_file)
    :param font_path: Path to TTF/OTF font file or name of built-in font
    :param page_size: Page size tuple (default=A4 landscape)
    :param border_thickness: Border size in points (default=5)
    :param show_debug_lines: Whether to show debugging boundary lines (default=False)
    :param message_area_ratio: Ratio of message area width (default=0.5 for 50%)
    :param auto_rotate_image: Automatically rotate portrait images to landscape (default=True)
    :param compression_quality: JPEG quality for non-JPEG images (1-100, default=85)
    :param enable_emoji: Enable colored emoji support (default=True)
    :param text_color: Text color for message and address (default='black')
    :param url: Optional URL to display as QR code in bottom right corner (default=None)
    :param warnings: Optional dict to collect warnings
    :return: List of generated file paths
    """
    if warnings is None:
        warnings = {}
    if not messages_and_addresses:
        raise ValueError("messages_and_addresses list cannot be empty")

    # Set up emoji cache directory if emoji support is enabled
    if enable_emoji:
        emoji_cache_dir = os.path.join(os.path.dirname(__file__), ".emoji_cache")
        set_emoji_cache_dir(emoji_cache_dir)

    # Register font once
    font_name = register_font(font_path)
    is_pdf_input = image_path.lower().endswith(".pdf")

    processed_image_path = image_path
    if is_pdf_input:
        temp_formatted = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_formatted.close()
        format_pdf_for_postcard(image_path, temp_formatted.name)
        processed_image_path = temp_formatted.name

    generated_files = []

    if mode == "compact":
        # Single PDF: one front side + all message sides
        pdf_writer = PdfWriter()

        # Generate and add front side
        temp_front = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_front.close()

        if is_pdf_input:
            with open(processed_image_path, "rb") as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                pdf_writer.add_page(pdf_reader.pages[0])
        else:

            front_side_page_size = page_size

            if( skip_bleed_border ):
                size = postcardformats.get_default_postcard_size_with_bleeding()
                front_side_page_size = (size[0]*mm, size[1]*mm)

            

            c = canvas.Canvas(temp_front.name, pagesize=front_side_page_size, compress=True)
            _draw_image_on_canvas(
                c=c,
                image_path=image_path,
                page_size=front_side_page_size,
                border_thickness=border_thickness,
                auto_rotate_image=auto_rotate_image,
                compression_quality=compression_quality,
            )
            c.save()

            with open(temp_front.name, "rb") as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                pdf_writer.add_page(pdf_reader.pages[0])

        # Generate and add all message sides
        for item in messages_and_addresses:
            message = item.get("message", "")
            address = item.get("address", "")

            temp_back = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_back.close()

            c = canvas.Canvas(temp_back.name, pagesize=page_size, compress=True)
            generate_back_side(
                c=c,
                message=message,
                address=address,
                font_name=font_name,
                page_size=page_size,
                show_debug_lines=show_debug_lines,
                message_area_ratio=message_area_ratio,
                enable_emoji=enable_emoji,
                text_color=text_color,
                url=url,
                warnings=warnings,
                category=category,
                sender_text=sender_text,
            )
            c.save()

            with open(temp_back.name, "rb") as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                pdf_writer.add_page(pdf_reader.pages[0])

            os.unlink(temp_back.name)

        # Write final PDF with compression
        with open(output_file, "wb") as output_pdf:
            pdf_writer.write(output_pdf)

        if not is_pdf_input:
            os.unlink(temp_front.name)

        generated_files.append(output_file)
        print(f"Compact postcard batch generated: {output_file}")

    elif mode == "joined":
        # Single PDF: alternating front and back sides
        # OPTIMIZATION: Keep front page in memory and reuse it for all postcards
        pdf_writer = PdfWriter()

        # Load or generate front side and check for existing back page
        if is_pdf_input:
            # Load from existing PDF - keep file open for duration
            front_pdf_file = open(processed_image_path, "rb")
            front_pdf_reader = PdfReader(front_pdf_file)
            front_page = front_pdf_reader.pages[0]
            
            # Check if PDF has multiple pages (existing back page)
            has_existing_back_page = len(front_pdf_reader.pages) >= 2
            existing_back_page = front_pdf_reader.pages[1] if has_existing_back_page else None
            
            should_close_front = True
            temp_front_name = None
        else:
            # Generate image-based front side
            temp_front = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_front.close()
            
            c = canvas.Canvas(temp_front.name, pagesize=page_size, compress=True)
            _draw_image_on_canvas(
                c=c,
                image_path=image_path,
                page_size=page_size,
                border_thickness=border_thickness,
                auto_rotate_image=auto_rotate_image,
                compression_quality=compression_quality,
            )
            c.save()

            front_pdf_file = open(temp_front.name, "rb")
            front_pdf_reader = PdfReader(front_pdf_file)
            front_page = front_pdf_reader.pages[0]
            
            # No existing back page for image-based input
            has_existing_back_page = False
            existing_back_page = None
            
            should_close_front = True
            temp_front_name = temp_front.name

        try:
            # Add front + back pairs
            for item in messages_and_addresses:
                # Add front side (clone the page so it doesn't depend on the reader)
                pdf_writer.add_page(front_page)

                # Generate and add back side
                message = item.get("message", "")
                address = item.get("address", "")

                temp_back = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                temp_back.close()

                c = canvas.Canvas(temp_back.name, pagesize=page_size, compress=True)
                generate_back_side(
                    c=c,
                    message=message,
                    address=address,
                    font_name=font_name,
                    page_size=page_size,
                    show_debug_lines=show_debug_lines,
                    message_area_ratio=message_area_ratio,
                    enable_emoji=enable_emoji,
                    text_color=text_color,
                    url=url,
                    warnings=warnings,
                    category=category,
                    sender_text=sender_text,
                )
                c.save()

                temp_back_file = open(temp_back.name, "rb")
                try:
                    temp_back_reader = PdfReader(temp_back_file)
                    text_overlay = temp_back_reader.pages[0]

                    if has_existing_back_page:
                        # Overlay text on a fresh copy of the existing back page
                        # Need to read a fresh page from the PDF file to avoid accumulation
                        with open(processed_image_path, "rb") as fresh_pdf:
                            fresh_reader = PdfReader(fresh_pdf)
                            fresh_back_page = fresh_reader.pages[1]
                            fresh_back_page.merge_page(text_overlay)
                            pdf_writer.add_page(fresh_back_page)
                    else:
                        # Use the generated text side directly
                        pdf_writer.add_page(text_overlay)
                finally:
                    temp_back_file.close()

                os.unlink(temp_back.name)

            # Write final PDF with compression
            with open(output_file, "wb") as output_pdf:
                pdf_writer.write(output_pdf)

        finally:
            # Close and cleanup
            if should_close_front:
                front_pdf_file.close()
                if temp_front_name:
                    os.unlink(temp_front_name)

        generated_files.append(output_file)
        print(f"Joined postcard batch generated: {output_file}")

    elif mode == "splitted":
        # Multiple PDFs, one per postcard
        if output_directory is None:
            output_directory = os.path.dirname(output_file) or "."

        base_name = os.path.splitext(os.path.basename(output_file))[0]

        for idx, item in enumerate(messages_and_addresses, 1):
            postcard_file = os.path.join(
                output_directory, f"{base_name}_{idx:03d}.pdf"
            )

            message = item.get("message", "")
            address = item.get("address", "")

            # Generate single postcard
            generate_postcard(
                image_path=image_path,
                message=message,
                address=address,
                output_file=postcard_file,
                font_path=font_path,
                page_size=page_size,
                border_thickness=border_thickness,
                show_debug_lines=show_debug_lines,
                message_area_ratio=message_area_ratio,
                auto_rotate_image=auto_rotate_image,
                compression_quality=compression_quality,
                enable_emoji=enable_emoji,
                text_color=text_color,
                url=url,
                sender_text=sender_text,
            )

            generated_files.append(postcard_file)

        print(f"Splitted postcard batch generated: {len(generated_files)} files")

    else:
        raise ValueError(
            f"Invalid mode: {mode}. Must be 'compact', 'joined', or 'splitted'"
        )

    # Clean up formatted PDF if used
    if is_pdf_input:
        os.unlink(processed_image_path)

    return generated_files


# Example usage
if __name__ == "__main__":
    # ============================================================================
    # EXAMPLE 1: Single postcard generation (original function)
    # ============================================================================
    folder = r"C:\Users\gjm\Projecte\PostCardDjango\media\misc\tmp\test_cards\\"
    folder = r"C:\Users\gjm\Downloads\Test"

    message = """Liebe Alina3,

ich möchte dir von Herzen mein tiefstes Beileid zum Verlust deiner Mama aussprechen."""

    # Using an image as front side
    generate_postcard(
        #image_path=r"C:\Users\gjm\Downloads\dc_grafiktestN.pdf",
        image_path=r"C:\Users\gjm\Downloads\Richa's Both Brands_text.result.pdf",
        page_size=landscape(A6),

        message=message,
        address="John Doe\n123 Main Street\n12345 Hometown\nCountry",
        output_file=folder + "postcard_single.pdf",
        font_path=r"C:\Users\gjm\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
        url="https://example.com",
        category="DE_INT",
        sender_text="Best regards,\nYour Name",
    )

    print("Single postcard generated.")
    x = 1/0

    # ============================================================================
    # EXAMPLE 2: Batch generation - COMPACT mode
    # ============================================================================
    # Single PDF with one front side and multiple message/address pages
    postcards_compact = [
        {
            "message": "Greetings 👋 from the mountains😂!",
            "address": "John Doe 🏠\n123 Main Street ❤️\n12345 Hometown",
        },
        {
            "message": "Wish you were here!",
            "address": "Jane Smith\n456 Oak Avenue\n54321 Cityville",
        },
        {
            "message": "Beautiful weather today!",
            "address": "Bob Wilson\n789 Pine Road\n99999 Smalltown",
        },
    ]

    # kannst du die einträge verfielfältigen für testzwecke
    postcards_compact *= 400


    generate_postcard_batch(
        #image_path=r"C:\Users\Gabri\Downloads\dc_grafiktest (1).pdf",
        image_path=r"C:\Users\gjm\Downloads\Richa's Both Brands_text.result.pdf",
        messages_and_addresses=postcards_compact,
        output_file=folder + "postcards_compact.pdf",
        mode="compact",
        font_path=r"C:\Users\Gabri\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
    )

    # ============================================================================
    # EXAMPLE 3: Batch generation - JOINED mode
    # ============================================================================
    # Single PDF with alternating front (reused) and back sides
    generate_postcard_batch(
        image_path=r"C:\Users\Gabri\Downloads\dc_grafiktest (1).pdf",
        messages_and_addresses=postcards_compact,
        output_file=folder + "postcards_joined.pdf",
        mode="joined",
        font_path=r"C:\Users\Gabri\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
    )

    if(False):
        # ============================================================================
        # EXAMPLE 4: Batch generation - SPLITTED mode
        # ============================================================================
        # Multiple individual PDFs (one per postcard)
        generated_files = generate_postcard_batch(
            image_path=r"C:\Users\Gabri\Downloads\dc_grafiktest (1).pdf",
            messages_and_addresses=postcards_compact,
            output_file=folder + "postcard_batch.pdf",
            mode="splitted",
            output_directory=folder,
            font_path=r"C:\Users\Gabri\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
        )

        print(f"Generated {len(generated_files)} individual postcards")

    # ============================================================================
    # Post-processing (optional)
    # ============================================================================
    # from postprocessor import process_postcard
    # process_postcard(
    #     folder + "postcard_single.pdf",
    #     folder + "print_version.pdf",
    #     folder + "preview_version.pdf",
    # )
