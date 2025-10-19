"""
Font Manager for Multi-language Text Support

This module handles automatic detection, download, and registration of fonts
that support Arabic, Chinese, Japanese, Korean, and other languages.
"""

import os
import urllib.request
import logging
from pathlib import Path
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

_LOGGER = logging.getLogger(__name__)

# Google Fonts with good Arabic support (Open Source)
ARABIC_FONTS = {
    "Amiri": {
        "url": "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf",
        "filename": "Amiri-Regular.ttf",
        "description": "Traditional Arabic typeface with excellent support",
    },
    "Cairo": {
        "url": "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo-Regular.ttf",
        "filename": "Cairo-Regular.ttf",
        "description": "Modern Arabic sans-serif font",
    },
    "Tajawal": {
        "url": "https://github.com/google/fonts/raw/main/ofl/tajawal/Tajawal-Regular.ttf",
        "filename": "Tajawal-Regular.ttf",
        "description": "Clean and modern Arabic font",
    },
    "Scheherazade": {
        "url": "https://github.com/google/fonts/raw/main/ofl/scheherazadenew/ScheherazadeNew-Regular.ttf",
        "filename": "ScheherazadeNew-Regular.ttf",
        "description": "Classical Arabic calligraphic style",
    },
}

# Google Fonts with good CJK (Chinese/Japanese/Korean) support
CJK_FONTS = {
    "NotoSansSC": {
        "url": "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC-Regular.ttf",
        "filename": "NotoSansSC-Regular.ttf",
        "description": "Noto Sans Simplified Chinese - comprehensive Chinese support",
    },
    "NotoSansTC": {
        "url": "https://github.com/google/fonts/raw/main/ofl/notosanstc/NotoSansTC-Regular.ttf",
        "filename": "NotoSansTC-Regular.ttf",
        "description": "Noto Sans Traditional Chinese",
    },
    "NotoSansJP": {
        "url": "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP-Regular.ttf",
        "filename": "NotoSansJP-Regular.ttf",
        "description": "Noto Sans Japanese",
    },
    "NotoSansKR": {
        "url": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR-Regular.ttf",
        "filename": "NotoSansKR-Regular.ttf",
        "description": "Noto Sans Korean",
    },
}

# Multi-language fonts (support multiple scripts)
MULTILINGUAL_FONTS = {
    "NotoSans": {
        "url": "https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans-Regular.ttf",
        "filename": "NotoSans-Regular.ttf",
        "description": "Noto Sans - supports Latin, Greek, Cyrillic and more",
    },
}

# System font locations by platform
SYSTEM_FONT_PATHS = {
    "windows": ["C:/Windows/Fonts", os.path.expandvars("%WINDIR%/Fonts")],
    "linux": ["/usr/share/fonts/truetype", "/usr/local/share/fonts", "~/.fonts"],
    "darwin": ["/Library/Fonts", "/System/Library/Fonts", "~/Library/Fonts"],  # macOS
}

# System fonts that support Arabic
SYSTEM_ARABIC_FONTS = [
    "arial.ttf",
    "Arial.ttf",
    "tahoma.ttf",
    "Tahoma.ttf",
    "times.ttf",
    "Times.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
]

# System fonts that support CJK (Chinese/Japanese/Korean)
SYSTEM_CJK_FONTS = [
    # Windows fonts
    "msyh.ttc",  # Microsoft YaHei (Simplified Chinese)
    "msjh.ttc",  # Microsoft JhengHei (Traditional Chinese)
    "msgothic.ttc",  # MS Gothic (Japanese)
    "malgun.ttf",  # Malgun Gothic (Korean)
    "simsun.ttc",  # SimSun (Simplified Chinese)
    "mingliu.ttc",  # MingLiU (Traditional Chinese)
    # macOS fonts
    "PingFang.ttc",  # PingFang (Chinese)
    "Hiragino Sans GB.ttc",  # Hiragino Sans (Chinese)
    "Hiragino Kaku Gothic Pro.ttf",  # Hiragino (Japanese)
    "AppleSDGothicNeo.ttc",  # Apple SD Gothic (Korean)
    # Linux fonts
    "NotoSansCJK-Regular.ttc",
    "NotoSansSC-Regular.otf",
    "NotoSansTC-Regular.otf",
    "NotoSansJP-Regular.otf",
    "NotoSansKR-Regular.otf",
    "WenQuanYi Micro Hei.ttf",
    "Droid Sans Fallback.ttf",
]


