"""
Postcard text side (back side) generation module.
Main module that orchestrates postcard back side generation using modular components.
"""

from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF
from reportlab.lib.colors import Color
import logging

# Import from modular components in text_rendering package
from text_rendering import (
    set_emoji_cache_dir,
    precache_emojis_in_text,
    contains_arabic,
    contains_cjk,
    get_font_for_text,
    get_color_rgb,
    has_special_rendering_needs,
    prepare_text_with_language_fonts,
    MIN_FONT_SIZE,
    DEFAULT_FONT_SIZE,
    get_font_line_height,
    wrap_text_to_width,
    estimate_if_text_fits,
    find_optimal_font_size_for_paragraph,
    find_optimal_font_size_for_text,
    truncate_paragraph_to_fit,
)

_LOGGER = logging.getLogger(__name__)


def _draw_handwriting_guide_lines(canvas_obj, divider_x, margin, height, width, num_lines=4, line_color=(0.8, 0.8, 0.8)):
    """
    Draw horizontal guide lines for handwriting in the address section.

    :param canvas_obj: ReportLab canvas object
    :param divider_x: X position of divider line
    :param margin: Margin size
    :param height: Page height
    :param width: Page width
    :param num_lines: Number of guide lines to draw (default=4)
    :param line_color: Color of guide lines as RGB tuple (default=(0.8, 0.8, 0.8) - light gray)
    """
    # Set line color (light gray for guide lines)
    canvas_obj.setStrokeColorRGB(*line_color)
    canvas_obj.setLineWidth(0.5)
    
    # Address area starts from divider_x + margin and goes to the right edge - margin
    addr_x_start = divider_x + margin
    addr_x_end = width - margin
    
    # Address area: lines should be at the BOTTOM of the page
    # Y coordinates: 0 is at bottom, height is at top
    # So small Y values = bottom of page
    # Start from bottom margin and go upward
    addr_y_start = margin + 10   # Start at bottom margin
    addr_y_end = addr_y_start + 120   # Extend upward 120mm from bottom margin
    
    # Calculate spacing between lines to distribute them evenly
    available_height = addr_y_end - addr_y_start
    line_spacing = available_height / (num_lines + 1)
    
    # Draw the specified number of horizontal lines
    for i in range(num_lines):
        y = addr_y_start + (i * line_spacing)
        canvas_obj.line(addr_x_start, y, addr_x_end, y)
    
    # Reset line color to black
    canvas_obj.setStrokeColorRGB(0, 0, 0)


