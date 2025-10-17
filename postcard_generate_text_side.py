from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
import emoji
import re
import os
import urllib.request
import urllib.error
import logging
from io import BytesIO


# Cache directory for emoji images
EMOJI_CACHE_DIR = None  # Will be set dynamically

# In-memory cache of emoji characters that previously failed to download
_FAILED_EMOJI_DOWNLOADS = set()

# In-memory cache of successfully downloaded emoji paths to avoid repeated file system checks
_EMOJI_PATH_CACHE = {}

_LOGGER = logging.getLogger(__name__)

# Constants
MIN_FONT_SIZE = 5
DEFAULT_FONT_SIZE = 12
EARLY_CHECK_THRESHOLD = (
    1.5  # Skip optimization if estimated height > threshold * available height
)


def _strip_variation_selectors(s):
    """
    Return a string with U+FE0F (variation selector-16) characters removed.
    Twemoji filenames often omit the FE0F codepoint (variation selector),
    so trying the filename without it can avoid 404 errors for characters
    like '❤️' (U+2764 U+FE0F).
    """
    return "".join(ch for ch in s if ord(ch) != 0xFE0F)


def set_emoji_cache_dir(cache_dir):
    """
    Set the directory where emoji images will be cached.

    :param cache_dir: Path to cache directory
    """
    global EMOJI_CACHE_DIR
    EMOJI_CACHE_DIR = cache_dir
    if cache_dir and not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)


def get_emoji_image_path(emoji_char, size=32):
    """
    Get the path to an emoji image, downloading it if necessary.
    Uses Twemoji (Twitter's open source emoji images).

    :param emoji_char: The emoji character
    :param size: Size in pixels (default=32)
    :return: Path to emoji image file or None if failed
    """
    # Check in-memory cache first (fastest)
    if emoji_char in _EMOJI_PATH_CACHE:
        return _EMOJI_PATH_CACHE[emoji_char]

    # Use cache directory or temp
    cache_dir = EMOJI_CACHE_DIR or os.path.join(
        os.path.dirname(__file__), ".emoji_cache"
    )
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)

    # Avoid retrying downloads for emoji we've already seen fail during this
    # process - this reduces repeated 404 warnings (user reported repeated
    # messages for emojis like ❤️).
    if emoji_char in _FAILED_EMOJI_DOWNLOADS:
        return None

    # Prepare a list of candidate emoji strings to try. The first candidate is
    # the original sequence. The second removes variation selectors (FE0F),
    # which Twemoji filenames commonly omit (e.g. U+2764 U+FE0F -> 2764.png).
    candidates = [emoji_char]
    stripped = _strip_variation_selectors(emoji_char)
    if stripped != emoji_char:
        candidates.append(stripped)

    last_error = None
    for candidate in candidates:
        # Get Unicode codepoint(s) for the candidate
        codepoint = "-".join([f"{ord(c):x}" for c in candidate])

        # Check cache before attempting download
        cache_path = os.path.join(cache_dir, f"{codepoint}.png")
        if os.path.exists(cache_path):
            # Store in memory cache for faster future lookups
            _EMOJI_PATH_CACHE[emoji_char] = cache_path
            return cache_path

        # Attempt to download from Twemoji CDN
        url = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{codepoint}.png"
        try:
            urllib.request.urlretrieve(url, cache_path)
            # Store successful download in memory cache
            _EMOJI_PATH_CACHE[emoji_char] = cache_path
            return cache_path
        except urllib.error.HTTPError as e:
            # If Twemoji doesn't have that exact filename we'll often get a
            # 404. Try next candidate instead of immediately failing.
            last_error = e
            if e.code == 404:
                _LOGGER.debug(
                    "Twemoji 404 for %s (candidate %s), trying next candidate",
                    emoji_char,
                    candidate,
                )
                continue
            else:
                _LOGGER.warning(
                    "HTTP error while downloading emoji %s: %s", emoji_char, e
                )
                last_error = e
                break
        except Exception as e:
            # Other errors (network, permission) - log and stop trying further
            _LOGGER.warning("Could not download emoji image for %s: %s", emoji_char, e)
            last_error = e
            break

    # If we reach here we couldn't download any candidate. Record failure to
    # avoid repeated attempts during the same run and emit a single warning.
    _FAILED_EMOJI_DOWNLOADS.add(emoji_char)
    if last_error is not None:
        _LOGGER.warning(
            "Could not download emoji image for %s: %s", emoji_char, last_error
        )
    else:
        _LOGGER.warning(
            "Could not download emoji image for %s: unknown error", emoji_char
        )
    return None


