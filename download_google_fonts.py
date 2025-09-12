#!/usr/bin/env python3
"""
Script to download Google Fonts and save them locally.
This ensures consistent rendering in PDFs.
"""

import os
import requests
import json
from pathlib import Path

# Google Fonts API key (you can get this free from Google Cloud Console)
# For now, we'll use direct download URLs
GOOGLE_FONTS = {
    "Handlee": "https://fonts.gstatic.com/s/handlee/v14/T3dUUJcGnHzKE2MYNXHmBt0VkN8.woff2",
    "Open Sans": "https://fonts.gstatic.com/s/opensans/v34/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsjZ0B4gaVI.woff2",
    "Lato": "https://fonts.gstatic.com/s/lato/v24/S6uyw4BMUTPHjx4wXiWtFCfQ7A.woff2",
    "Roboto": "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxKKTU1Kg.woff2",
    "Zeyada": "https://fonts.gstatic.com/s/zeyada/v18/C1tGsVw2DyhfxOGZk2ysJHKq.woff2",
    "Sacramento": "https://fonts.gstatic.com/s/sacramento/v13/LmnJBxE6qIHJ-Qw4UpZ0mNV1cjM.woff2",
    "Cookie": "https://fonts.gstatic.com/s/cookie/v19/W1xZcAP6l_LpQqAgQCrJJw.woff2",
    "Coming Soon": "https://fonts.gstatic.com/s/comingsoon/v20/yYbOkOlEe2EMJC8xxlH2ZQ.woff2",
    "Dawning of a New Day": "https://fonts.gstatic.com/s/dawningofanewday/v16/Xkuy0rXTzbYwGrwFtqxpYHIoNTJCN4qQP_UW4IwpA4kXIK9l.woff2",
    "Fuzzy Bubbles": "https://fonts.gstatic.com/s/fuzzybubbles/v5/Q0a_KbMhEIfLKwJKtBvfTlOcP7cQ8a8kWJj9W-OzUA.woff2",
}

# TTF versions for better PDF support
GOOGLE_FONTS_TTF = {
    "Handlee": "https://github.com/google/fonts/raw/main/ofl/handlee/Handlee-Regular.ttf",
    "Open Sans": "https://github.com/google/fonts/raw/main/apache/opensans/OpenSans%5Bwdth,wght%5D.ttf",
    "Lato": "https://github.com/google/fonts/raw/main/ofl/lato/Lato-Regular.ttf",
    "Roboto": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto%5Bwdth,wght%5D.ttf",
    "Zeyada": "https://github.com/google/fonts/raw/main/ofl/zeyada/Zeyada-Regular.ttf",
    "Sacramento": "https://github.com/google/fonts/raw/main/ofl/sacramento/Sacramento-Regular.ttf",
    "Cookie": "https://github.com/google/fonts/raw/main/ofl/cookie/Cookie-Regular.ttf",
    "Coming Soon": "https://github.com/google/fonts/raw/main/apache/comingsoon/ComingSoon.ttf",
    "Dawning of a New Day": "https://github.com/google/fonts/raw/main/ofl/dawningofanewday/DawningofaNewDay.ttf",
    "Fuzzy Bubbles": "https://github.com/google/fonts/raw/main/ofl/fuzzybubbles/FuzzyBubbles-Regular.ttf",
}


def download_font(name, url, output_dir):
    """Download a font file from URL"""
    try:
        print(f"Downloading {name}...")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # Create safe filename
        safe_name = name.replace(" ", "_").replace("/", "_")
        if url.endswith(".ttf"):
            filename = f"{safe_name}.ttf"
        elif url.endswith(".woff2"):
            filename = f"{safe_name}.woff2"
        else:
            # Try to guess from content-type or default to ttf
            filename = f"{safe_name}.ttf"

        filepath = output_dir / filename

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"✓ Downloaded {name} to {filepath}")
        return True
    except Exception as e:
        print(f"✗ Failed to download {name}: {e}")
        return False


def main():
    # Create fonts directory
    script_dir = Path(__file__).parent
    fonts_dir = script_dir / "fonts" / "google"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading Google Fonts to: {fonts_dir}")

    success_count = 0
    total_count = len(GOOGLE_FONTS_TTF)

    for name, url in GOOGLE_FONTS_TTF.items():
        if download_font(name, url, fonts_dir):
            success_count += 1

    print(
        f"\nDownload complete: {success_count}/{total_count} fonts downloaded successfully"
    )

    # List downloaded files
    print("\nDownloaded files:")
    for file in fonts_dir.glob("*"):
        if file.is_file():
            print(f"  - {file.name}")


if __name__ == "__main__":
    main()
