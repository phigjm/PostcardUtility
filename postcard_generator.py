from reportlab.lib.pagesizes import A6, A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from PIL import Image
import os
from pypdf import PdfReader, PdfWriter

# Try relative import first (when used as module), fall back to direct import (when run standalone)
try:
    from .postcard_generate_text_side import generate_back_side
except ImportError:
    from postcard_generate_text_side import generate_back_side


def register_font(font_path):
    """
    Register a font and return the font name to use.

    :param font_path: Path to TTF/OTF font file or name of built-in font
    :return: Font name string
    """
    if font_path.endswith((".ttf", ".otf")):
        try:
            # Check if font file exists
            if not os.path.exists(font_path):
                print(f"WARNING: Font file not found: {font_path}")
                print("Available built-in fonts: Helvetica, Times-Roman, Courier")
                font_name = "Helvetica"  # Fallback to built-in font
            else:
                pdfmetrics.registerFont(TTFont("CustomFont", font_path))
                font_name = "CustomFont"
                print(f"Successfully loaded font: {font_path}")
        except Exception as e:
            print(f"ERROR loading font {font_path}: {e}")
            print("Falling back to Helvetica")
            font_name = "Helvetica"
    else:
        # Assume it's a built-in font name
        font_name = font_path

    return font_name


def generate_front_side(
    c,
    image_path,
    page_size,
    border_thickness=5,
    auto_rotate_image=True,
):
    """
    Generate the front side (image side) of a postcard on an existing canvas.

    :param c: ReportLab canvas object
    :param image_path: Path to the front image
    :param page_size: Page size tuple (width, height)
    :param border_thickness: Border size in points (default=5)
    :param auto_rotate_image: Automatically rotate portrait images to landscape (default=True)
    """
    width, height = page_size

    # Load and prepare image
    img = Image.open(image_path)

    # Automatically rotate to landscape if image is in portrait
    if auto_rotate_image and img.height > img.width:
        img = img.rotate(90, expand=True)

    img_ratio = img.width / img.height
    page_ratio = width / height

    # Crop to match aspect ratio
    if img_ratio > page_ratio:
        new_width = int(img.height * page_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        new_height = int(img.width / page_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    # Draw image
    img_reader = ImageReader(img)
    c.drawImage(
        img_reader,
        border_thickness,
        border_thickness,
        width - 2 * border_thickness,
        height - 2 * border_thickness,
    )

    # Draw white border
    if border_thickness > 0:
        c.setLineWidth(border_thickness)
        c.setStrokeColorRGB(1, 1, 1)  # white border
        c.rect(
            border_thickness / 2,
            border_thickness / 2,
            width - border_thickness,
            height - border_thickness,
        )


def generate_postcard(
    image_path,
    message,
    address,
    output_file="postcard.pdf",
    font_path=r"C:\Users\gjm\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
    page_size=landscape(A4),
    border_thickness=5,
    show_debug_lines=False,
    message_area_ratio=0.5,  # Anteil des Messagebereichs (z.B. 0.6 für 3/5 links)
    auto_rotate_image=True,
):
    """
    Generate a complete postcard PDF with front (image/PDF) and back (text) sides.

    :param image_path: Path to the front image or PDF file
    :param message: Text message for back
    :param address: Address string (multiline)
    :param output_file: Output PDF filename
    :param font_path: Path to TTF/OTF font file or name of built-in font
    :param page_size: Page size tuple (default=A4 landscape)
    :param border_thickness: Border size in points (default=5)
    :param show_debug_lines: Whether to show debugging boundary lines (default=False)
    :param message_area_ratio: Ratio of message area width (default=0.5 for 50%)
    :param auto_rotate_image: Automatically rotate portrait images to landscape (default=True)
    """
    width, height = page_size

    # Check if input is a PDF or an image
    is_pdf_input = image_path.lower().endswith(".pdf")

    if is_pdf_input:
        # PDF input: merge existing PDF with generated text side
        # Register font
        font_name = register_font(font_path)

        # Create temporary file for text side
        import tempfile

        temp_text_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_text_pdf.close()

        # Generate only the text side
        c = canvas.Canvas(temp_text_pdf.name, pagesize=page_size)
        generate_back_side(
            c=c,
            message=message,
            address=address,
            font_name=font_name,
            page_size=page_size,
            show_debug_lines=show_debug_lines,
            message_area_ratio=message_area_ratio,
        )
        c.save()

        # Merge the input PDF with the generated text side
        pdf_writer = PdfWriter()

        # Add the front side from input PDF (first page only)
        with open(image_path, "rb") as front_pdf_file:
            pdf_reader = PdfReader(front_pdf_file)
            pdf_writer.add_page(pdf_reader.pages[0])

        # Add the text side
        with open(temp_text_pdf.name, "rb") as text_pdf_file:
            pdf_reader = PdfReader(text_pdf_file)
            pdf_writer.add_page(pdf_reader.pages[0])

        # Write the merged PDF
        with open(output_file, "wb") as output_pdf_file:
            pdf_writer.write(output_pdf_file)

        # Clean up temporary file
        os.unlink(temp_text_pdf.name)

        print(f"Postcard generated successfully (PDF merged): {output_file}")

    else:
        # Image input: generate both sides
        # Register font
        font_name = register_font(font_path)

        # Create canvas
        c = canvas.Canvas(output_file, pagesize=page_size)

        # --- FRONT SIDE ---
        generate_front_side(
            c=c,
            image_path=image_path,
            page_size=page_size,
            border_thickness=border_thickness,
            auto_rotate_image=auto_rotate_image,
        )

        c.showPage()

        # --- BACK SIDE ---
        generate_back_side(
            c=c,
            message=message,
            address=address,
            font_name=font_name,
            page_size=page_size,
            show_debug_lines=show_debug_lines,
            message_area_ratio=message_area_ratio,
        )

        # Save PDF
        c.save()
        print(f"Postcard generated successfully: {output_file}")


# Example usage
if __name__ == "__main__":
    message = "4Greetings from the mountains! \n Wish you were here. \n \n asdlf alseiofn asdiofn asdfoi nweiofnasiofn owienf aaaaoiasdnfoiasdfnioasndfoiasdfnasoidfnaosidfnasdoifnaaa aaaaosidfoiasndfoinasdoifnasodifnaosidfnaosidfnaaa oiasdfn asdofn asdifnoasdnf oiasdfnoi nasidfo nasdiofna sdnfiasdf aaaaaaaaaaaaaaaaalasdkflöasdfkoiowenroaisnfojasdfoiasdfnasodfiaaaaaaaaaaaaa askdfaklsd foiansdfo isadnfoas difasof sdofinsdifnoi sdnfisndfo isdnf osdibf soidfi sdoifiosdfisodfo sdifods iofiosdfio sdiof isdfi sdif isddfoisoidf ois asdifo osadfn sidfno aisdfn asoidfn asoidfno asdifnasdoif nasdofn asdoifn asdoifn asdfoia asdkfkalsd asdfoi asdnf asodif asdfioasd foasdiof ioasdfio asidf ioasdfiaisdfioasdiofioasdfioioi iio ioasdiofiofi iosdfdio ifisdfio siodf ioiosdf iodisdiof io ioios fdioiosdfi iosidf i sdf ioasndf asdfi oisdfio sdiofio iosdiofi isdio iosdifo iosidfio isdfi iosdiof isdi iosdfio iosdfiid siofi isdiof iosiodf iosdiof iosdif iosdfio isdfio oisdfio ioios difoiosdiofi sidfio isdfinoisdfn sonidf nsoifdi osifd iosdiof isidfoi oisdfio sidofi osdfioi osdiof iosdfio iosif iosdfio iosdf sdf"
    message = """Liebe Alina,

ich möchte dir von Herzen mein tiefstes Beileid zum Verlust deiner Mama aussprechen. Ich kann mir nur annähernd vorstellen, wie schwer dieser Abschied für dich sein muss. Deine Mutter war ein wichtiger Teil deines Lebens, und es ist unendlich schwer, so einen geliebten Menschen loslassen zu müssen.
"""
    # print(message)

    message = "sadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdf32343452345234523452345234523452345234523452345234523452345234523453245234523452345234523452345234523452345234523452345234523452345234523452345sadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdf32343452345234523452345234523452345234523452345234523452345234523453245234523452345234523452345234523452345234523452345234523452345234523452345sadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfasdfasdfalksdfklasdkfaskdflkasdfkasdfsadfasdflasdfa"
    message += message + message + message + message + message  # Test very long message
    message += message + message + message + message + message  # Test very long message

    print("längth message", len(message))
    folder = r"C:\Users\gjm\Projecte\PostCardDjango\media\misc\tmp\test_cards\\"

    # Example 1: Using an image as front side
    generate_postcard(
        # image_path=r"C:\Users\gjm\Projecte\PostCardDjango\media\postcards\tmp\i-311.jpeg",
        # image_path=r"C:\Users\gjm\Downloads\IMG_20250912_141205_773.jpg",
        image_path=r"C:\Users\gjm\Downloads\dc_grafiktest (1).pdf",
        message=message,
        address="John Doe\n123 Main Street\n12345 Hometown\nCountry",
        output_file=folder + "postcard.pdf",
        font_path=r"C:\Users\gjm\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
        show_debug_lines=False,  # Set to True to show boundary lines for debugging
        border_thickness=0,
    )

    # Example 2: Using a PDF as front side (will be merged with text side)
    # generate_postcard(
    #     image_path=r"C:\Users\gjm\Projecte\PostCardDjango\media\postcards\tmp\front_design.pdf",
    #     message="Hello from the mountains!",
    #     address="Jane Smith\n456 Oak Avenue\n54321 Cityville\nCountry",
    #     output_file=folder + "postcard_with_pdf_front.pdf",
    #     font_path=r"C:\Users\gjm\Projecte\PostCardDjango\static\fonts\Handlee.ttf",
    #     show_debug_lines=False,
    # )

    from postprocessor import process_postcard

    process_postcard(
        folder + "postcard.pdf",
        folder + "print_version.pdf",
        folder + "preview_version.pdf",
    )
