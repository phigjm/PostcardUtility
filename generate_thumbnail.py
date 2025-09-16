import fitz  # PyMuPDF


def generate_pdf_thumbnail(pdf_path, thumbnail_path, thumbnail_width=200):
    print("Generating thumbnail...", pdf_path, thumbnail_path)
    # Open the PDF file
    doc = fitz.open(pdf_path)

    # Load the first page (page numbering starts at 0)
    page = doc.load_page(0)

    # Calculate scale to maintain aspect ratio for the thumbnail width
    rect = page.rect
    scale = thumbnail_width / rect.width
    matrix = fitz.Matrix(scale, scale)

    # Render page to a pixmap with the scaling matrix
    pix = page.get_pixmap(matrix=matrix)

    # Save the thumbnail image
    pix.save(thumbnail_path)
    doc.close()
    print("Thumbnail saved to", thumbnail_path)


# Example usage
if __name__ == "__main__":

    generate_pdf_thumbnail(
        r"C:\Users\gjm\Projecte\PostCardDjango\media\postcards\tmp\out\preview_version.pdf",
        r"C:\Users\gjm\Projecte\PostCardDjango\media\postcards\tmp\out\thumbnail.png",
        thumbnail_width=200,
    )
