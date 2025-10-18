from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
import emoji
import re
import os
import urllib.request
import urllib.error
import logging
from io import BytesIO
from font_manager import get_arabic_font, get_cjk_font

# Arabic text support
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False

_LOGGER = logging.getLogger(__name__)

if not ARABIC_SUPPORT:
    _LOGGER.warning(
        "Arabic text support not available. Install 'arabic-reshaper' and 'python-bidi' "
        "for proper Arabic text rendering: pip install arabic-reshaper python-bidi"
    )


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


def contains_arabic(text):
    """
    Check if text contains Arabic characters.

    :param text: Text to check
    :return: True if text contains Arabic characters
    """
    # Arabic Unicode ranges:
    # U+0600-U+06FF: Arabic
    # U+0750-U+077F: Arabic Supplement
    # U+08A0-U+08FF: Arabic Extended-A
    # U+FB50-U+FDFF: Arabic Presentation Forms-A
    # U+FE70-U+FEFF: Arabic Presentation Forms-B
    arabic_pattern = re.compile(
        r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
    )
    return bool(arabic_pattern.search(text))


def contains_cjk(text):
    """
    Check if text contains CJK (Chinese, Japanese, Korean) characters.

    :param text: Text to check
    :return: True if text contains CJK characters
    """
    # CJK Unicode ranges:
    # U+4E00-U+9FFF: CJK Unified Ideographs (Chinese, Japanese, Korean)
    # U+3400-U+4DBF: CJK Unified Ideographs Extension A
    # U+20000-U+2A6DF: CJK Unified Ideographs Extension B
    # U+2A700-U+2B73F: CJK Unified Ideographs Extension C
    # U+2B740-U+2B81F: CJK Unified Ideographs Extension D
    # U+3040-U+309F: Hiragana (Japanese)
    # U+30A0-U+30FF: Katakana (Japanese)
    # U+AC00-U+D7AF: Hangul Syllables (Korean)
    # U+1100-U+11FF: Hangul Jamo (Korean)
    cjk_pattern = re.compile(
        r"[\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF\u1100-\u11FF]"
    )
    return bool(cjk_pattern.search(text))


def process_arabic_text(text):
    """
    Process Arabic text for proper display (reshaping and bidi).

    :param text: Text potentially containing Arabic
    :return: Processed text ready for rendering
    """
    if not ARABIC_SUPPORT:
        return text

    if not contains_arabic(text):
        return text

    try:
        # Reshape Arabic characters (connect letters properly)
        reshaped_text = arabic_reshaper.reshape(text)
        # Apply bidirectional algorithm for RTL display
        bidi_text = get_display(reshaped_text)
        return bidi_text
    except Exception as e:
        _LOGGER.warning(f"Failed to process Arabic text: {e}")
        return text


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
    Note: This function should be called BEFORE processing Arabic text with bidi algorithm.

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


def process_text_for_rendering(text, font_size, enable_emoji=True):
    """
    Process text for rendering, handling both emojis and Arabic text.

    Order of operations:
    1. Replace emojis with image tags (if enabled)
    2. Process Arabic text for proper RTL display

    :param text: Text to process
    :param font_size: Font size for emoji sizing
    :param enable_emoji: Enable emoji replacement
    :return: Processed text ready for rendering
    """
    # First, replace emojis with images (before bidi processing)
    if enable_emoji:
        text = replace_emojis_with_images(text, font_size)

    # Then process Arabic text for RTL display
    # Note: HTML tags from emoji replacement are preserved
    if contains_arabic(text):
        # Split by HTML tags to preserve them
        parts = re.split(r"(<img[^>]+>)", text)
        processed_parts = []

        for part in parts:
            if part.startswith("<img"):
                # Keep HTML tags as-is
                processed_parts.append(part)
            else:
                # Process text parts for Arabic
                processed_parts.append(process_arabic_text(part))

        text = "".join(processed_parts)

    return text