def replace_emojis_with_images(text, font_size):
    """
    Replace emoji characters in text with HTML img tags for colored emoji rendering.

    :param text: Text containing emojis
    :param font_size: Font size to match emoji size
    :return: Text with emojis replaced by <img> tags
    """
    # Get all emojis in the text using the emoji library
    # emoji.emoji_list() returns list of dicts with 'emoji', 'match_start', 'match_end'
    emoji_data = emoji.emoji_list(text)

    if not emoji_data:
        return text

    # Process from end to start to avoid position shifts
    result = text
    for item in reversed(emoji_data):
        emoji_char = item["emoji"]
        start = item["match_start"]
        end = item["match_end"]

        # Check if there's a variation selector (U+FE0F) immediately after the emoji
        # and extend the end position to include it
        actual_end = end
        if actual_end < len(result) and ord(result[actual_end]) == 0xFE0F:
            actual_end += 1

        img_path = get_emoji_image_path(emoji_char)

        if img_path:
            # Use file:// URL for local images
            # ReportLab Paragraph needs proper file URI
            img_uri = img_path.replace("\\", "/")
            if not img_uri.startswith("file:///"):
                img_uri = "file:///" + img_uri

            # Size emoji to match font size (slightly larger for visibility)
            emoji_size = int(font_size * 1.2)
            replacement = f'<img src="{img_uri}" width="{emoji_size}" height="{emoji_size}" valign="middle"/>'
        else:
            # Fallback to the emoji character itself (will render as monochrome)
            replacement = emoji_char

        # Replace this emoji occurrence (including any trailing variation selector)
        result = result[:start] + replacement + result[actual_end:]

    return result


def escape_html_except_tags(text):
    """
    Escape HTML special characters but preserve <img> tags.

    :param text: Text that may contain HTML entities and <img> tags
    :return: Escaped text with <img> tags preserved
    """
    # First, temporarily replace <img> tags with placeholders
    img_tags = []

    def save_img_tag(match):
        img_tags.append(match.group(0))
        return f"___IMG_TAG_{len(img_tags)-1}___"

    text = re.sub(r"<img[^>]+>", save_img_tag, text)

    # Escape HTML entities
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # Restore <img> tags
    for i, tag in enumerate(img_tags):
        text = text.replace(f"___IMG_TAG_{i}___", tag)

    return text


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


def _estimate_if_text_fits(message, max_width, available_height, font_name):
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


