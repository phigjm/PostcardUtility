import comtypes.client
import comtypes
import os


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
        PP_FORMAT_PDF = 32  # https://learn.microsoft.com/en-us/office/vba/api/powerpoint.ppsaveasfiletype

        # Ensure paths are absolute
        input_file = os.path.abspath(input_file)
        output_file = os.path.abspath(output_file)

        # Create PowerPoint application
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        powerpoint.Visible = 1  # Keep PowerPoint hidden for server use

        try:
            # Open presentation
            presentation = powerpoint.Presentations.Open(input_file)

            # Save as PDF
            presentation.SaveAs(output_file, PP_FORMAT_PDF)

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
        # powerpoint.Quit()

    finally:
        # Always uninitialize COM
        comtypes.CoUninitialize()
