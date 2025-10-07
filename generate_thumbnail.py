import fitz  # PyMuPDF


def generate_pdf_image(
    pdf_path,
    output_path,
    page_num=0,
    width=None,
    height=None,
    dpi=150,
    compression="jpeg",
    quality=95,
):
    """
    Generate an image from a PDF page with configurable resolution and compression.

    Args:
        pdf_path (str): Path to the PDF file
        output_path (str): Path where the image will be saved
        page_num (int): Page number to render (0-indexed)
        width (int, optional): Target width in pixels. If provided, height is calculated to maintain aspect ratio
        height (int, optional): Target height in pixels. If provided, width is calculated to maintain aspect ratio
        dpi (int): DPI for rendering (default: 150)
        compression (str): Image format/compression ("PNG", "JPEG", "WEBP", etc.)
        quality (int): JPEG quality (1-100, only applies to JPEG format)

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    print(f"Generating image from PDF page {page_num}...", pdf_path, "->", output_path)

    try:
        # Open the PDF file
        doc = fitz.open(pdf_path)

        # Check if page number is valid
        if page_num >= doc.page_count or page_num < 0:
            doc.close()
            return (
                False,
                f"Invalid page number {page_num}. PDF has {doc.page_count} pages.",
            )

        # Load the specified page
        page = doc.load_page(page_num)
        rect = page.rect

        # Calculate scaling matrix
        if width and height:
            # Use both dimensions (may distort aspect ratio)
            scale_x = width / rect.width
            scale_y = height / rect.height
            matrix = fitz.Matrix(scale_x, scale_y)
        elif width:
            # Scale by width, maintain aspect ratio
            scale = width / rect.width
            matrix = fitz.Matrix(scale, scale)
        elif height:
            # Scale by height, maintain aspect ratio
            scale = height / rect.height
            matrix = fitz.Matrix(scale, scale)
        else:
            # Use DPI to determine scale
            scale = dpi / 72.0  # 72 DPI is the default PDF resolution
            matrix = fitz.Matrix(scale, scale)

        # Render page to a pixmap with the scaling matrix
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        # Save with appropriate format and quality
        if compression.upper() == "JPEG" or compression.upper() == "JPG":
            pix.save(output_path, output="jpeg", jpg_quality=quality)
        elif compression.upper() == "PNG":
            pix.save(output_path, output="png")
        elif compression.upper() == "WEBP":
            pix.save(output_path, output="webp")
        else:
            # Default to JPEG for unknown formats
            pix.save(output_path, output="jpeg", jpg_quality=quality)

        doc.close()
        print(f"Image saved to {output_path}")
        return True, None

    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return False, str(e)


def generate_pdf_thumbnail(pdf_path, thumbnail_path, thumbnail_width=200):
    """
    Generate a thumbnail image from the first page of a PDF.

    Args:
        pdf_path (str): Path to the PDF file
        thumbnail_path (str): Path where the thumbnail will be saved
        thumbnail_width (int): Width of the thumbnail in pixels (default: 200)

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    return generate_pdf_image(
        pdf_path=pdf_path,
        output_path=thumbnail_path,
        page_num=0,
        width=thumbnail_width,
        compression="PNG",
    )


# Example usage
if __name__ == "__main__":

    generate_pdf_thumbnail(
        r"C:\Users\gjm\Projecte\PostCardDjango\media\postcards\tmp\out\preview_version.pdf",
        r"C:\Users\gjm\Projecte\PostCardDjango\media\postcards\tmp\out\thumbnail.png",
        thumbnail_width=200,
    )
