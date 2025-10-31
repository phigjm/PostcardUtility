"""
Text fitting and font sizing utilities for postcard generation.
Handles optimal font size calculation, text wrapping, and truncation.
"""

import logging
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from .text_processing import prepare_text_with_language_fonts
from .language_support import contains_arabic, contains_cjk, get_font_for_text

_LOGGER = logging.getLogger(__name__)

# Constants
MIN_FONT_SIZE = 5
DEFAULT_FONT_SIZE = 12
EARLY_CHECK_THRESHOLD = 1.5  # Skip optimization if estimated height > threshold * available height


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


def estimate_if_text_fits(message, max_width, available_height, font_name):
    """
    Quickly estimate if message can possibly fit at minimum font size.

    :param message: Text message to estimate
    :param max_width: Maximum width available
    :param available_height: Maximum height available
    :param font_name: Font name for metrics
    :return: None (needs full check), True (likely fits), or False (definitely won't fit)
    """
    estimated_chars_per_line = int(max_width / (MIN_FONT_SIZE * 0.5))
    estimated_line_height = get_font_line_height(font_name, MIN_FONT_SIZE)
    estimated_lines = max(
        len(message) / max(estimated_chars_per_line, 1), len(message.splitlines())
    )
    estimated_min_height = estimated_lines * estimated_line_height

    if estimated_min_height > available_height * EARLY_CHECK_THRESHOLD:
        _LOGGER.warning(
            f"Message is extremely long ({len(message)} chars, ~{int(estimated_lines)} lines). "
            f"Skipping optimization and using minimum font size directly."
        )
        return False
    return None


def find_optimal_font_size_for_paragraph(
    message,
    max_width,
    available_height,
    font_name,
    min_font_size=MIN_FONT_SIZE,
    max_font_size=DEFAULT_FONT_SIZE,
    alignment=TA_LEFT,
    enable_emoji=True,
):
    """
    Find optimal font size using binary search for Paragraph-based rendering.

    :param message: Text message
    :param max_width: Maximum width
    :param available_height: Maximum height
    :param font_name: Font name
    :param min_font_size: Minimum font size to try
    :param max_font_size: Maximum font size to try
    :param alignment: Text alignment (TA_LEFT or TA_RIGHT)
    :param enable_emoji: Enable emoji support
    :return: (best_font_size, text_fits_completely, final_paragraph)
    """
    style = ParagraphStyle(
        "MessageStyle",
        fontName=font_name,
        fontSize=max_font_size,
        leading=get_font_line_height(font_name, max_font_size),
        alignment=alignment,
        leftIndent=0,
        rightIndent=0,
        spaceBefore=0,
        spaceAfter=0,
    )

    best_fitting_size = min_font_size
    text_fits = False
    search_min = min_font_size
    search_max = max_font_size
    final_para = None

    while search_min <= search_max:
        test_font_size = (search_min + search_max) // 2
        style.fontSize = test_font_size
        style.leading = get_font_line_height(font_name, test_font_size)

        processed_message = prepare_text_with_language_fonts(
            message, enable_emoji, test_font_size
        )

        para = Paragraph(processed_message, style)
        w, h = para.wrap(max_width, available_height)

        if h <= available_height:
            best_fitting_size = test_font_size
            text_fits = True
            final_para = para
            search_min = test_font_size + 1
        else:
            search_max = test_font_size - 1

    return best_fitting_size, text_fits, final_para


def find_optimal_font_size_for_text(
    message,
    max_width,
    available_height,
    canvas_obj,
    font_name,
    min_font_size=MIN_FONT_SIZE,
    max_font_size=DEFAULT_FONT_SIZE,
):
    """
    Find optimal font size using binary search for text-based rendering.

    :param message: Text message
    :param max_width: Maximum width
    :param available_height: Maximum height
    :param canvas_obj: Canvas object for text measurement
    :param font_name: Font name
    :param min_font_size: Minimum font size to try
    :param max_font_size: Maximum font size to try
    :return: (best_font_size, wrapped_lines)
    """
    lines = message.splitlines()
    best_fitting_size = min_font_size
    best_wrapped_lines = []
    search_min = min_font_size
    search_max = max_font_size

    while search_min <= search_max:
        test_font_size = (search_min + search_max) // 2
        canvas_obj.setFont(font_name, test_font_size)
        test_wrapped_lines = []

        for line in lines:
            if line.strip():
                # Get appropriate font for this line
                line_font = get_font_for_text(line, font_name)
                test_wrapped_lines.extend(
                    wrap_text_to_width(
                        line, max_width, canvas_obj, line_font, test_font_size
                    )
                )
            else:
                test_wrapped_lines.append("")

        line_height = get_font_line_height(font_name, test_font_size)
        total_text_height = len(test_wrapped_lines) * line_height

        if total_text_height < available_height:
            best_fitting_size = test_font_size
            best_wrapped_lines = test_wrapped_lines
            search_min = test_font_size + 1
        else:
            search_max = test_font_size - 1

    return best_fitting_size, best_wrapped_lines


def truncate_paragraph_to_fit(
    message, max_width, available_height, font_name, font_size, style, enable_emoji=True
):
    """
    Truncate message to fit available space using binary search.

    :param message: Text message to truncate
    :param max_width: Maximum width
    :param available_height: Maximum height
    :param font_name: Font name
    :param font_size: Font size to use
    :param style: ParagraphStyle to use
    :param enable_emoji: Enable emoji support
    :return: (truncated_paragraph, lines_used, total_lines)
    """
    style.fontSize = font_size
    style.leading = get_font_line_height(font_name, font_size)

    message_lines = message.splitlines()
    max_lines = len(message_lines)
    min_lines = 1
    best_fit_lines = 1

    while min_lines <= max_lines:
        mid_lines = (min_lines + max_lines) // 2
        truncated_message = "\n".join(message_lines[:mid_lines])

        processed_message = prepare_text_with_language_fonts(
            truncated_message, enable_emoji, font_size
        )

        para = Paragraph(processed_message, style)
        w, h = para.wrap(max_width, available_height)

        if h <= available_height:
            best_fit_lines = mid_lines
            min_lines = mid_lines + 1
        else:
            max_lines = mid_lines - 1

    # Create final truncated paragraph
    if best_fit_lines < len(message_lines):
        truncated_message = "\n".join(message_lines[:best_fit_lines])
        if best_fit_lines > 0:
            truncated_message += "\n[...]"
    else:
        truncated_message = message

    processed_message = prepare_text_with_language_fonts(
        truncated_message, enable_emoji, font_size
    )
    para = Paragraph(processed_message, style)

    return para, best_fit_lines, len(message_lines)
