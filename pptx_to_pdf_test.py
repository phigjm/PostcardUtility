#!/usr/bin/env python3
"""
Test script for PowerPoint to PDF conversion
"""

import os
import sys
from pdfutilities.pptx_to_pdf import ppt_to_pdf


def test_conversion():
    """Test the PowerPoint to PDF conversion"""
    print("Testing PowerPoint to PDF conversion...")

    # Check if PowerPoint file exists
    test_file = "Examples/PostkartenVorlage.pptx"
    if not os.path.exists(test_file):
        print(f"Test file '{test_file}' not found in current directory.")
        print("Available files:")
        for file in os.listdir("."):
            if file.endswith(".pptx"):
                print(f"  - {file}")
        return False

    # Test conversion
    output_file = "Examples/test_output.pdf"
    try:
        print(f"Converting {test_file} to {output_file}...")
        ppt_to_pdf(test_file, output_file)

        if os.path.exists(output_file):
            print(f"✓ Conversion successful! Output saved as {output_file}")
            file_size = os.path.getsize(output_file)
            print(f"  File size: {file_size} bytes")
            return True
        else:
            print("✗ Conversion failed - output file not created")
            return False

    except Exception as e:
        print(f"✗ Conversion failed with error: {e}")
        return False


if __name__ == "__main__":
    success = test_conversion()
    sys.exit(0 if success else 1)
