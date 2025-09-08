from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from combine_pdfs import combine_double_sided_pdfs, print_layout_example


def test_different_layouts():
    """Testet verschiedene Layouts um das Flippen zu validieren"""

    pdf_files = [
        r"Examples/postcard1.pdf",
        r"Examples/postcard2.pdf",
        r"Examples/postcard3.pdf",
        r"Examples/postcard4.pdf",
        r"Examples/postcard5.pdf",
        r"Examples/postcard6.pdf",
        r"Examples/postcard7.pdf",
        r"Examples/postcard8.pdf",
    ]

    # Test verschiedene Layouts
    layouts_to_test = [
        ((2, 2), "2x2 Layout (Quadrat)"),
        ((2, 3), "2x3 Layout (Hochformat)"),
        ((2, 4), "2x4 Layout (Hochformat)"),
        ((3, 2), "3x2 Layout (Querformat)"),
        ((4, 2), "4x2 Layout (Querformat)"),
    ]

    print("=== Layout Tests ===")

    for layout, description in layouts_to_test:
        print(f"\n--- {description} ---")

        # Zeige Layout-Beispiel
        print_layout_example(layout, flip_on_short_edge=False)

        # Teste beide Flip-Modi
        for flip_mode in [False, True]:
            flip_desc = "lange_seite" if not flip_mode else "kurze_seite"
            output_file = f"Examples/test_{layout[0]}x{layout[1]}_{flip_desc}.pdf"

            print(f"\nTeste {description} mit flip_on_short_edge={flip_mode}")

            try:
                success = combine_double_sided_pdfs(
                    pdf_files[: layout[0] * layout[1]],
                    output_file,
                    layout=layout,
                    flip_on_short_edge=flip_mode,
                )

                if success:
                    print(f"✅ Erfolgreich: {output_file}")
                else:
                    print(f"❌ Fehler bei: {output_file}")

            except Exception as e:
                print(f"❌ Exception bei {output_file}: {e}")


def merge_two_pages_side_by_side(input_path, output_path):
    reader = PdfReader(input_path)
    if len(reader.pages) != 2:
        raise ValueError("Input PDF must have exactly 2 pages.")

    page1 = reader.pages[0]
    page2 = reader.pages[1]

    width = float(page1.mediabox.width)
    height = float(page1.mediabox.height)

    # Create new blank page with double width
    writer = PdfWriter()
    new_page = writer.add_blank_page(width=2 * width, height=height)

    # Merge first page at (0, 0)
    new_page.merge_transformed_page(page1, Transformation().translate(tx=0, ty=0))

    # Merge second page shifted right by width
    new_page.merge_transformed_page(page2, Transformation().translate(tx=width, ty=0))

    # Write output PDF
    with open(output_path, "wb") as f_out:
        writer.write(f_out)


if __name__ == "__main__":
    test_different_layouts()
