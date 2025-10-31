"""
Emoji handling utilities for postcard generation.
Provides emoji detection, image downloading, and replacement functionality.
"""

import emoji
import os
import urllib.request
import urllib.error
import logging

_LOGGER = logging.getLogger(__name__)

# Cache directory for emoji images
EMOJI_CACHE_DIR = None  # Will be set dynamically

# In-memory cache of emoji characters that previously failed to download
_FAILED_EMOJI_DOWNLOADS = set()

# In-memory cache of successfully downloaded emoji paths to avoid repeated file system checks
_EMOJI_PATH_CACHE = {}


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


def precache_emojis_in_text(text):
    """
    Pre-cache all emoji images found in text for better performance.
    
    :param text: Text to scan for emojis
    """
    emoji_list = emoji.emoji_list(text)
    for emoji_item in emoji_list:
        get_emoji_image_path(emoji_item["emoji"])
