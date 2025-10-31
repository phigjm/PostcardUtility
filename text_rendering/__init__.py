"""
Text rendering utilities package.
Modular components for postcard text side generation.
"""

from .emoji_handler import set_emoji_cache_dir, precache_emojis_in_text, get_emoji_image_path
from .language_support import contains_arabic, contains_cjk, get_font_for_text, process_arabic_text
from .text_processing import get_color_rgb, has_special_rendering_needs, prepare_text_with_language_fonts
from .text_fitting import (
    MIN_FONT_SIZE,
    DEFAULT_FONT_SIZE,
    get_font_line_height,
    wrap_text_to_width,
    estimate_if_text_fits,
    find_optimal_font_size_for_paragraph,
    find_optimal_font_size_for_text,
    truncate_paragraph_to_fit,
)

__all__ = [
    # Emoji handling
    'set_emoji_cache_dir',
    'precache_emojis_in_text',
    'get_emoji_image_path',
    # Language support
    'contains_arabic',
    'contains_cjk',
    'get_font_for_text',
    'process_arabic_text',
    # Text processing
    'get_color_rgb',
    'has_special_rendering_needs',
    'prepare_text_with_language_fonts',
    # Text fitting
    'MIN_FONT_SIZE',
    'DEFAULT_FONT_SIZE',
    'get_font_line_height',
    'wrap_text_to_width',
    'estimate_if_text_fits',
    'find_optimal_font_size_for_paragraph',
    'find_optimal_font_size_for_text',
    'truncate_paragraph_to_fit',
]