def _draw_address_section(
        canvas_obj, address, divider_x, margin, height, font_name, width, enable_emoji=True, text_color="black", warnings=None, sender_text=""
):
    """
    Draw the address section on the right side of the postcard.

    :param canvas_obj: ReportLab canvas object
    :param address: Address text (multiline)
    :param divider_x: X position of divider line
    :param margin: Margin size
    :param height: Page height
    :param font_name: Font name
    :param width: Page width
    :param enable_emoji: Enable colored emoji support (default=True)
    :param text_color: Text color name (default='black')
    :param warnings: Optional dict to collect warnings (e.g., overflow warnings)
    """
    if warnings is None:
        warnings = {}
    # Check if address is an annotation (e.g., "Handwriting", "Handwritten", "Custom")
    # These should not be printed on the postcard, just leave space empty
    # Remove quotes for checking annotations
    cleaned_address = address.replace('"', '').replace("'", '').lower().strip()
    
    # Only treat as annotation if it's exactly "handwriting" after stripping
    is_annotation = cleaned_address == "handwriting"
    
    # If it's just an annotation, draw guide lines for handwriting
    if is_annotation:
        _LOGGER.debug(f"Address is annotation '{address}' - drawing guide lines for handwriting")
        # Draw horizontal guide lines for handwriting
        _draw_handwriting_guide_lines(canvas_obj, divider_x, margin, height, width)
        return
    
    is_clean = cleaned_address == "clean"
    if is_clean:
        _LOGGER.debug(f"Address is clean '{address}' - dont add any address")
        return
    
    # Get RGB color values
    r, g, b = get_color_rgb(text_color)
    
    addr_x = divider_x + margin
    address_font_size = 12

    # Calculate available width for address
    available_width = width - divider_x - 2 * margin

    # Check if address has special rendering needs
    needs_paragraph = has_special_rendering_needs(address, enable_emoji)

    if needs_paragraph:
        # Use Paragraph for emoji and/or Arabic support
        # Use right alignment for Arabic text
        alignment = TA_RIGHT if contains_arabic(address) else TA_LEFT

        style = ParagraphStyle(
            "AddressStyle",
            fontName=font_name,
            fontSize=address_font_size,
            leading=get_font_line_height(font_name, address_font_size),
            alignment=alignment,
            leftIndent=0,
            rightIndent=0,
            spaceBefore=0,
            spaceAfter=0,
            textColor=Color(r, g, b),
        )

        # Process address with proper language and emoji support
        processed_address = prepare_text_with_language_fonts(
            address, enable_emoji, address_font_size, text_color
        )

        para = Paragraph(processed_address, style)

        # Wrap and get height
        w, h = para.wrap(available_width, height)

        # Check for overflow
        if w > available_width:
            _LOGGER.warning(f"Address text overflows available width: {w:.1f}pt > {available_width:.1f}pt")
            warnings['address_overflow'] = {
                'overflow': True,
                'required_width': w,
                'available_width': available_width,
                'mode': 'paragraph'
            }

        # Position address (starting from bottom + 10mm offset to make more room for sender text)
        addr_y = margin + 10

        # Calculate sender text position
        sender_y = addr_y + h + 10  # Position above address, relative to address height

        # Draw using Frame
        frame = Frame(
            addr_x,
            addr_y,
            available_width,
            h,
            leftPadding=0,
            bottomPadding=0,
            rightPadding=0,
            topPadding=0,
            showBoundary=0,
        )
        frame.addFromList([para], canvas_obj)
    else:
        # Traditional text rendering without special needs
        canvas_obj.setFont(font_name, address_font_size)
        canvas_obj.setFillColorRGB(r, g, b)

        address_lines = address.splitlines()
        line_height = 14
        total_address_height = len(address_lines) * line_height
        addr_y = margin + 10 + total_address_height

        # Calculate sender text position
        sender_y = addr_y + 10  # Position above address, relative to address top

        for line in address_lines:
            # Set appropriate font for each line
            line_font = get_font_for_text(line, font_name)
            canvas_obj.setFont(line_font, address_font_size)
            line_width = canvas_obj.stringWidth(line, line_font, address_font_size)
            if line_width > available_width:
                _LOGGER.warning(f"Address line overflows available width: '{line}' ({line_width:.1f}pt > {available_width:.1f}pt)")
                if 'address_overflow' not in warnings:
                    warnings['address_overflow'] = {
                        'overflow': True,
                        'lines': []
                    }
                warnings['address_overflow']['lines'].append({
                    'line': line,
                    'width': line_width,
                    'available_width': available_width
                })
            canvas_obj.drawString(addr_x, addr_y, line)
            addr_y -= line_height

    # Draw sender text above address (after calculating position)
    if sender_text:  # Only draw if not empty
        sender_font_size = 10
        canvas_obj.setFont(font_name, sender_font_size)
        canvas_obj.setFillColorRGB(r, g, b)
        canvas_obj.drawString(addr_x, sender_y, sender_text)


def _draw_stamp_box(canvas_obj, width, height, margin, font_name):
    """
    Draw the stamp box in the top right corner.

    :param canvas_obj: ReportLab canvas object
    :param width: Page width
    :param height: Page height
    :param margin: Margin size
    :param font_name: Font name
    """
    stamp_size_x = 20 * mm
    stamp_size_y = 27 * mm
    canvas_obj.rect(
        width - margin - stamp_size_x,
        height - margin - stamp_size_y,
        stamp_size_x,
        stamp_size_y,
    )
    canvas_obj.setFont(font_name, 8)
    canvas_obj.drawCentredString(
        width - margin - stamp_size_x / 2, height - margin - stamp_size_y / 2, "STAMP"
    )


