import fitz  # PyMuPDF
import os
from PIL import Image
import io
from pyzbar.pyzbar import decode
import sys


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


def qr_code_postprocessor(input_pdf_path: str, replacement_image_path: str, output_pdf_path: str):
    """
    Prozessiert ein PDF: Überprüft alle Bilder auf QR-Codes, ersetzt Bilder mit QR-Code "weriosdisos" mit replacement.png,
    löscht die Originalbilder und speichert als out.pdf.
    """
    if not os.path.exists(replacement_image_path):
        print(f"Replacement image {replacement_image_path} not found.")
        return

    doc = fitz.open(input_pdf_path)
    matching_xrefs = set()
    processed_xrefs = set()

    # Ersten Durchlauf: Alle QR-Codes analysieren und matching xrefs identifizieren
    for page_num in range(len(doc)):
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
                if qr_data:
                    print(f"QR-Code mit xref {xref}: {qr_data}")
                    if "whatsapp.com" in qr_data:  # Test mit vorhandenem QR-Code
                        matching_xrefs.add(xref)
                        print(f"  -> Wird ersetzt!")
                else:
                    print(f"Kein QR-Code in Bild xref {xref}")
                processed_xrefs.add(xref)

    if not matching_xrefs:
        print("Keine QR-Codes mit 'weriosdisos' gefunden.")
        doc.close()
        return

    # Zweiter Durchlauf: Alle Instanzen der matching xrefs ersetzen
    replacements_made = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img in image_list:
            xref = img[0]
            if xref in matching_xrefs:
                # Alle Rechtecke für dieses Bild auf dieser Seite holen
                img_rects = page.get_image_rects(xref)
                print(f"Ersetze Bild xref {xref} auf Seite {page_num + 1}, {len(img_rects)} Instanzen")
                
                for rect in img_rects:
                    page.insert_image(rect, filename=replacement_image_path, keep_proportion=False)
                    replacements_made += 1

    print(f"Insgesamt {replacements_made} Bild-Instanzen ersetzt")

    # Dritter Durchlauf: Alle ersetzten xrefs aus dem Dokument entfernen
    for page_num in range(len(doc)):
        page = doc[page_num]
        for xref in matching_xrefs:
            page.delete_image(xref)

    doc.save(output_pdf_path)
    doc.close()
    print(f"Verarbeitung abgeschlossen. Output: {output_pdf_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Verwendung: python qr_code_postprocessor.py <input_pdf>")
        sys.exit(1)

    input_pdf = sys.argv[1]
    replacement_png = "replacement.png"
    output_pdf = "out.pdf"

    qr_code_postprocessor(input_pdf, replacement_png, output_pdf)