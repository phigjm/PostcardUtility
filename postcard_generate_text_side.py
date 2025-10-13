from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


def get_font_line_height(font_name, font_size):
    """
    Calculate line height based on font-specific metrics.

    :param font_name: Name of the font
    :param font_size: Size of the font in points
    :return: Line height in points
    """
    try:
        font_info = pdfmetrics.getFont(font_name)
        font_ascent = font_info.face.ascent
        font_descent = font_info.face.descent

        # Calculate line height based on actual font metrics with small padding
        actual_font_height = font_ascent - font_descent  # descent is negative
        line_height = actual_font_height * font_size / 1000 + 2  # Add 2pt padding
        return line_height
    except:
        # Fallback to simple calculation if font metrics not available
        return font_size * 1.2  # 120% of font size is a common line height


def wrap_text_to_width(text, max_width, canvas_obj, font_name, font_size):
    """
    Wrap text to fit within max_width using actual character measurements.

    :param text: Text to wrap
    :param max_width: Maximum width in points
    :param canvas_obj: ReportLab canvas object for text measurement
    :param font_name: Font name
    :param font_size: Font size
    :return: List of wrapped lines
    """
    words = text.split()
    if not words:
        return [""]

    lines = []
    current_line = []

    def break_long_word(word, max_width):
        """Break a long word into parts that fit the width."""
        if canvas_obj.stringWidth(word, font_name, font_size) <= max_width:
            return [word]

        broken_parts = []
        current_part = ""

        for i, char in enumerate(word):
            test_part = current_part + char

            # Check if we need to add a hyphen (except for the last character)
            is_last_char = i == len(word) - 1
            if not is_last_char:
                test_width = canvas_obj.stringWidth(
                    test_part + "-", font_name, font_size
                )
            else:
                test_width = canvas_obj.stringWidth(test_part, font_name, font_size)

            if test_width <= max_width:
                current_part = test_part
            else:
                # Current part is full, finalize it
                if current_part:
                    # Add hyphen if this isn't the last part and part has more than 1 character
                    if not is_last_char and len(current_part) > 1:
                        broken_parts.append(current_part + "-")
                    else:
                        broken_parts.append(current_part)
                    current_part = char
                else:
                    # Single character exceeds width - force it anyway
                    broken_parts.append(char)
                    current_part = ""

        # Add the final part
        if current_part:
            broken_parts.append(current_part)

        return broken_parts

    for word in words:
        # Test if adding this word would exceed the width
        test_line = " ".join(current_line + [word])
        test_width = canvas_obj.stringWidth(test_line, font_name, font_size)

        if test_width <= max_width:
            current_line.append(word)
        else:
            # If current line has words, finalize it
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []

            # Check if the word itself is too long
            if canvas_obj.stringWidth(word, font_name, font_size) > max_width:
                # Break the long word
                broken_parts = break_long_word(word, max_width)

                # Add all but the last part as complete lines
                for part in broken_parts[:-1]:
                    lines.append(part)

                # The last part becomes the start of the next line
                if broken_parts:
                    current_line = [broken_parts[-1]]
            else:
                current_line = [word]

    # Add the last line if it has content
    if current_line:
        lines.append(" ".join(current_line))

    return lines