def _draw_priority_label(canvas_obj, width, height, margin, divider_x, font_name):
    """
    Draw a priority label for international postcards on the right side near the divider line.
    
    :param canvas_obj: ReportLab canvas object
    :param width: Page width
    :param height: Page height
    :param margin: Margin size
    :param divider_x: X position of divider line
    :param font_name: Font name
    """
    label_width = 19 * mm
    label_height = 6 * mm
    distance_to_divider = 2 * mm
    
    # Position on the right side, near the divider line
    label_x = divider_x - label_width/2 + label_height/2 +distance_to_divider# Links rechts
    label_y = height - margin - label_height/2  - label_width/2 # höhe
    
    # Save current state for rotation
    canvas_obj.saveState()
    
    # Translate to label position and rotate 15 degrees
    canvas_obj.translate(label_x + label_width / 2, label_y + label_height / 2)
    canvas_obj.rotate(90)  # Rotate 15 degrees
    
    # Draw rounded rectangle background - complete blue
    blue_rgb = (3/255, 69/255, 147/255)  # RGB(3, 69, 147)
    canvas_obj.setFillColorRGB(*blue_rgb)
    canvas_obj.setStrokeColorRGB(*blue_rgb)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.roundRect(-label_width/2, -label_height/2, label_width, label_height, 2 * mm, fill=1, stroke=1)
    
    # Draw white text
    canvas_obj.setFillColorRGB(1, 1, 1)  # White text
    canvas_obj.setFont(font_name, 7)
    canvas_obj.drawCentredString(0, -2.5, "PRIORITY ✈")
    
    # Restore canvas state
    canvas_obj.restoreState()


def _draw_qr_code_and_url(canvas_obj, url, width, height, margin, divider_x, font_name = "Courier", text_color="black"):
    """
    Draw QR code and rotated URL text on the divider line.
    
    QR code is positioned below the divider line, text is rotated 90° on the divider line 
    and starts (bottom-left) at the bottom of the QR code.

    :param canvas_obj: ReportLab canvas object
    :param url: URL to encode in QR code and display
    :param width: Page width
    :param height: Page height
    :param margin: Margin size
    :param divider_x: X position of divider line
    :param font_name: Font name
    :param text_color: Text color for URL (default='black')
    :return: Y position of the top of the QR code/text element (for divider line positioning)
    """
    # QR code settings - smaller size
    qr_size = 10 * mm  # Size of the QR code (reduced from 15mm)

    # Position QR code centered at bottom, below the divider line
    # Move QR code lower (more margin below)
    qr_x = divider_x - qr_size / 2  # Center on divider line
    qr_y = margin - 7 * mm  # Move down by 3mm from margin
    qr_y_top = qr_y + qr_size
    
    # Create QR code
    qr_code = QrCodeWidget(url+"?q=1") 
    bounds = qr_code.getBounds()
    qr_width = bounds[2] - bounds[0]
    qr_height = bounds[3] - bounds[1]
    
    # Create drawing with proper scaling
    d = Drawing(qr_size, qr_size, transform=[qr_size/qr_width, 0, 0, qr_size/qr_height, 0, 0])
    d.add(qr_code)
    
    # Render QR code on canvas
    renderPDF.draw(d, canvas_obj, qr_x, qr_y)
    
    # Draw rotated URL text on the divider line
    r, g, b = get_color_rgb(text_color)
    canvas_obj.setFillColorRGB(r, g, b)
    
    # Use Courier (monospace font) for URL - this is a standard PDF font
    canvas_obj.setFont("Courier", 5)
    
    # Truncate URL if too long
    display_url = url
    if len(url) > 50:
        # Try to extract domain
        if "://" in url:
            display_url = url.split("://")[1].split("/")[0]
        else:
            display_url = url[:27] + "..."
    
    # Draw URL text rotated 90° on the divider line
    # Text starts (bottom-left) at the bottom of the QR code
    # When rotated 90°, the "left" of the rotated text is at the bottom
    text_x = divider_x + 0.3 * mm  # On the divider line
    text_y = qr_y_top  # At the bottom of QR code
    
    # Save current canvas state
    canvas_obj.saveState()
    
    # Translate to the position and rotate
    canvas_obj.translate(text_x, text_y)
    canvas_obj.rotate(90)
    
    # Draw the rotated text with left alignment (starts at origin, goes up)
    canvas_obj.drawString(0, 0, display_url)
    
    # Calculate the width (which becomes height when rotated 90°) of the displayed URL text
    text_width = canvas_obj.stringWidth(display_url, "Courier", 5)
    
    # Restore canvas state
    canvas_obj.restoreState()
    
    # Return the Y position of the top of the QR code + rotated text length (for divider line positioning)
    # When rotated 90°, the text extends upward, so we add the text width to qr_y_top
    return qr_y_top + text_width+0.5 * mm  # Add small margin


