import subprocess
import os


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

    if pdf_out is None:
        pdf_out = os.path.splitext(pdf_in)[0] + "_CMYK.pdf"
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

    val = subprocess.run(args, check=True)
    print("val", val)
    print(f"Converted {pdf_in} to CMYK and saved as {pdf_out}")

    return pdf_out


if __name__ == "__main__":
    input_pdf = "Examples/postcard.pdf"
    input_pdf = r"C:\Users\gjm\Projecte\PostCard\Examples\print_version.pdf"
    convertPDFtoCMYK(input_pdf)
