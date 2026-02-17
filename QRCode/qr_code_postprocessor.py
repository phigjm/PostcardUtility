import fitz  # PyMuPDF
import os
from PIL import Image
import io
from pyzbar.pyzbar import decode
import sys
import qrcode
import tempfile


def extract_image_from_pdf(doc, xref):
    """
    Extracts a single image from the PDF based on xref.
    """
    try:
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        img_pil = Image.open(io.BytesIO(image_bytes))

        # Handle smask if present
        if "smask" in base_image and base_image["smask"] != 0:
            smask_xref = base_image["smask"]
            smask_data = doc.extract_image(smask_xref)
            smask_bytes = smask_data["image"]
            mask_pil = Image.open(io.BytesIO(smask_bytes))
            if mask_pil.mode != 'L':
                mask_pil = mask_pil.convert('L')
            img_pil.putalpha(mask_pil)
        else:
            if img_pil.mode != 'RGB':
                img_pil = img_pil.convert('RGB')

        return img_pil
    except Exception as e:
        print(f"Error extracting image xref {xref}: {e}")
        return None


def decode_qr_from_pil_image(img_pil):
    """
    Decodes QR code from a PIL Image.
    """
    try:
        # Ensure RGB mode
        if img_pil.mode == 'RGBA':
            background = Image.new('RGB', img_pil.size, (255, 255, 255))
            background.paste(img_pil, mask=img_pil.split()[-1])
            img_pil = background
        elif img_pil.mode != 'RGB':
            img_pil = img_pil.convert('RGB')

        decoded_objects = decode(img_pil)
        if not decoded_objects:
            return None
        qr_data = decoded_objects[0].data.decode('utf-8')
        return qr_data
    except Exception as e:
        print(f"Error decoding: {e}")
        return None


def generate_qr_code_image(url):
    """
    Generates a QR code PIL Image for the given URL with transparent background.
    box_size=1 is a good compromise: large enough for good quality when stretching,
    but small enough for efficient file size.
    """
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=1,
        border=0,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="transparent")
    
    return img


def qr_code_postprocessor(input_pdf_path: str, placeholder_string: str, replacement_urls: list, output_pdf_path: str, pages_per_card=None):
    """
    Processes a PDF: Checks all images for QR codes, replaces images with QR codes containing placeholder_string
    with generated QR codes for the replacement_urls in order.
    pages_per_card: Number of pages per card, None for all pages as one card.
    """
    doc = fitz.open(input_pdf_path)
    total_pages = len(doc)
    if pages_per_card is None:
        pages_per_card = total_pages
    num_cards = len(replacement_urls)
    matching_xrefs_per_card = [[] for _ in range(num_cards)]
    processed_xrefs_per_card = [set() for _ in range(num_cards)]

    # First pass: Analyze all QR codes and identify matching xrefs per card
    for page_num in range(total_pages):
        card_idx = page_num // pages_per_card
        if card_idx >= num_cards:
            continue
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img in image_list:
            xref = img[0]
            
            # Decode QR code only once per xref per card
            if xref not in processed_xrefs_per_card[card_idx]:
                img_pil = extract_image_from_pdf(doc, xref)
                if img_pil is None:
                    processed_xrefs_per_card[card_idx].add(xref)
                    continue

                qr_data = decode_qr_from_pil_image(img_pil)
                
                print(f"QR code with xref {xref} on page {page_num + 1} contains placeholder: {qr_data}")
                if qr_data and placeholder_string in qr_data:
                    matching_xrefs_per_card[card_idx].append((xref, page_num))
                    print(f"  -> Will be replaced for card {card_idx + 1}!")
                processed_xrefs_per_card[card_idx].add(xref)

    # Second pass: Replace all instances of matching xrefs per card
    replacements_made = 0
    for card_idx, xrefs in enumerate(matching_xrefs_per_card):
        if not xrefs:
            continue
        replacement_url = replacement_urls[card_idx]
        print(f"Replacing QR codes for card {card_idx + 1} with URL: {replacement_url}")
        
        for xref, page_num in xrefs:
            page = doc[page_num]
            img_rects = page.get_image_rects(xref)
            print(f"  Replacing image xref {xref} on page {page_num + 1}, {len(img_rects)} instances")
            
            # Generate QR code image
            qr_img = generate_qr_code_image(replacement_url)
            
            for rect in img_rects:
                # Save temp image with optimized compression
                temp_img = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                qr_img.save(temp_img.name, 'PNG', optimize=True)
                temp_img.close()
                
                page.insert_image(rect, filename=temp_img.name, keep_proportion=False)
                os.unlink(temp_img.name)
                replacements_made += 1

    print(f"Total {replacements_made} image instances replaced")

    # Third pass: Remove all replaced xrefs from the document
    for xrefs in matching_xrefs_per_card:
        for xref, _ in xrefs:
            for page_num in range(total_pages):
                page = doc[page_num]
                try:
                    page.delete_image(xref)
                except:
                    pass  # Ignore if already deleted

    doc.save(output_pdf_path)
    doc.close()
    print(f"Processing completed. Output: {output_pdf_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python qr_code_postprocessor.py <input_pdf>")
        sys.exit(1)

    input_pdf = sys.argv[1]
    replacement_png = "replacement.png"
    replacement_png = ".\\temp_images\\tmp1.png"
    #replacement_png = ".\\temp_images\\qrcode.png"
    output_pdf = "out.pdf"

    qr_code_postprocessor(input_pdf, replacement_png, output_pdf)