def _draw_debug_lines(
    canvas_obj,
    width,
    height,
    margin,
    divider_x,
    max_width,
    available_height,
    font_size,
    line_height,
    font_name,
):
    """
    Draw debug boundary lines and labels.

    :param canvas_obj: ReportLab canvas object
    :param width: Page width
    :param height: Page height
    :param margin: Margin size
    :param divider_x: X position of divider
    :param max_width: Maximum text width
    :param available_height: Available height for text
    :param font_size: Current font size
    :param line_height: Current line height
    :param font_name: Font name
    """
    top_margin = margin
    bottom_margin = margin

    canvas_obj.setStrokeColorRGB(1, 0, 0)
    canvas_obj.setLineWidth(0.5)

    # Draw margin boundaries
    canvas_obj.rect(margin, margin, width - 2 * margin, height - 2 * margin)

    # Draw text area boundary
    canvas_obj.rect(margin, bottom_margin, max_width, available_height)

    # Draw max width line
    canvas_obj.line(margin + max_width, margin, margin + max_width, height - margin)

    # Draw divider line (blue)
    canvas_obj.setStrokeColorRGB(0, 0, 1)
    canvas_obj.line(divider_x, margin, divider_x, height - margin)
    canvas_obj.setStrokeColorRGB(1, 0, 0)

    # Draw height margin line
    canvas_obj.line(margin, height - top_margin, divider_x, height - top_margin)

    # Labels
    canvas_obj.setFont(font_name, 6)
    canvas_obj.setFillColorRGB(1, 0, 0)
    canvas_obj.drawString(margin + 2, height - margin - 8, f"Margin: {margin/mm:.1f}mm")
    canvas_obj.drawString(
        margin + max_width + 2, height - margin - 8, f"MaxWidth: {max_width/mm:.1f}mm"
    )
    canvas_obj.drawString(
        margin + 2, height - top_margin + 2, f"TopMargin: {top_margin/mm:.1f}mm"
    )
    canvas_obj.drawString(margin + 2, margin + 2, f"FontSize: {font_size}pt")
    canvas_obj.drawString(margin + 2, margin + 12, f"LineHeight: {line_height:.1f}pt")
    canvas_obj.drawString(
        divider_x + 2, height - margin - 8, f"DividerX: {divider_x/mm:.1f}mm"
    )

    # Reset colors
    canvas_obj.setStrokeColorRGB(0, 0, 0)
    canvas_obj.setFillColorRGB(0, 0, 0)


