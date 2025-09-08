from reportlab.lib.pagesizes import A6, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from PIL import Image
import textwrap


def wrap_text_to_width(text, max_width, canvas_obj, font_name, font_size):
    """
    Wrap text to fit within max_width using actual character measurements.

    :param text: Text to wrap
    :param max_width: Maximum width in points
    :param canvas_obj: ReportLab canvas object for text measurement
    :param font_name: Font name
    :param font_size: Font size
    :return: List of wrapped lines
    """
    words = text.split()
    if not words:
        return [""]

    lines = []
    current_line = []

    def break_long_word(word, max_width):
        """Break a long word into parts that fit the width."""
        if canvas_obj.stringWidth(word, font_name, font_size) <= max_width:
            return [word]

        broken_parts = []
        current_part = ""

        for i, char in enumerate(word):
            test_part = current_part + char

            # Check if we need to add a hyphen (except for the last character)
            is_last_char = i == len(word) - 1
            if not is_last_char:
                test_width = canvas_obj.stringWidth(
                    test_part + "-", font_name, font_size
                )
            else:
                test_width = canvas_obj.stringWidth(test_part, font_name, font_size)

            if test_width <= max_width:
                current_part = test_part
            else:
                # Current part is full, finalize it
                if current_part:
                    # Add hyphen if this isn't the last part and part has more than 1 character
                    if not is_last_char and len(current_part) > 1:
                        broken_parts.append(current_part + "-")
                    else:
                        broken_parts.append(current_part)
                    current_part = char
                else:
                    # Single character exceeds width - force it anyway
                    broken_parts.append(char)
                    current_part = ""

        # Add the final part
        if current_part:
            broken_parts.append(current_part)

        return broken_parts

    for word in words:
        # Test if adding this word would exceed the width
        test_line = " ".join(current_line + [word])
        test_width = canvas_obj.stringWidth(test_line, font_name, font_size)

        if test_width <= max_width:
            current_line.append(word)
        else:
            # If current line has words, finalize it
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []

            # Check if the word itself is too long
            if canvas_obj.stringWidth(word, font_name, font_size) > max_width:
                # Break the long word
                broken_parts = break_long_word(word, max_width)

                # Add all but the last part as complete lines
                for part in broken_parts[:-1]:
                    lines.append(part)

                # The last part becomes the start of the next line
                if broken_parts:
                    current_line = [broken_parts[-1]]
            else:
                current_line = [word]

    # Add the last line if it has content
    if current_line:
        lines.append(" ".join(current_line))

    return lines