def get_fonts_directories():
    """
    Get all possible fonts directories (both PostcardUtility/fonts and static/fonts).
    Returns list of directories, creates them if they don't exist.
    """
    directories = []

    # 1. PostcardUtility/fonts (for local development)
    local_fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
    directories.append(local_fonts_dir)

    # 2. Django static/fonts (for production/Docker)
    # Go up from PostcardUtility to project root, then to static/fonts
    project_root = os.path.dirname(os.path.dirname(__file__))
    static_fonts_dir = os.path.join(project_root, "static", "fonts")
    directories.append(static_fonts_dir)

    # 3. Django staticfiles/fonts (collected static files in Docker)
    staticfiles_dir = os.path.join(project_root, "staticfiles", "fonts")
    if os.path.exists(staticfiles_dir):
        directories.append(staticfiles_dir)

    # Create directories if they don't exist
    for dir_path in directories[:2]:  # Only create the first two, not staticfiles
        os.makedirs(dir_path, exist_ok=True)

    return directories


def get_fonts_directory():
    """Get the primary fonts directory for downloaded fonts (backwards compatibility)."""
    return get_fonts_directories()[0]


def find_system_arabic_font():
    """
    Try to find an Arabic-supporting font in system fonts.

    :return: Path to font file or None if not found
    """
    return _find_system_font(SYSTEM_ARABIC_FONTS, "Arabic")


def find_system_cjk_font():
    """
    Try to find a CJK-supporting font in system fonts.

    :return: Path to font file or None if not found
    """
    return _find_system_font(SYSTEM_CJK_FONTS, "CJK")


def _find_system_font(font_list, font_type="font"):
    """
    Generic function to find a font in system fonts.

    :param font_list: List of font filenames to search for
    :param font_type: Type of font for logging purposes
    :return: Path to font file or None if not found
    """


def _find_system_font(font_list, font_type="font"):
    """
    Generic function to find a font in system fonts.

    :param font_list: List of font filenames to search for
    :param font_type: Type of font for logging purposes
    :return: Path to font file or None if not found
    """
    import platform

    system = platform.system().lower()

    if system == "windows":
        search_paths = SYSTEM_FONT_PATHS["windows"]
    elif system == "linux":
        search_paths = SYSTEM_FONT_PATHS["linux"]
    elif system == "darwin":
        search_paths = SYSTEM_FONT_PATHS["darwin"]
    else:
        _LOGGER.warning(f"Unknown platform: {system}")
        return None

    # Expand user paths
    search_paths = [os.path.expanduser(p) for p in search_paths]

    # Search for fonts
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue

        for font_name in font_list:
            # Check direct path
            font_path = os.path.join(search_path, font_name)
            if os.path.exists(font_path):
                _LOGGER.info(f"Found system {font_type} font: {font_path}")
                return font_path

            # Check subdirectories (for Linux)
            for root, dirs, files in os.walk(search_path):
                if font_name in files:
                    font_path = os.path.join(root, font_name)
                    _LOGGER.info(f"Found system {font_type} font: {font_path}")
                    return font_path

    _LOGGER.warning(f"No system {font_type} font found")
    return None