def _find_optimal_font_size_for_paragraph(
    message, max_width, available_height, font_name, min_font_size, max_font_size
):
    """
    Find optimal font size using binary search for Paragraph-based rendering.

    :param message: Text message
    :param max_width: Maximum width
    :param available_height: Maximum height
    :param font_name: Font name
    :param min_font_size: Minimum font size to try
    :param max_font_size: Maximum font size to try
    :return: (best_font_size, text_fits_completely, final_paragraph)
    """
    style = ParagraphStyle(
        "MessageStyle",
        fontName=font_name,
        fontSize=max_font_size,
        leading=get_font_line_height(font_name, max_font_size),
        alignment=TA_LEFT,
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

        processed_message = replace_emojis_with_images(message, test_font_size)
        processed_message = escape_html_except_tags(processed_message)
        processed_message = processed_message.replace("\n", "<br/>")

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


def _find_optimal_font_size_for_text(
    message,
    max_width,
    available_height,
    canvas_obj,
    font_name,
    min_font_size,
    max_font_size,
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
                test_wrapped_lines.extend(
                    wrap_text_to_width(
                        line, max_width, canvas_obj, font_name, test_font_size
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


def _truncate_paragraph_to_fit(
    message, max_width, available_height, font_name, font_size, style
):
    """
    Truncate message to fit available space using binary search.

    :param message: Text message to truncate
    :param max_width: Maximum width
    :param available_height: Maximum height
    :param font_name: Font name
    :param font_size: Font size to use
    :param style: ParagraphStyle to use
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

        processed_message = replace_emojis_with_images(truncated_message, font_size)
        processed_message = escape_html_except_tags(processed_message)
        processed_message = processed_message.replace("\n", "<br/>")

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

    processed_message = replace_emojis_with_images(truncated_message, font_size)
    processed_message = escape_html_except_tags(processed_message)
    processed_message = processed_message.replace("\n", "<br/>")
    para = Paragraph(processed_message, style)

    return para, best_fit_lines, len(message_lines)


def _draw_address_section(
    canvas_obj, address, divider_x, margin, height, font_name, width, enable_emoji=True
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
    """
    addr_x = divider_x + margin
    address_font_size = 12

    # Check if address contains emojis
    has_emojis = enable_emoji and bool(emoji.emoji_list(address))

    if has_emojis:
        # Use Paragraph for emoji support
        style = ParagraphStyle(
            "AddressStyle",
            fontName=font_name,
            fontSize=address_font_size,
            leading=get_font_line_height(font_name, address_font_size),
            alignment=TA_LEFT,
            leftIndent=0,
            rightIndent=0,
            spaceBefore=0,
            spaceAfter=0,
        )

        # Process address with emoji support
        processed_address = replace_emojis_with_images(address, address_font_size)
        processed_address = escape_html_except_tags(processed_address)
        processed_address = processed_address.replace("\n", "<br/>")

        para = Paragraph(processed_address, style)

        # Calculate available width for address
        available_width = width - divider_x - 2 * margin

        # Wrap and get height
        w, h = para.wrap(available_width, height)

        # Position address (starting from bottom + 40mm offset)
        addr_y = margin + 40

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
        # Traditional text rendering without emojis
        canvas_obj.setFont(font_name, address_font_size)

        address_lines = address.splitlines()
        line_height = 14
        total_address_height = len(address_lines) * line_height
        addr_y = margin + 40 + total_address_height

        for line in address_lines:
            canvas_obj.drawString(addr_x, addr_y, line)
            addr_y -= line_height


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
    """
    width, height = page_size
    margin = 10 * mm

    # Calculate layout dimensions
    divider_x = width * message_area_ratio
    max_width = divider_x - 2 * margin
    top_margin = margin
    bottom_margin = margin
    available_height = height - top_margin - bottom_margin

    # Check if message contains emojis
    has_emojis = enable_emoji and bool(emoji.emoji_list(message))

    # Quick estimation check
    text_fits = _estimate_if_text_fits(message, max_width, available_height, font_name)

    # === EMOJI MODE (Paragraph-based rendering) ===
    if has_emojis:
        # Pre-cache all emoji images for performance
        _LOGGER.debug("Pre-caching emoji images for message")
        emoji_list = emoji.emoji_list(message)
        for emoji_item in emoji_list:
            get_emoji_image_path(emoji_item["emoji"])

        # Create base paragraph style
        style = ParagraphStyle(
            "MessageStyle",
            fontName=font_name,
            fontSize=DEFAULT_FONT_SIZE,
            leading=get_font_line_height(font_name, DEFAULT_FONT_SIZE),
            alignment=TA_LEFT,
            leftIndent=0,
            rightIndent=0,
            spaceBefore=0,
            spaceAfter=0,
        )

        # Determine font size and create paragraph
        if text_fits is None:
            # Run binary search optimization
            font_size, text_fits, para = _find_optimal_font_size_for_paragraph(
                message,
                max_width,
                available_height,
                font_name,
                MIN_FONT_SIZE,
                DEFAULT_FONT_SIZE,
            )
        else:
            # Skip optimization, use minimum font size
            font_size = MIN_FONT_SIZE
            para = None

        # Handle truncation if text doesn't fit
        if not text_fits:
            _LOGGER.warning(
                f"Message is too long to fit on postcard even at minimum font size {MIN_FONT_SIZE}pt. "
                f"Message will be truncated. Original length: {len(message)} characters."
            )

            para, lines_used, total_lines = _truncate_paragraph_to_fit(
                message, max_width, available_height, font_name, MIN_FONT_SIZE, style
            )

            if lines_used < total_lines:
                _LOGGER.warning(
                    f"Message truncated to {lines_used} of {total_lines} lines to fit on postcard."
                )

            font_size = MIN_FONT_SIZE

        # Ensure we have a paragraph to draw
        if para is None:
            style.fontSize = font_size
            style.leading = get_font_line_height(font_name, font_size)
            processed_message = replace_emojis_with_images(message, font_size)
            processed_message = escape_html_except_tags(processed_message)
            processed_message = processed_message.replace("\n", "<br/>")
            para = Paragraph(processed_message, style)

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
        frame.addFromList([para], c)
        final_line_height = style.leading

    # === TEXT MODE (Text-based rendering without emojis) ===
    else:
        if text_fits is None:
            # Run binary search optimization
            font_size, wrapped_lines = _find_optimal_font_size_for_text(
                message,
                max_width,
                available_height,
                c,
                font_name,
                MIN_FONT_SIZE,
                DEFAULT_FONT_SIZE,
            )
        else:
            # Skip optimization, use minimum font size
            font_size = MIN_FONT_SIZE
            lines = message.splitlines()
            wrapped_lines = []
            c.setFont(font_name, font_size)
            for line in lines:
                if line.strip():
                    wrapped_lines.extend(
                        wrap_text_to_width(line, max_width, c, font_name, font_size)
                    )
                else:
                    wrapped_lines.append("")

        # Calculate line height
        c.setFont(font_name, font_size)
        final_line_height = get_font_line_height(font_name, font_size)

        # Truncate if necessary
        if len(wrapped_lines) * final_line_height >= available_height:
            max_lines = int(available_height / final_line_height)
            _LOGGER.warning(
                f"Message is too long to fit on postcard even at minimum font size {font_size}pt. "
                f"Message will be truncated from {len(wrapped_lines)} lines to {max_lines} lines. "
                f"Original message length: {len(message)} characters."
            )
            wrapped_lines = wrapped_lines[:max_lines]
            if max_lines > 0:
                wrapped_lines[-1] = wrapped_lines[-1] + " [...]"

        # Draw text
        text_obj = c.beginText(margin, height - margin - font_size)
        text_obj.setFont(font_name, font_size)
        text_obj.setLeading(final_line_height)
        for line in wrapped_lines:
            text_obj.textLine(line)
        c.drawText(text_obj)

    # === DRAW ADDRESS AND STAMP ===
    _draw_address_section(
        c, address, divider_x, margin, height, font_name, width, enable_emoji
    )
    _draw_stamp_box(c, width, height, margin, font_name)

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
    c.setStrokeColorRGB(0, 0, 0)
    c.line(divider_x, margin, divider_x, height - margin)
