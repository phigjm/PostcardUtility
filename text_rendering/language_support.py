"""
Language support utilities for postcard generation.
Handles Arabic, CJK (Chinese, Japanese, Korean), and other special character sets.
"""

import re
import logging
import sys
import os

# Add parent directory to path to import font_manager
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


def wrap_special_text_with_fonts(text, arabic_font_name=None, cjk_font_name=None):
    """
    Wrap Arabic and CJK runs in the text with ReportLab <font name="..."> tags.

    Expects plain text (no <img> tags). Returns text where Arabic and CJK
    substrings are wrapped so Paragraph can render them with the appropriate fonts.
    Note: Does NOT escape HTML - escaping should be done AFTER this function.
    
    :param text: Plain text to process
    :param arabic_font_name: Font name for Arabic text (optional)
    :param cjk_font_name: Font name for CJK text (optional)
    :return: Text with font tags around special character runs
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


def get_font_for_text(text, default_font_name):
    """
    Determine the appropriate font name for a given text based on its content.
    
    :param text: Text to analyze
    :param default_font_name: Default font to use if no special characters
    :return: Font name to use
    """
    if contains_arabic(text):
        return get_arabic_font()
    elif contains_cjk(text):
        return get_cjk_font()
    else:
        return default_font_name