def generate_postcard(
    image_path,
    message,
    address,
    output_file="postcard.pdf",
    font_path="Helvetica",
    page_size=landscape(A6),
    border_thickness=5,
    show_debug_lines=False,
):
    """
    Generate a postcard PDF in landscape format.

    :param image_path: Path to the front image
    :param message: Text message for back
    :param address: Address string (multiline)
    :param output_file: Output PDF filename
    :param font_path: Path to TTF font or name of built-in font
    :param page_size: Page size tuple (default=A6 landscape)
    :param border_thickness: Border size in points
    :param show_debug_lines: Whether to show debugging boundary lines (default=False)
    """

    width, height = page_size

    # Register font if it's a TTF file
    if font_path.endswith(".ttf"):
        pdfmetrics.registerFont(TTFont("CustomFont", font_path))
        font_name = "CustomFont"
    else:
        font_name = font_path

    # Create canvas
    c = canvas.Canvas(output_file, pagesize=page_size)

    # --- FRONT SIDE ---
    img = Image.open(image_path)
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

    img = img.resize(
        (int(width - 2 * border_thickness), int(height - 2 * border_thickness))
    )

    img_reader = ImageReader(img)
    c.drawImage(
        img_reader,
        border_thickness,
        border_thickness,
        width - 2 * border_thickness,
        height - 2 * border_thickness,
    )

    # Draw white border
    c.setLineWidth(border_thickness)
    c.setStrokeColorRGB(1, 1, 1)  # white border
    c.rect(
        border_thickness / 2,
        border_thickness / 2,
        width - border_thickness,
        height - border_thickness,
    )

    c.showPage()

    # --- BACK SIDE ---
    margin = 10 * mm
    c.setFont(font_name, 12)

    # Message (left side)
    max_width = width / 2 - 2 * margin  # option to add margin -2*margin
    font_size = 12

    # Auto-shrink font size and line wrapping using actual character widths
    hight_margin = 1 * margin

    lines = message.splitlines()
    wrapped_lines = []
    while font_size > 6:
        c.setFont(font_name, font_size)
        wrapped_lines = []
        for line in lines:
            if line.strip():
                wrapped_lines.extend(
                    wrap_text_to_width(line, max_width, c, font_name, font_size)
                )
            else:
                wrapped_lines.append("")

        # Calculate total height needed
        line_height = font_size + 2
        total_text_height = len(wrapped_lines) * line_height

        if total_text_height < height - hight_margin:
            break
        font_size -= 1

    if len(wrapped_lines) * (font_size + 2) >= height - hight_margin:
        print("WARNING: Message too long to fit on postcard.")
        # Trim lines that overflow
        max_lines = int((height - hight_margin) / (font_size + 2))
        wrapped_lines = wrapped_lines[:max_lines]

    text_obj = c.beginText(margin, height - margin - font_size)
    text_obj.setFont(font_name, font_size)
    for line in wrapped_lines:
        text_obj.textLine(line)
    c.drawText(text_obj)

    # --- DEBUG: Draw boundary lines (optional) ---
    if show_debug_lines:
        c.setStrokeColorRGB(1, 0, 0)  # Red color for debug lines
        c.setLineWidth(0.5)

        # Draw margin boundaries
        c.rect(margin, margin, width - 2 * margin, height - 2 * margin)

        # Draw text area boundary (left side)
        text_area_width = max_width
        text_area_height = height - hight_margin
        c.rect(margin, margin, text_area_width, text_area_height)

        # Draw max width line for text
        c.line(margin + max_width, margin, margin + max_width, height - margin)

        # Draw height margin line
        c.line(margin, height - hight_margin, width / 2, height - hight_margin)

        # Label the boundaries
        c.setFont(font_name, 6)
        c.setFillColorRGB(1, 0, 0)  # Red text
        c.drawString(margin + 2, height - margin - 8, f"Margin: {margin/mm:.1f}mm")
        c.drawString(
            margin + max_width + 2,
            height - margin - 8,
            f"MaxWidth: {max_width/mm:.1f}mm",
        )
        c.drawString(
            margin + 2,
            height - hight_margin + 2,
            f"HeightMargin: {hight_margin/mm:.1f}mm",
        )
        c.drawString(margin + 2, margin + 2, f"FontSize: {font_size}pt")

        # Reset colors
        c.setStrokeColorRGB(0, 0, 0)  # Black
        c.setFillColorRGB(0, 0, 0)  # Black

    # Address (bottom right)
    addr_x = width / 2 + margin
    addr_y = margin + 40  # start above bottom margin
    c.setFont(font_name, 12)
    for line in address.split("\n"):
        c.drawString(addr_x, addr_y, line)
        addr_y += 14

    # Stamp box (top right)
    stamp_size = 30 * mm
    c.rect(
        width - margin - stamp_size,
        height - margin - stamp_size,
        stamp_size,
        stamp_size,
    )
    c.setFont(font_name, 8)
    c.drawCentredString(
        width - margin - stamp_size / 2, height - margin - stamp_size / 2, "STAMP"
    )

    # URL under stamp
    c.setFont(font_name, 10)
    c.drawRightString(
        width - margin, height - margin - stamp_size - 12, "ServiceCard.de"
    )

    # Divider line
    c.setStrokeColorRGB(0, 0, 0)  # reset to black
    c.line(width / 2, margin, width / 2, height - margin)

    # Save
    c.save()


# Example usage
if __name__ == "__main__":
    message = "4Greetings from the mountains! \n Wish you were here. \n \n asdlf alseiofn asdiofn asdfoi nweiofnasiofn owienf aaaaoiasdnfoiasdfnioasndfoiasdfnasoidfnaosidfnasdoifnaaa aaaaosidfoiasndfoinasdoifnasodifnaosidfnaosidfnaaa oiasdfn asdofn asdifnoasdnf oiasdfnoi nasidfo nasdiofna sdnfiasdf aaaaaaaaaaaaaaaaalasdkflöasdfkoiowenroaisnfojasdfoiasdfnasodfiaaaaaaaaaaaaa askdfaklsd foiansdfo isadnfoas difasof sdofinsdifnoi sdnfisndfo isdnf osdibf soidfi sdoifiosdfisodfo sdifods iofiosdfio sdiof isdfi sdif isddfoisoidf ois asdifo osadfn sidfno aisdfn asoidfn asoidfno asdifnasdoif nasdofn asdoifn asdoifn asdfoia asdkfkalsd asdfoi asdnf asodif asdfioasd foasdiof ioasdfio asidf ioasdfiaisdfioasdiofioasdfioioi iio ioasdiofiofi iosdfdio ifisdfio siodf ioiosdf iodisdiof io ioios fdioiosdfi iosidf i sdf ioasndf asdfi oisdfio sdiofio iosdiofi isdio iosdifo iosidfio isdfi iosdiof isdi iosdfio iosdfiid siofi isdiof iosiodf iosdiof iosdif iosdfio isdfio oisdfio ioios difoiosdiofi sidfio isdfinoisdfn sonidf nsoifdi osifd iosdiof isidfoi oisdfio sidofi osdfioi osdiof iosdfio iosif iosdfio iosdf sdf"
    print(message)

    generate_postcard(
        image_path="Examples/example.jpg",
        message=message,
        address="John Doe\n123 Main Street\n12345 Hometown\nCountry",
        output_file="Examples/postcard.pdf",
        font_path="Helvetica",  # or provide a .ttf file
        show_debug_lines=True,  # Set to True to show boundary lines for debugging
    )
