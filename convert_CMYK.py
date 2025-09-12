import subprocess
import os
import tempfile
import shutil


args_hq = [
    "-sDEVICE=pdfwrite",
    "-dUseBleedBox",
    "-dQUIET",
    "-dPDFSETTINGS=/prepress",  # Higher quality setting
    "-dDetectDuplicateImages",
    "-dAutoFilterColorImages=false",
    "-dAutoFilterGrayImages=false",
    "-dColorImageFilter=/FlateEncode",
    "-dGrayImageFilter=/FlateEncode",
    "-dDownsampleMonoImages=false",
    "-dDownsampleGrayImages=false",
    "-dColorImageResolution=300",
    "-dGrayImageResolution=300",
    "-dCompressPages=true",
    "-dSubsetFonts=true",
    "-sProcessColorModel=DeviceCMYK",
    "-sColorConversionStrategy=CMYK",
    "-sColorConversionStrategyForImages=CMYK",
    "-dCompatibilityLevel=1.4",
    "-dNOPAUSE",
    "-dBATCH",
]

args_minimum = [
    "-sDEVICE=pdfwrite",
    "-dColorConversionStrategy=/CMYK",
    "-dProcessColorModel=/DeviceCMYK",
    "-sColorConversionStrategyForImages=CMYK",
    "-dCompatibilityLevel=1.4",
    "-dNOPAUSE",
    "-dBATCH",
]


def convertPDFtoCMYK(pdf_in, pdf_out=None):
    # convert pdf_in to absolute path
    pdf_in = os.path.abspath(pdf_in)

    # If pdf_out is None, we need to replace the original file
    # Since Ghostscript doesn't allow same input/output, use temp file
    replace_original = pdf_out is None
    if replace_original:
        # Create a temporary file for output
        temp_fd, pdf_out = tempfile.mkstemp(suffix=".pdf")
        os.close(temp_fd)  # Close the file descriptor, we only need the path

    gs_path = "gswin64c.exe"  # Adjust to your GhostScript executable path if needed

    quality_args = args_hq

    args = [
        gs_path,
        "-o",
        pdf_out,
        *quality_args,  # Use high quality settings
        r"-f",
        pdf_in,  # Input file prefixed with -f
    ]

    # print the command for debugging
    print("Running command:", " ".join(args))

    try:
        val = subprocess.run(args, check=True)
        print("val", val)

        # If we're replacing the original file, move temp file to original location
        if replace_original:
            shutil.move(pdf_out, pdf_in)
            pdf_out = pdf_in

        print(f"Converted {pdf_in} to CMYK and saved as {pdf_out}")
    except Exception as e:
        # Clean up temp file if something went wrong
        if replace_original and os.path.exists(pdf_out):
            os.remove(pdf_out)
        raise e

    return pdf_out


if __name__ == "__main__":
    input_pdf = "Examples/postcard.pdf"
    input_pdf = r"C:\Users\gjm\Projecte\PostCard\Examples\print_version.pdf"
    convertPDFtoCMYK(input_pdf)