def generate_back_side(
    c,
    message,
    address,
    font_name,
    page_size,
    show_debug_lines=False,
    message_area_ratio=0.5,
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
    """
    width, height = page_size
    margin = 10 * mm

    # Message (left area)
    divider_x = width * message_area_ratio
    max_width = divider_x - 2 * margin
    font_size = 12

    # Auto-shrink font size and line wrapping using actual character widths
    hight_margin = 1 * margin

    lines = message.splitlines()
    wrapped_lines = []
    while font_size > 6:
        c.setFont(font_name, font_size)
        wrapped_lines = []
        for line in lines:
            if line.strip():
                wrapped_lines.extend(
                    wrap_text_to_width(line, max_width, c, font_name, font_size)
                )
            else:
                wrapped_lines.append("")

        # Calculate total height needed using font-specific metrics
        line_height = get_font_line_height(font_name, font_size)
        total_text_height = len(wrapped_lines) * line_height

        if total_text_height < height - hight_margin:
            break
        font_size -= 1

    # Recalculate line height for final font size
    c.setFont(font_name, font_size)
    final_line_height = get_font_line_height(font_name, font_size)

    if len(wrapped_lines) * final_line_height >= height - hight_margin:
        print("WARNING: Message too long to fit on postcard.")
        # Trim lines that overflow
        max_lines = int((height - hight_margin) / final_line_height)
        wrapped_lines = wrapped_lines[:max_lines]

    # Draw message text
    text_obj = c.beginText(margin, height - margin - font_size)
    text_obj.setFont(font_name, font_size)
    text_obj.setLeading(final_line_height)  # Set line spacing to calculated line height
    for line in wrapped_lines:
        text_obj.textLine(line)
    c.drawText(text_obj)

    # --- DEBUG: Draw boundary lines (optional) ---
    if show_debug_lines:
        c.setStrokeColorRGB(1, 0, 0)  # Red color for debug lines
        c.setLineWidth(0.5)

        # Draw margin boundaries
        c.rect(margin, margin, width - 2 * margin, height - 2 * margin)

        # Draw text area boundary (left area)
        text_area_width = max_width
        text_area_height = height - hight_margin
        c.rect(margin, margin, text_area_width, text_area_height)

        # Draw max width line for text (right boundary of message area)
        c.line(margin + max_width, margin, margin + max_width, height - margin)

        # Draw Divider line (center strip)
        c.setStrokeColorRGB(0, 0, 1)  # Blue for divider
        c.line(divider_x, margin, divider_x, height - margin)
        c.setStrokeColorRGB(1, 0, 0)  # Back to red for other debug lines

        # Draw height margin line
        c.line(margin, height - hight_margin, divider_x, height - hight_margin)

        # Label the boundaries
        c.setFont(font_name, 6)
        c.setFillColorRGB(1, 0, 0)  # Red text
        c.drawString(margin + 2, height - margin - 8, f"Margin: {margin/mm:.1f}mm")
        c.drawString(
            margin + max_width + 2,
            height - margin - 8,
            f"MaxWidth: {max_width/mm:.1f}mm",
        )
        c.drawString(
            margin + 2,
            height - hight_margin + 2,
            f"HeightMargin: {hight_margin/mm:.1f}mm",
        )
        c.drawString(margin + 2, margin + 2, f"FontSize: {font_size}pt")
        c.drawString(margin + 2, margin + 12, f"LineHeight: {final_line_height:.1f}pt")
        c.drawString(
            divider_x + 2, height - margin - 8, f"DividerX: {divider_x/mm:.1f}mm"
        )

        # Reset colors
        c.setStrokeColorRGB(0, 0, 0)  # Black
        c.setFillColorRGB(0, 0, 0)  # Black

    # Address (right area)
    addr_x = divider_x + margin
    c.setFont(font_name, 12)

    # Calculate starting position for address (top-down)
    address_lines = address.splitlines()
    line_height = 14
    total_address_height = len(address_lines) * line_height
    addr_y = margin + 40 + total_address_height  # start from top of address block

    for line in address_lines:
        c.drawString(addr_x, addr_y, line)
        addr_y -= line_height  # move down for next line

    # Stamp box (top right)
    stamp_size_x = 20 * mm
    stamp_size_y = 27 * mm
    c.rect(
        width - margin - stamp_size_x,
        height - margin - stamp_size_y,
        stamp_size_x,
        stamp_size_y,
    )
    c.setFont(font_name, 8)
    c.drawCentredString(
        width - margin - stamp_size_x / 2, height - margin - stamp_size_y / 2, "STAMP"
    )

    # URL under stamp (optional)
    c.setFont(font_name, 10)
    if False:  # TODO: add subtext to Stamp
        c.drawRightString(
            width - margin, height - margin - stamp_size_y - 12, "ServiceCard.de"
        )

    # Divider line (center strip)
    c.setStrokeColorRGB(0, 0, 0)  # reset to black
    c.line(divider_x, margin, divider_x, height - margin)