def download_font(font_dict, font_name, fonts_dir=None):
    """
    Download a font from a font dictionary (ARABIC_FONTS, CJK_FONTS, etc.).

    :param font_dict: Dictionary containing font information
    :param font_name: Name of the font to download
    :param fonts_dir: Directory to save fonts (default: ./fonts)
    :return: Path to downloaded font file or None if failed
    """
    if fonts_dir is None:
        fonts_dir = get_fonts_directory()

    if font_name not in font_dict:
        _LOGGER.error(
            f"Unknown font: {font_name}. Available fonts: {list(font_dict.keys())}"
        )
        return None

    font_info = font_dict[font_name]
    font_path = os.path.join(fonts_dir, font_info["filename"])

    # Check if already downloaded
    if os.path.exists(font_path):
        _LOGGER.info(f"Font already exists: {font_path}")
        return font_path

    # Download font
    try:
        _LOGGER.info(f"Downloading {font_name} font from Google Fonts...")
        _LOGGER.info(f"  URL: {font_info['url']}")
        _LOGGER.info(f"  Description: {font_info['description']}")

        urllib.request.urlretrieve(font_info["url"], font_path)

        _LOGGER.info(f"✓ Successfully downloaded: {font_path}")
        return font_path

    except Exception as e:
        _LOGGER.error(f"Failed to download font {font_name}: {e}")
        return None


def download_arabic_font(font_name="Amiri", fonts_dir=None):
    """
    Download an Arabic-supporting font from Google Fonts.

    :param font_name: Name of the font to download (from ARABIC_FONTS)
    :param fonts_dir: Directory to save fonts (default: ./fonts)
    :return: Path to downloaded font file or None if failed
    """
    return download_font(ARABIC_FONTS, font_name, fonts_dir)


def download_cjk_font(font_name="NotoSansSC", fonts_dir=None):
    """
    Download a CJK-supporting font from Google Fonts.

    :param font_name: Name of the font to download (from CJK_FONTS)
    :param fonts_dir: Directory to save fonts (default: ./fonts)
    :return: Path to downloaded font file or None if failed
    """
    return download_font(CJK_FONTS, font_name, fonts_dir)


def register_arabic_font(font_name="ArabicFont", force_download=False):
    """
    Register a font with Arabic support for use with ReportLab.

    This function tries multiple strategies:
    1. Check if already registered
    2. Look for system fonts (Arial, Tahoma, etc.)
    3. Look for downloaded fonts in ./fonts directory
    4. Download a font from Google Fonts if needed

    :param font_name: Name to register the font as in ReportLab
    :param force_download: Force download even if system font exists
    :return: Registered font name or None if failed
    """
    return _register_font(
        font_name=font_name,
        force_download=force_download,
        system_font_finder=find_system_arabic_font,
        font_dict=ARABIC_FONTS,
        default_download="Amiri",
        font_type="Arabic",
    )


def register_cjk_font(font_name="CJKFont", force_download=False):
    """
    Register a font with CJK (Chinese/Japanese/Korean) support for use with ReportLab.

    This function tries multiple strategies:
    1. Check if already registered
    2. Look for system fonts (MS YaHei, PingFang, etc.)
    3. Look for downloaded fonts in ./fonts directory
    4. Download a font from Google Fonts if needed

    :param font_name: Name to register the font as in ReportLab
    :param force_download: Force download even if system font exists
    :return: Registered font name or None if failed
    """
    return _register_font(
        font_name=font_name,
        force_download=force_download,
        system_font_finder=find_system_cjk_font,
        font_dict=CJK_FONTS,
        default_download="NotoSansSC",
        font_type="CJK",
    )


def _register_font(
    font_name,
    force_download,
    system_font_finder,
    font_dict,
    default_download,
    font_type,
):
    """
    Generic font registration function.

    :param font_name: Name to register the font as in ReportLab
    :param force_download: Force download even if system font exists
    :param system_font_finder: Function to find system fonts
    :param font_dict: Dictionary of downloadable fonts
    :param default_download: Default font to download
    :param font_type: Type of font for logging
    :return: Registered font name or None if failed
    """


