from crop_to_size import process_pdf_for_print
from draw_bleed_area import draw_cutting_area
from set_crop_markers import add_crop_marks_to_pdf
import postcardformats
from convert_CMYK import convertPDFtoCMYK


def process_postcard(input_pdf, printversion_pdf, preview_version_pdf):

    process_pdf_for_print(
        input_path=input_pdf,
        output_path=printversion_pdf,
        target_width_mm=postcardformats.get_default_postcard_size()[0],
        target_height_mm=postcardformats.get_default_postcard_size()[1],
        target_width_mm_with_bleeding=postcardformats.get_default_postcard_size_with_bleeding()[
            0
        ],
        target_height_mm_with_bleeding=postcardformats.get_default_postcard_size_with_bleeding()[
            1
        ],
    )

    # todo convert cmyk
    if True:  # dosnt work well yet

        try:
            convertPDFtoCMYK(printversion_pdf)
            print(f"Converted {printversion_pdf} to CMYK")
        except Exception as e:
            print(f"Error converting to CMYK: {e}")
            # stacktrace
            import traceback

            traceback.print_exc()

    draw_cutting_area(
        pdf_input=printversion_pdf,
        pdf_output=preview_version_pdf,
        cut_edge_x_mm=postcardformats.get_default_cutting_size()[0],
        cut_edge_y_mm=postcardformats.get_default_cutting_size()[1],
        tolerances_mm=3,
    )
    add_crop_marks_to_pdf(
        input_pdf_path=printversion_pdf,
        output_pdf_path=printversion_pdf,
        bleed_area_width_mm=postcardformats.get_default_cutting_size()[0],
        bleed_area_height_mm=postcardformats.get_default_cutting_size()[1],
    )


if __name__ == "__main__":
    input_pdf = "Examples/postcard.pdf"
    input_pdf = r"C:\Users\gjm\Projecte\PostCard\Ablauf\FehlendeJoeDipperKarte.pdf"
    printversion_pdf = "Examples/postcard_for_print.pdf"
    preview_version_pdf = "Examples/postcard_with_cutting.pdf"
    process_postcard(input_pdf, printversion_pdf, preview_version_pdf)
    print(
        f"Postcard {input_pdf} processed and saved to {printversion_pdf} and {preview_version_pdf}"
    )