def _wrap_special_text_with_fonts(text, arabic_font_name=None, cjk_font_name=None):
    """Wrap Arabic and CJK runs in the text with ReportLab <font name="..."> tags.

    Expects plain text (no <img> tags). Returns text where Arabic and CJK
    substrings are wrapped so Paragraph can render them with the appropriate fonts.
    Note: Does NOT escape HTML - escaping should be done AFTER this function.
    """
    if not arabic_font_name and not cjk_font_name:
        return text

    # Build a pattern that matches both Arabic and CJK runs
    patterns = []
    if arabic_font_name:
        patterns.append(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+")
    if cjk_font_name:
        patterns.append(r"[\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF\u1100-\u11FF]+")
    
    combined_pattern = "|".join(f"({p})" for p in patterns)
    parts = re.split(f"({combined_pattern})", text)
    
    out_parts = []
    for part in parts:
        if not part:
            continue
        
        if arabic_font_name and contains_arabic(part):
            # Wrap Arabic text with Arabic font tags
            out_parts.append(f'<font name="{arabic_font_name}">{part}</font>')
        elif cjk_font_name and contains_cjk(part):
            # Wrap CJK text with CJK font tags
            out_parts.append(f'<font name="{cjk_font_name}">{part}</font>')
        else:
            out_parts.append(part)

    return "".join(out_parts)


def _wrap_arabic_spans_with_font(text, arabic_font_name):
    """Wrap Arabic runs in the text with ReportLab <font name="..."> tags.

    Expects plain text (no <img> tags). Returns text where Arabic
    substrings are wrapped so Paragraph can render them with the Arabic font.
    Note: Does NOT escape HTML - escaping should be done AFTER this function.
    
    DEPRECATED: Use _wrap_special_text_with_fonts instead for multi-language support.
    """
    return _wrap_special_text_with_fonts(text, arabic_font_name=arabic_font_name)


def escape_html_except_tags(text):
    """
    Escape HTML special characters but preserve <img> and <font> tags.

    :param text: Text that may contain HTML entities, <img> tags, and <font> tags
    :return: Escaped text with allowed tags preserved
    """
    # First, temporarily replace allowed tags with placeholders
    allowed_tags = []

    def save_tag(match):
        allowed_tags.append(match.group(0))
        return f"___TAG_{len(allowed_tags)-1}___"

    # Save <img> tags and <font> tags (both opening and closing)
    text = re.sub(r"<img[^>]+>", save_tag, text)
    text = re.sub(r"<font[^>]+>", save_tag, text)
    text = re.sub(r"</font>", save_tag, text)

    # Escape HTML entities
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # Restore allowed tags
    for i, tag in enumerate(allowed_tags):
        text = text.replace(f"___TAG_{i}___", tag)

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
    message,
    max_width,
    available_height,
    font_name,
    min_font_size,
    max_font_size,
    alignment=TA_LEFT,
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

        processed_message = process_text_for_rendering(
            message, test_font_size, enable_emoji=True
        )

        # Preserve <img> tags while wrapping Arabic/CJK text spans with appropriate fonts
        arabic_font_name = get_arabic_font()
        cjk_font_name = get_cjk_font()
        parts = re.split(r"(<img[^>]+>)", processed_message)
        wrapped_parts = []
        for p in parts:
            if p.startswith("<img"):
                wrapped_parts.append(p)
            else:
                # wrap Arabic and CJK spans inside this text part
                wrapped = _wrap_special_text_with_fonts(p, arabic_font_name, cjk_font_name)
                wrapped_parts.append(wrapped)
        processed_message = "".join(wrapped_parts)

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

        processed_message = process_text_for_rendering(
            truncated_message, font_size, enable_emoji=True
        )
        # Preserve <img> tags and wrap Arabic/CJK spans with appropriate fonts
        arabic_font_name = get_arabic_font()
        cjk_font_name = get_cjk_font()
        parts = re.split(r"(<img[^>]+>)", processed_message)
        wrapped_parts = []
        for p in parts:
            if p.startswith("<img"):
                wrapped_parts.append(p)
            else:
                wrapped_parts.append(_wrap_special_text_with_fonts(p, arabic_font_name, cjk_font_name))
        processed_message = "".join(wrapped_parts)

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

    processed_message = process_text_for_rendering(
        truncated_message, font_size, enable_emoji=True
    )
    arabic_font_name = get_arabic_font()
    cjk_font_name = get_cjk_font()
    parts = re.split(r"(<img[^>]+>)", processed_message)
    wrapped_parts = []
    for p in parts:
        if p.startswith("<img"):
            wrapped_parts.append(p)
        else:
            wrapped_parts.append(_wrap_special_text_with_fonts(p, arabic_font_name, cjk_font_name))
    processed_message = "".join(wrapped_parts)
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

    # Check if address contains emojis or Arabic text
    has_emojis = enable_emoji and bool(emoji.emoji_list(address))
    has_arabic = contains_arabic(address)
    needs_paragraph = has_emojis or has_arabic

    if needs_paragraph:
        # Use Paragraph for emoji and/or Arabic support
        # Use right alignment for Arabic text
        alignment = TA_RIGHT if has_arabic else TA_LEFT

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
        )

        # Process address with emoji and Arabic support
        processed_address = process_text_for_rendering(
            address, address_font_size, enable_emoji=enable_emoji
        )

        # Preserve <img> tags and wrap Arabic/CJK spans with appropriate fonts
        arabic_font_name = get_arabic_font()
        cjk_font_name = get_cjk_font()
        parts = re.split(r"(<img[^>]+>)", processed_address)
        wrapped_parts = []
        for p in parts:
            if p.startswith("<img"):
                wrapped_parts.append(p)
            else:
                wrapped_parts.append(_wrap_special_text_with_fonts(p, arabic_font_name, cjk_font_name))
        processed_address = "".join(wrapped_parts)

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
            if contains_arabic(line):
                arabic_font_name = get_arabic_font()
                canvas_obj.setFont(arabic_font_name, address_font_size)
            elif contains_cjk(line):
                cjk_font_name = get_cjk_font()
                canvas_obj.setFont(cjk_font_name, address_font_size)
            else:
                canvas_obj.setFont(font_name, address_font_size)

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

    # Check if message contains emojis, Arabic, or CJK text
    has_emojis = enable_emoji and bool(emoji.emoji_list(message))
    has_arabic = contains_arabic(message)
    has_cjk = contains_cjk(message)
    needs_paragraph = has_emojis or has_arabic or has_cjk

    # Quick estimation check
    text_fits = _estimate_if_text_fits(message, max_width, available_height, font_name)

    # === PARAGRAPH MODE (for emoji, Arabic, and/or CJK text) ===
    if needs_paragraph:
        # Pre-cache all emoji images for performance
        if has_emojis:
            _LOGGER.debug("Pre-caching emoji images for message")
            emoji_list = emoji.emoji_list(message)
            for emoji_item in emoji_list:
                get_emoji_image_path(emoji_item["emoji"])

        # Create base paragraph style with appropriate alignment
        # Use right alignment for Arabic text
        alignment = TA_RIGHT if has_arabic else TA_LEFT

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
                alignment=alignment,
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
            processed_message = process_text_for_rendering(
                message, font_size, enable_emoji=enable_emoji
            )

            # Wrap Arabic/CJK spans with appropriate fonts while preserving <img> tags
            arabic_font_name = get_arabic_font()
            cjk_font_name = get_cjk_font()
            parts = re.split(r"(<img[^>]+>)", processed_message)
            wrapped_parts = []
            for p in parts:
                if p.startswith("<img"):
                    wrapped_parts.append(p)
                else:
                    wrapped_parts.append(
                        _wrap_special_text_with_fonts(p, arabic_font_name, cjk_font_name)
                    )
            processed_message = "".join(wrapped_parts)

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
                    # When wrapping text for canvas mode, treat Arabic and CJK lines specially
                    if contains_arabic(line):
                        # Use Arabic font for measurement and wrapping
                        arabic_font_name = get_arabic_font()
                        wrapped_lines.extend(
                            wrap_text_to_width(
                                line, max_width, c, arabic_font_name, font_size
                            )
                        )
                    elif contains_cjk(line):
                        # Use CJK font for measurement and wrapping
                        cjk_font_name = get_cjk_font()
                        wrapped_lines.extend(
                            wrap_text_to_width(
                                line, max_width, c, cjk_font_name, font_size
                            )
                        )
                    else:
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

        # Draw text (set font per-line depending on Arabic/CJK content)
        y = height - margin - font_size
        for line in wrapped_lines:
            if contains_arabic(line):
                arabic_font_name = get_arabic_font()
                c.setFont(arabic_font_name, font_size)
            elif contains_cjk(line):
                cjk_font_name = get_cjk_font()
                c.setFont(cjk_font_name, font_size)
            else:
                c.setFont(font_name, font_size)

            # drawString uses left-to-right origin; for Arabic canvas drawing we keep it
            # simple - Paragraph mode handles rich RTL/reshaping. For canvas mode we
            # draw the raw line (reshaped text should already be applied earlier).
            c.drawString(margin, y, line)
            y -= final_line_height

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
