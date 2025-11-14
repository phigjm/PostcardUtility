"""
Text processing utilities for postcard generation.
Handles color conversion, HTML escaping, and text rendering preparation.
"""

import re
import emoji
import logging
from .emoji_handler import replace_emojis_with_images
from .language_support import contains_arabic, process_arabic_text, wrap_special_text_with_fonts, get_arabic_font, get_cjk_font

_LOGGER = logging.getLogger(__name__)

# Color mapping from color names to RGB tuples
COLOR_MAP = {
    "black": (0, 0, 0),
    "white": (1, 1, 1),
    "gray": (0.5, 0.5, 0.5),
    "red": (1, 0, 0),
    "blue": (0, 0, 1),
    "green": (0, 0.5, 0),
    "navy": (0, 0, 0.5),
    "darkred": (0.5, 0, 0),
    "purple": (0.5, 0, 0.5),
    "brown": (0.6, 0.4, 0.2),
    "orange": (1, 0.65, 0),
}


def get_color_rgb(color_input):
    """
    Convert color input to RGB tuple.
    Supports:
    - Color names: 'black', 'red', 'blue', etc.
    - Hex codes: '#FF0000', 'FF0000'
    - RGB values: '255,0,0', 'rgb(255,0,0)'
    
    :param color_input: Color string in various formats
    :return: RGB tuple (r, g, b) where each value is between 0 and 1
    """
    if not color_input or not isinstance(color_input, str):
        return (0, 0, 0)  # Default to black
    
    color_input = color_input.strip().lower()
    
    # Check if it's a predefined color name
    if color_input in COLOR_MAP:
        return COLOR_MAP[color_input]
    
    # Check for hex color code
    if color_input.startswith('#'):
        hex_color = color_input.lstrip('#')
    elif len(color_input) == 6 and all(c in '0123456789abcdef' for c in color_input):
        hex_color = color_input
    else:
        hex_color = None
    
    if hex_color and len(hex_color) == 6:
        try:
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            return (r, g, b)
        except ValueError:
            pass
    
    # Check for RGB format: "255,0,0" or "rgb(255,0,0)"
    rgb_match = re.match(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color_input)
    if rgb_match:
        try:
            r = int(rgb_match.group(1)) / 255.0
            g = int(rgb_match.group(2)) / 255.0
            b = int(rgb_match.group(3)) / 255.0
            return (max(0, min(1, r)), max(0, min(1, g)), max(0, min(1, b)))
        except (ValueError, AttributeError):
            pass
    
    # Try simple comma-separated RGB values
    try:
        parts = color_input.split(',')
        if len(parts) == 3:
            r = int(parts[0].strip()) / 255.0
            g = int(parts[1].strip()) / 255.0
            b = int(parts[2].strip()) / 255.0
            return (max(0, min(1, r)), max(0, min(1, g)), max(0, min(1, b)))
    except (ValueError, AttributeError):
        pass
    
    # Default to black if nothing matched
    return (0, 0, 0)


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


def prepare_text_with_language_fonts(text, enable_emoji=True, font_size=12, text_color="black"):
    """
    Prepare text for ReportLab Paragraph rendering with proper font tags and emoji support.
    
    :param text: Raw text to prepare
    :param enable_emoji: Whether to replace emojis with images
    :param font_size: Font size for emoji sizing
    :param text_color: Text color name or hex code (default='black')
    :return: HTML-formatted text ready for Paragraph rendering
    """
    # Process for emoji and Arabic RTL
    processed_text = process_text_for_rendering(text, font_size, enable_emoji)
    
    # Preserve <img> tags while wrapping Arabic/CJK text spans with appropriate fonts
    arabic_font_name = get_arabic_font()
    cjk_font_name = get_cjk_font()
    parts = re.split(r"(<img[^>]+>)", processed_text)
    wrapped_parts = []
    for p in parts:
        if p.startswith("<img"):
            wrapped_parts.append(p)
        else:
            # wrap Arabic and CJK spans inside this text part
            wrapped = wrap_special_text_with_fonts(p, arabic_font_name, cjk_font_name)
            wrapped_parts.append(wrapped)
    processed_text = "".join(wrapped_parts)
    
    # Escape HTML and convert newlines
    processed_text = escape_html_except_tags(processed_text)
    processed_text = processed_text.replace("\n", "<br/>")
    
    # Convert text color to hex format for HTML font tag
    rgb = get_color_rgb(text_color)
    hex_color = "#{:02x}{:02x}{:02x}".format(
        int(rgb[0] * 255),
        int(rgb[1] * 255),
        int(rgb[2] * 255)
    )
    
    # Wrap entire text in a font tag with the specified color
    processed_text = f'<font color="{hex_color}">{processed_text}</font>'
    
    return processed_text


def has_special_rendering_needs(text, enable_emoji=True):
    """
    Check if text has special rendering needs (emoji, Arabic, CJK).
    
    :param text: Text to check
    :param enable_emoji: Whether emoji support is enabled
    :return: True if text needs Paragraph rendering (vs simple canvas text)
    """
    from .language_support import contains_cjk
    
    has_emojis = enable_emoji and bool(emoji.emoji_list(text))
    has_arabic = contains_arabic(text)
    has_cjk = contains_cjk(text)
    
    return has_emojis or has_arabic or has_cjk
