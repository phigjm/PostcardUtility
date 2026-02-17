import fitz  # PyMuPDF
import os
from PIL import Image
import io
from pyzbar.pyzbar import decode
import sys
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
import tempfile


def extract_image_from_pdf(doc, xref):
    """
    Extrahiert ein einzelnes Bild aus dem PDF basierend auf xref.
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
        print(f"Fehler beim Extrahieren von Bild xref {xref}: {e}")
        return None


def decode_qr_from_pil_image(img_pil):
    """
    Dekodiert QR-Code aus einem PIL Image.
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
        print(f"Fehler beim Dekodieren: {e}")
        return None


def generate_qr_code_image(url, size=100):
    """
    Generiert ein QR-Code PIL Image für die gegebene URL mit transparentem Hintergrund.
    """
    qr_code = QrCodeWidget(url)
    bounds = qr_code.getBounds()
    qr_width = bounds[2] - bounds[0]
    qr_height = bounds[3] - bounds[1]
    
    d = Drawing(size, size, transform=[size/qr_width, 0, 0, size/qr_height, 0, 0])
    d.add(qr_code)
    
    # Create a temporary PDF to render the QR code
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_pdf.close()
    
    c = canvas.Canvas(temp_pdf.name, pagesize=(size, size))
    renderPDF.draw(d, c, 0, 0)
    c.save()
    
    # Convert PDF to PIL Image with alpha channel
    doc = fitz.open(temp_pdf.name)
    page = doc[0]
    pix = page.get_pixmap(alpha=True)  # Enable alpha channel for transparency
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    
    doc.close()
    try:
        os.unlink(temp_pdf.name)
    except OSError as e:
        print(f"Failed to cleanup temp PDF file: {e}")
    
    return img


def qr_code_postprocessor(input_pdf_path: str, placeholder_string: str, replacement_urls: list, output_pdf_path: str, pages_per_card=None):
    """
    Prozessiert ein PDF: Überprüft alle Bilder auf QR-Codes, ersetzt Bilder mit QR-Code containing placeholder_string
    mit generierten QR-Codes für die replacement_urls in Reihenfolge.
    pages_per_card: Anzahl Seiten pro Karte, None für alle Seiten als eine Karte.
    """
    doc = fitz.open(input_pdf_path)
    total_pages = len(doc)
    if pages_per_card is None:
        pages_per_card = total_pages
    num_cards = len(replacement_urls)
    matching_xrefs_per_card = [[] for _ in range(num_cards)]
    processed_xrefs = set()

    # Ersten Durchlauf: Alle QR-Codes analysieren und matching xrefs pro Karte identifizieren
    for page_num in range(total_pages):
        card_idx = page_num // pages_per_card
        if card_idx >= num_cards:
            continue
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img in image_list:
            xref = img[0]
            
            # QR-Code nur einmal pro xref dekodieren
            if xref not in processed_xrefs:
                img_pil = extract_image_from_pdf(doc, xref)
                if img_pil is None:
                    processed_xrefs.add(xref)
                    continue

                qr_data = decode_qr_from_pil_image(img_pil)
                
                print(f"QR-Code mit xref {xref} auf Seite {page_num + 1} enthält Platzhalter: {qr_data}")
                if qr_data and placeholder_string in qr_data:
                    matching_xrefs_per_card[card_idx].append((xref, page_num))
                    print(f"  -> Wird ersetzt für Karte {card_idx + 1}!")
                processed_xrefs.add(xref)

    # Zweiter Durchlauf: Alle Instanzen der matching xrefs pro Karte ersetzen
    replacements_made = 0
    for card_idx, xrefs in enumerate(matching_xrefs_per_card):
        if not xrefs:
            continue
        replacement_url = replacement_urls[card_idx]
        print(f"Ersetze QR-Codes für Karte {card_idx + 1} mit URL: {replacement_url}")
        
        for xref, page_num in xrefs:
            page = doc[page_num]
            img_rects = page.get_image_rects(xref)
            print(f"  Ersetze Bild xref {xref} auf Seite {page_num + 1}, {len(img_rects)} Instanzen")
            
            # Generiere QR-Code Bild
            qr_img = generate_qr_code_image(replacement_url, size=100)  # Größe anpassen
            
            for rect in img_rects:
                # Speichere temp Bild
                temp_img = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                qr_img.save(temp_img.name, 'PNG')
                temp_img.close()
                
                page.insert_image(rect, filename=temp_img.name, keep_proportion=False)
                os.unlink(temp_img.name)
                replacements_made += 1

    print(f"Insgesamt {replacements_made} Bild-Instanzen ersetzt")

    # Dritter Durchlauf: Alle ersetzten xrefs aus dem Dokument entfernen
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
    print(f"Verarbeitung abgeschlossen. Output: {output_pdf_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Verwendung: python qr_code_postprocessor.py <input_pdf>")
        sys.exit(1)

    input_pdf = sys.argv[1]
    replacement_png = "replacement.png"
    replacement_png = ".\\temp_images\\tmp1.png"
    #replacement_png = ".\\temp_images\\qrcode.png"
    output_pdf = "out.pdf"

    qr_code_postprocessor(input_pdf, replacement_png, output_pdf)