#!/usr/bin/env python3
"""
Standalone script to convert PowerPoint template to multiple formats (ODP and PDF)
Usage: python convert_templates.py [input_pptx_file]

If no input file is specified, it defaults to: ../../static/templates/Size154x111mm.pptx
"""

import comtypes.client
import comtypes
import os
import sys
import argparse


def ppt_to_pdf(input_file, output_file):
    """
    Convert PowerPoint file to PDF using COM automation.

    Args:
        input_file (str): Path to the input PowerPoint file
        output_file (str): Path to the output PDF file
    """
    # Initialize COM
    comtypes.CoInitialize()

    try:
        PP_FORMAT_PDF = 32  # PDF format constant

        # Ensure paths are absolute
        input_file = os.path.abspath(input_file)
        output_file = os.path.abspath(output_file)

        # Create PowerPoint application
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        powerpoint.Visible = 1  # Keep PowerPoint visible for debugging

        try:
            # Open presentation
            presentation = powerpoint.Presentations.Open(input_file)

            # Save as PDF
            presentation.SaveAs(output_file, PP_FORMAT_PDF)
            print(f"✓ PDF created: {output_file}")

            # Close presentation
            presentation.Close()

        except Exception as e:
            # If PowerPoint is open, try to quit gracefully
            try:
                if "powerpoint" in locals():
                    powerpoint.Quit()
            except:
                pass
            raise e

        # Quit PowerPoint
        powerpoint.Quit()

    finally:
        # Always uninitialize COM
        comtypes.CoUninitialize()


def ppt_to_odp(input_file, output_file):
    """
    Convert PowerPoint file to ODP (OpenDocument Presentation) using COM automation.

    Args:
        input_file (str): Path to the input PowerPoint file
        output_file (str): Path to the output ODP file
    """
    # Initialize COM
    comtypes.CoInitialize()

    try:
        PP_FORMAT_ODP = 35  # ODP format constant (OpenDocument Presentation)

        # Ensure paths are absolute
        input_file = os.path.abspath(input_file)
        output_file = os.path.abspath(output_file)

        # Create PowerPoint application
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        powerpoint.Visible = 1  # Keep PowerPoint visible for debugging

        try:
            # Open presentation
            presentation = powerpoint.Presentations.Open(input_file)

            # Save as ODP
            presentation.SaveAs(output_file, PP_FORMAT_ODP)
            print(f"✓ ODP created: {output_file}")

            # Close presentation
            presentation.Close()

        except Exception as e:
            # If PowerPoint is open, try to quit gracefully
            try:
                if "powerpoint" in locals():
                    powerpoint.Quit()
            except:
                pass
            raise e

        # Quit PowerPoint
        powerpoint.Quit()

    finally:
        # Always uninitialize COM
        comtypes.CoUninitialize()


def convert_template(input_pptx):
    """
    Convert a PowerPoint template to both ODP and PDF formats.

    Args:
        input_pptx (str): Path to the input PPTX file
    """
    if not os.path.exists(input_pptx):
        print(f"❌ Error: Input file '{input_pptx}' not found!")
        return False

    if not input_pptx.lower().endswith('.pptx'):
        print(f"❌ Error: Input file must be a .pptx file!")
        return False

    # Get the base name without extension
    base_name = os.path.splitext(input_pptx)[0]
    base_dir = os.path.dirname(input_pptx)

    # Output file paths
    pdf_output = os.path.join(base_dir, f"{os.path.basename(base_name)}.pdf")
    odp_output = os.path.join(base_dir, f"{os.path.basename(base_name)}.odp")

    print(f"🔄 Converting {input_pptx}...")
    print(f"📁 Output directory: {base_dir}")

    try:
        # Convert to PDF
        ppt_to_pdf(input_pptx, pdf_output)

        # Convert to ODP
        ppt_to_odp(input_pptx, odp_output)

        print("✅ Conversion completed successfully!")
        print(f"📄 PDF: {pdf_output}")
        print(f"📊 ODP: {odp_output}")

        return True

    except Exception as e:
        print(f"❌ Error during conversion: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Convert PowerPoint template to PDF and ODP formats')
    parser.add_argument('input_file', nargs='?', default='../../static/templates/Size154x111mm.pptx',
                       help='Path to the input PPTX file (default: ../../static/templates/Size154x111mm.pptx)')

    args = parser.parse_args()

    print("🎯 PowerPoint Template Converter")
    print("=" * 40)
    print(f"📂 Using template: {args.input_file}")

    success = convert_template(args.input_file)

    if success:
        print("\n🎉 All conversions completed successfully!")
        return 0
    else:
        print("\n💥 Conversion failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())