def _register_font(
    font_name,
    force_download,
    system_font_finder,
    font_dict,
    default_download,
    font_type,
):
    """
    Generic font registration function.

    :param font_name: Name to register the font as in ReportLab
    :param force_download: Force download even if system font exists
    :param system_font_finder: Function to find system fonts
    :param font_dict: Dictionary of downloadable fonts
    :param default_download: Default font to download
    :param font_type: Type of font for logging
    :return: Registered font name or None if failed
    """
    # Check if already registered
    try:
        pdfmetrics.getFont(font_name)
        _LOGGER.info(f"Font '{font_name}' is already registered")
        return font_name
    except:
        pass

    font_path = None

    # Strategy 1: Find system font (unless forced download)
    if not force_download:
        font_path = system_font_finder()
        if font_path:
            _LOGGER.info(f"Using system font: {font_path}")

    # Strategy 2: Check all fonts directories (PostcardUtility/fonts, static/fonts, staticfiles/fonts)
    if not font_path:
        fonts_dirs = get_fonts_directories()
        for fonts_dir in fonts_dirs:
            if not os.path.exists(fonts_dir):
                continue
            for font_info in font_dict.values():
                local_path = os.path.join(fonts_dir, font_info["filename"])
                if os.path.exists(local_path):
                    font_path = local_path
                    _LOGGER.info(f"Using font from {fonts_dir}: {font_path}")
                    break
            if font_path:
                break

    # Strategy 3: Download a font
    if not font_path:
        _LOGGER.info(
            f"No {font_type} font found locally. Downloading from Google Fonts..."
        )
        font_path = download_font(font_dict, default_download)

    # Register the font
    if font_path and os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            _LOGGER.info(
                f"✓ Successfully registered font '{font_name}' from: {font_path}"
            )
            return font_name
        except Exception as e:
            _LOGGER.error(f"Failed to register font: {e}")
            return None

    _LOGGER.error(f"Failed to find or download a {font_type}-supporting font")
    return None


def get_arabic_font():
    """
    Get a font name that supports Arabic characters.
    Automatically registers a font if needed.

    :return: Font name suitable for Arabic text
    """
    # Try to register Arabic font
    font_name = register_arabic_font("ArabicFont")

    if font_name:
        return font_name

    # Fallback to Helvetica (won't render Arabic correctly but won't crash)
    _LOGGER.warning(
        "Could not register Arabic font. Using Helvetica as fallback. "
        "Arabic text will appear as boxes. "
        "Install arabic-reshaper and python-bidi: pip install arabic-reshaper python-bidi"
    )
    return "Helvetica"


def get_cjk_font():
    """
    Get a font name that supports CJK (Chinese/Japanese/Korean) characters.
    Automatically registers a font if needed.

    :return: Font name suitable for CJK text
    """
    # Try to register CJK font
    font_name = register_cjk_font("CJKFont")

    if font_name:
        return font_name

    # Fallback to Helvetica (won't render CJK correctly but won't crash)
    _LOGGER.warning(
        "Could not register CJK font. Using Helvetica as fallback. "
        "Chinese/Japanese/Korean text will appear as boxes."
    )
    return "Helvetica"


def list_available_arabic_fonts():
    """
    List all available Arabic fonts (system + downloadable).

    :return: Dictionary with font information
    """
    result = {
        "system_fonts": [],
        "downloaded_fonts": [],
        "downloadable_fonts": list(ARABIC_FONTS.keys()),
    }

    # Check system fonts
    system_font = find_system_arabic_font()
    if system_font:
        result["system_fonts"].append(system_font)

    # Check all fonts directories
    fonts_dirs = get_fonts_directories()
    for fonts_dir in fonts_dirs:
        if not os.path.exists(fonts_dir):
            continue
        for font_name, font_info in ARABIC_FONTS.items():
            local_path = os.path.join(fonts_dir, font_info["filename"])
            if os.path.exists(local_path):
                # Check if already in list (avoid duplicates)
                if not any(f["path"] == local_path for f in result["downloaded_fonts"]):
                    result["downloaded_fonts"].append(
                        {
                            "name": font_name,
                            "path": local_path,
                            "location": fonts_dir,
                            "description": font_info["description"],
                        }
                    )

    return result