def generate_back_side(
    c,
    message,
    address,
    font_name,
    page_size,
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
    Generate the back side (text side) of a postcard on an existing canvas.

    :param c: ReportLab canvas object
    :param message: Text message for back
    :param address: Address string (multiline)
    :param font_name: Name of the registered font
    :param page_size: Page size tuple (width, height)
    :param show_debug_lines: Whether to show debugging boundary lines (default=False)
    :param message_area_ratio: Ratio of message area width (default=0.5 for 50%)
    :param enable_emoji: Enable colored emoji support (default=True)
    :param text_color: Text color for message and address (default='black')
    :param url: Optional URL to display as QR code in bottom right corner (default=None)
    :param warnings: Optional dict to collect warnings (e.g., truncation warnings)
    :param category: Optional category for special labels (e.g., "DE_INT")
    :param sender_text: Optional sender text to display above the address (default="")
    """
    if warnings is None:
        warnings = {}
    width, height = page_size
    margin = 10 * mm

    print("Text resived ", message)

    # Calculate layout dimensions
    divider_x = width * message_area_ratio
    max_width = divider_x - 2 * margin
    top_margin = margin
    bottom_margin = margin
    available_height = height - top_margin - bottom_margin

    # Check if message has special rendering needs
    needs_paragraph = has_special_rendering_needs(message, enable_emoji)

    # Quick estimation check
    text_fits = estimate_if_text_fits(message, max_width, available_height, font_name)

    # === PARAGRAPH MODE (for emoji, Arabic, and/or CJK text) ===
    if needs_paragraph:
        # Pre-cache all emoji images for performance
        if enable_emoji:
            _LOGGER.debug("Pre-caching emoji images for message")
            precache_emojis_in_text(message)

        # Create base paragraph style with appropriate alignment
        # Use right alignment for Arabic text
        alignment = TA_RIGHT if contains_arabic(message) else TA_LEFT

        style = ParagraphStyle(
            "MessageStyle",
            fontName=font_name,
            fontSize=DEFAULT_FONT_SIZE,
            leading=get_font_line_height(font_name, DEFAULT_FONT_SIZE),
            alignment=alignment,
            leftIndent=0,
            rightIndent=0,
            spaceBefore=0,
            spaceAfter=0,
            textColor=Color(*get_color_rgb(text_color)),
        )

        # Determine font size and create paragraph
        if text_fits is None:
            # Run binary search optimization
            font_size, text_fits, para = find_optimal_font_size_for_paragraph(
                message,
                max_width,
                available_height,
                font_name,
                MIN_FONT_SIZE,
                DEFAULT_FONT_SIZE,
                alignment=alignment,
                enable_emoji=enable_emoji,
                text_color=text_color,
            )
            print(f"[PARAGRAPH MODE] Font size: {font_size}pt, fits: {text_fits}")
        else:
            # Skip optimization, use minimum font size
            font_size = MIN_FONT_SIZE
            para = None
            print(f"[PARAGRAPH MODE] Using minimum font size: {font_size}pt")

        # Handle truncation if text doesn't fit
        if not text_fits:
            _LOGGER.warning(
                f"Message is too long to fit on postcard even at minimum font size {MIN_FONT_SIZE}pt. "
                f"Message will be truncated. Original length: {len(message)} characters."
            )

            para, lines_used, total_lines = truncate_paragraph_to_fit(
                message, max_width, available_height, font_name, MIN_FONT_SIZE, style, enable_emoji, text_color
            )

            if lines_used < total_lines:
                _LOGGER.warning(
                    f"Message truncated to {lines_used} of {total_lines} lines to fit on postcard."
                )
                # Add warning for truncation
                warnings['message_truncated'] = {
                    'truncated': True,
                    'original_lines': total_lines,
                    'truncated_to_lines': lines_used,
                    'mode': 'paragraph'
                }

            font_size = MIN_FONT_SIZE

        # Ensure we have a paragraph to draw
        if para is None:
            style.fontSize = font_size
            # For emoji-heavy text with high line count, reduce leading to save space
            default_leading = get_font_line_height(font_name, font_size)
            line_count = len(message.splitlines())
            if enable_emoji and line_count > 15:
                # Reduce leading by 10% for very tall emoji-heavy messages
                style.leading = default_leading * 0.90
                print(f"[PARAGRAPH MODE] High line count ({line_count}) detected: reducing leading from {default_leading:.2f}pt to {style.leading:.2f}pt")
            else:
                style.leading = default_leading
            print(f"[PARAGRAPH MODE] Creating new paragraph with font_size: {font_size}pt, leading: {style.leading:.2f}pt")
            processed_message = prepare_text_with_language_fonts(
                message, enable_emoji, font_size, text_color
            )
            para = Paragraph(processed_message, style)
        
        # Check paragraph dimensions and fallback if needed
        w, h = para.wrap(max_width, available_height)
        
        if h > available_height:
            print(f"[PARAGRAPH MODE] Text exceeds height: {h:.0f}pt > {available_height:.0f}pt, reducing leading...")
            # Reduce leading by 5% to fit
            style.leading = style.leading * 0.95
            processed_message = prepare_text_with_language_fonts(
                message, enable_emoji, font_size, text_color
            )
            para = Paragraph(processed_message, style)
            w, h = para.wrap(max_width, available_height)
            
            if h > available_height:
                _LOGGER.warning(f"Text still exceeds height by {h - available_height:.0f}pt. Rendering anyway.")
                print(f"[PARAGRAPH MODE] ⚠ Rendering with overflow")

        # Draw the paragraph
        frame = Frame(
            margin,
            bottom_margin,
            max_width,
            available_height,
            leftPadding=0,
            bottomPadding=0,
            rightPadding=0,
            topPadding=0,
            showBoundary=0,
        )
        para.leftIndent = 0
        para.rightIndent = 0
        para.spaceBefore = 0
        para.spaceAfter = 0
        frame.addFromList([para], c)
        final_line_height = style.leading

    # === TEXT MODE (Text-based rendering without special needs) ===
    else:
        if text_fits is None:
            # Run binary search optimization
            font_size, wrapped_lines = find_optimal_font_size_for_text(
                message,
                max_width,
                available_height,
                c,
                font_name,
                MIN_FONT_SIZE,
                DEFAULT_FONT_SIZE,
            )
            print(f"[TEXT MODE] Font size: {font_size}pt, {len(wrapped_lines)} lines")
        else:
            # Skip optimization, use minimum font size
            font_size = MIN_FONT_SIZE
            lines = message.splitlines()
            wrapped_lines = []
            c.setFont(font_name, font_size)
            for line in lines:
                if line.strip():
                    line_font = get_font_for_text(line, font_name)
                    wrapped_lines.extend(
                        wrap_text_to_width(
                            line, max_width, c, line_font, font_size
                        )
                    )
                else:
                    wrapped_lines.append("")
            print(f"[TEXT MODE] Using minimum font size: {font_size}pt, {len(wrapped_lines)} lines")

        # Calculate line height
        c.setFont(font_name, font_size)
        final_line_height = get_font_line_height(font_name, font_size)

        # Truncate if necessary
        if len(wrapped_lines) * final_line_height >= available_height:
            max_lines = int(available_height / final_line_height)
            print(f"[TEXT MODE] Text too long: truncating from {len(wrapped_lines)} to {max_lines} lines")
            original_length = len(wrapped_lines)
            wrapped_lines = wrapped_lines[:max_lines]
            if max_lines > 0:
                wrapped_lines[-1] = wrapped_lines[-1] + " [...]"
                #TODO write ERror message instead of [...]
            
            # Add warning for truncation
            warnings['message_truncated'] = {
                'truncated': True,
                'original_lines': original_length,
                'truncated_to_lines': max_lines,
                'mode': 'text'
            }

        # Draw text
        r, g, b = get_color_rgb(text_color)
        y = height - margin - font_size
        for line in wrapped_lines:
            line_font = get_font_for_text(line, font_name)
            c.setFont(line_font, font_size)
            c.setFillColorRGB(r, g, b)
            c.drawString(margin, y, line)
            y -= final_line_height

    # === DRAW ADDRESS AND STAMP ===
    _draw_address_section(
        c, address, divider_x, margin, height, font_name, width, enable_emoji, text_color, warnings, sender_text
    )
    _draw_stamp_box(c, width, height, margin, font_name)
    
    # === DRAW PRIORITY LABEL FOR INTERNATIONAL POSTCARDS ===
    if category == "DE_INT":
        _draw_priority_label(c, width, height, margin, divider_x, "Helvetica-Bold")

    # === DRAW QR CODE AND URL (if provided) ===
    qr_code_top_y = None
    if url:
        qr_code_top_y = _draw_qr_code_and_url(c, url, width, height, margin, divider_x)

    # === OPTIONAL DEBUG LINES ===
    if show_debug_lines:
        _draw_debug_lines(
            c,
            width,
            height,
            margin,
            divider_x,
            max_width,
            available_height,
            font_size,
            final_line_height,
            font_name,
        )

    # === DRAW DIVIDER LINE ===
    # Calculate the Y position where the text starts (at the top of the text area)
    text_top_y = height - margin
    
    # Use the calculated QR code top position if URL was provided
    if qr_code_top_y is not None:
        text_top_y = qr_code_top_y
    
    c.setStrokeColorRGB(0, 0, 0)
    # Draw divider line from bottom margin to the top of the text area
    c.line(divider_x, text_top_y, divider_x, height - margin)
