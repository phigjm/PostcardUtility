import fitz  # PyMuPDF
import re


def extract_addresses(pdf_path, page_number=1, bbox=None):
    """
    Extrahiert Text aus einer bestimmten Bounding Box einer PDF-Seite

    Args:
        pdf_path: Pfad zur PDF-Datei
        page_number: Seitennummer (0-basiert, also 1 für Seite 2)
        bbox: Bounding Box als Tuple (x0, y0, x1, y1) - wenn None, wird unten rechts verwendet

    Returns:
        Dictionary mit 'success' (bool) und 'addresses' (list) Keys
    """

    try:
        # PDF öffnen
        doc = fitz.open(pdf_path)

        if page_number >= len(doc):
            print(
                f"Seite {page_number + 1} existiert nicht. PDF hat nur {len(doc)} Seiten."
            )
            doc.close()
            return {"success": False, "address": ""}

        # Seite laden
        page = doc[page_number]

        if bbox is None:
            # unten rechts
            bbox = (
                page.rect.width * 0.5,
                page.rect.height * 0.5,
                page.rect.width,
                page.rect.height,
            )

        print(
            f"Verwende Bounding Box: ({bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f})"
        )

        # Text aus der Bounding Box extrahieren
        bbox_rect = fitz.Rect(bbox)
        text = page.get_text("text", clip=bbox_rect)

        doc.close()

        # Text bereinigen
        extracted_text = text.strip()

        # Remove descriptors like "Name:", "Street:", "Country:" etc.
        # Split into lines and process each line
        address_lines = extracted_text.splitlines()
        cleaned_lines = []

        # Common descriptor patterns to remove
        descriptors = [
            "name",
            "street",
            "address",
            "city",
            "town",
            "country",
            "zip",
            "postal",
            "state",
            "province",
            "region",
            "phone",
            "tel",
            "email",
            "mail",
        ]

        for line in address_lines:
            line = line.strip()

            # Check if line starts with a descriptor pattern (with or without colon)
            if ":" in line:
                # Get the part before the first colon
                prefix = line.split(":", 1)[0].strip().lower()
                # Check if prefix is a known descriptor
                if prefix in descriptors:
                    # Split at first colon and take the part after it
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        cleaned_line = parts[1].strip()
                        if cleaned_line:  # Only add non-empty lines
                            cleaned_lines.append(cleaned_line)
                else:
                    # Not a descriptor, keep the whole line
                    cleaned_lines.append(line)
            else:
                if False:  # disabled for the moment
                    # No colon - check if line starts with a descriptor word
                    words = line.split()
                    if len(words) >= 2:  # At least descriptor + content
                        first_word = words[0].lower()
                        if first_word in descriptors:
                            # Remove the first word (descriptor) and keep the rest
                            cleaned_line = " ".join(words[1:]).strip()
                            if cleaned_line:  # Only add non-empty lines
                                cleaned_lines.append(cleaned_line)
                        else:
                            # Not a descriptor, keep the whole line
                            cleaned_lines.append(line)
                else:
                    # Line too short or single word, keep as is
                    cleaned_lines.append(line)

        # Rejoin the cleaned lines
        extracted_text = "\n".join(cleaned_lines).strip()

        # split address in lines again for further processing
        address_lines = extracted_text.splitlines()
        # check if longer than 3 lines
        if len(address_lines) > 2:
            # check if last line is a country
            # check if first line contains a name and e.g. no number.
            if address_lines[0] and not any(
                char.isdigit() for char in address_lines[0]
            ):
                # First line seems to be a name and can be removed
                extracted_text = extracted_text.split("\n", 1)[-1].strip()

        # Prüfen ob eine Adresse gefunden wurde
        # Einfache Heuristik: mindestens 10 Zeichen und enthält Ziffern (für PLZ/Hausnummer)
        has_address = len(extracted_text) >= 10 and any(
            char.isdigit() for char in extracted_text
        )

        # Rückgabe im erwarteten Format
        if has_address and extracted_text:
            return {"success": True, "address": extracted_text}
        else:
            return {"success": False, "address": ""}

    except Exception as e:
        print(f"Fehler beim Extrahieren der Adresse: {str(e)}")
        return {"success": False, "address": ""}


if __name__ == "__main__":
    # Example usage
    # pdf_path = "path/to/your/pdf/file.pdf"
    # extracted_text = extract_address_from_bbox(pdf_path, page_number=1)
    # print("Extrahierter Text aus der Bounding Box:")
    # print("=" * 40)
    # print(extracted_text)
    # print("=" * 40)
    pass