def list_available_cjk_fonts():
    """
    List all available CJK fonts (system + downloadable).

    :return: Dictionary with font information
    """
    result = {
        "system_fonts": [],
        "downloaded_fonts": [],
        "downloadable_fonts": list(CJK_FONTS.keys()),
    }

    # Check system fonts
    system_font = find_system_cjk_font()
    if system_font:
        result["system_fonts"].append(system_font)

    # Check all fonts directories
    fonts_dirs = get_fonts_directories()
    for fonts_dir in fonts_dirs:
        if not os.path.exists(fonts_dir):
            continue
        for font_name, font_info in CJK_FONTS.items():
            local_path = os.path.join(fonts_dir, font_info["filename"])
            if os.path.exists(local_path):
                # Check if already in list (avoid duplicates)
                if not any(f["path"] == local_path for f in result["downloaded_fonts"]):
                    result["downloaded_fonts"].append(
                        {
                            "name": font_name,
                            "path": local_path,
                            "location": fonts_dir,
                            "description": font_info["description"],
                        }
                    )

    return result


def list_all_available_fonts():
    """
    List all available fonts for all languages.

    :return: Dictionary with font information for all supported languages
    """
    return {
        "arabic": list_available_arabic_fonts(),
        "cjk": list_available_cjk_fonts(),
    }


if __name__ == "__main__":
    # Test the font manager
    print("=" * 60)
    print("Multi-language Font Manager Test")
    print("=" * 60)

    # List available fonts
    print("\n1. Checking available fonts...")
    all_fonts = list_all_available_fonts()

    print("\n   ARABIC FONTS:")
    arabic_fonts = all_fonts["arabic"]
    print(f"   System fonts: {len(arabic_fonts['system_fonts'])}")
    for font in arabic_fonts["system_fonts"]:
        print(f"     - {font}")

    print(f"\n   Downloaded fonts: {len(arabic_fonts['downloaded_fonts'])}")
    for font in arabic_fonts["downloaded_fonts"]:
        print(f"     - {font['name']}: {font['path']}")

    print(f"\n   Downloadable fonts: {len(arabic_fonts['downloadable_fonts'])}")
    for font_name in arabic_fonts["downloadable_fonts"]:
        print(f"     - {font_name}: {ARABIC_FONTS[font_name]['description']}")

    print("\n   CJK FONTS:")
    cjk_fonts = all_fonts["cjk"]
    print(f"   System fonts: {len(cjk_fonts['system_fonts'])}")
    for font in cjk_fonts["system_fonts"]:
        print(f"     - {font}")

    print(f"\n   Downloaded fonts: {len(cjk_fonts['downloaded_fonts'])}")
    for font in cjk_fonts["downloaded_fonts"]:
        print(f"     - {font['name']}: {font['path']}")

    print(f"\n   Downloadable fonts: {len(cjk_fonts['downloadable_fonts'])}")
    for font_name in cjk_fonts["downloadable_fonts"]:
        print(f"     - {font_name}: {CJK_FONTS[font_name]['description']}")

    # Try to register fonts
    print("\n2. Registering fonts...")

    print("\n   Registering Arabic font...")
    arabic_font_name = register_arabic_font("TestArabicFont")
    if arabic_font_name:
        print(f"   ✓ Successfully registered: {arabic_font_name}")
    else:
        print("   ✗ Failed to register Arabic font")

    print("\n   Registering CJK font...")
    cjk_font_name = register_cjk_font("TestCJKFont")
    if cjk_font_name:
        print(f"   ✓ Successfully registered: {cjk_font_name}")
    else:
        print("   ✗ Failed to register CJK font")

    print("\n" + "=" * 60)
