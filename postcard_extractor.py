import fitz  # PyMuPDF
import re


def extract_text_from_bbox(pdf_path, page_number=1, bbox=None):
    """
    Extrahiert rohen Text aus einer bestimmten Bounding Box einer PDF-Seite

    Args:
        pdf_path: Pfad zur PDF-Datei
        page_number: Seitennummer (0-basiert, also 1 für Seite 2)
        bbox: Bounding Box als Tuple (x0, y0, x1, y1) - wenn None, wird unten rechts verwendet

    Returns:
        Dictionary mit 'success' (bool) und 'text' (str) Keys
    """
    try:
        # PDF öffnen
        doc = fitz.open(pdf_path)

        if page_number >= len(doc):
            print(
                f"Seite {page_number + 1} existiert nicht. PDF hat nur {len(doc)} Seiten."
            )
            doc.close()
            return {"success": False, "text": ""}

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

        return {"success": True, "text": extracted_text}

    except Exception as e:
        print(f"Fehler beim Extrahieren des Textes: {str(e)}")
        return {"success": False, "text": ""}


def extract_entire_text(pdf_path, page_number=1):
    """
    Extrahiert den gesamten Text einer Postkarte

    Args:
        pdf_path: Pfad zur PDF-Datei
        page_number: Seitennummer (0-basiert, also 1 für Seite 2)

    Returns:
        Dictionary mit 'success' (bool) und 'text' (str) Keys
    """
    try:
        # PDF öffnen
        doc = fitz.open(pdf_path)

        if page_number >= len(doc):
            print(
                f"Seite {page_number + 1} existiert nicht. PDF hat nur {len(doc)} Seiten."
            )
            doc.close()
            return {"success": False, "text": ""}

        # Seite laden
        page = doc[page_number]

        # Gesamten Text der Seite extrahieren
        text = page.get_text("text")

        doc.close()

        # Text bereinigen
        extracted_text = text.strip()

        if extracted_text:
            return {"success": True, "text": extracted_text}
        else:
            return {"success": False, "text": ""}

    except Exception as e:
        print(f"Fehler beim Extrahieren des Postkartentextes: {str(e)}")
        return {"success": False, "text": ""}


def extract_postcard_body_text(pdf_path, page_number=1, body_bbox=None):
    """
    Extrahiert den Body-Text (Haupttext) einer Postkarte, ohne die Adresse

    Args:
        pdf_path: Pfad zur PDF-Datei
        page_number: Seitennummer (0-basiert, also 1 für Seite 2)
        body_bbox: Bounding Box für den Body-Bereich als Tuple (x0, y0, x1, y1)
                  - wenn None, wird der linke Bereich verwendet (typisch für Postkarten-Body)

    Returns:
        Dictionary mit 'success' (bool) und 'text' (str) Keys
    """

    if body_bbox is None:
        # Standardmäßig linke Hälfte für Body-Text (typisches Postkarten-Layout)
        # Text aus der Body-Bounding Box extrahieren (ohne spezifische bbox)
        text_result = extract_text_from_bbox(pdf_path, page_number, None)

        if not text_result["success"]:
            return {"success": False, "text": ""}

        # Da extract_text_from_bbox standardmäßig die rechte untere Hälfte nimmt (für Adressen),
        # müssen wir eine eigene Body-bbox definieren
        try:
            doc = fitz.open(pdf_path)
            if page_number >= len(doc):
                doc.close()
                return {"success": False, "text": ""}

            page = doc[page_number]
            # Linke Hälfte der Seite für Body-Text
            body_bbox = (
                0,  # x0: ganz links
                0,  # y0: ganz oben
                page.rect.width * 0.53,  # x1: bis zur Mitte
                page.rect.height,  # y1: ganz unten
            )
            doc.close()

        except Exception as e:
            print(f"Fehler beim Bestimmen der Body-Bbox: {str(e)}")
            return {"success": False, "text": ""}

    # Text aus der Body-Bounding Box extrahieren
    text_result = extract_text_from_bbox(pdf_path, page_number, body_bbox)

    if not text_result["success"]:
        return {"success": False, "text": ""}

    extracted_text = text_result["text"]

    try:
        # Body-Text bereinigen (weniger aggressive Bereinigung als bei Adressen)
        # Hauptsächlich nur Leerzeichen normalisieren
        lines = extracted_text.splitlines()
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:  # Nur nicht-leere Zeilen behalten
                cleaned_lines.append(line)

        # Zeilen wieder zusammenfügen
        cleaned_text = "\n".join(cleaned_lines).strip()

        if cleaned_text:
            return {"success": True, "text": cleaned_text}
        else:
            return {"success": False, "text": ""}

    except Exception as e:
        print(f"Fehler beim Verarbeiten des Body-Textes: {str(e)}")
        return {"success": False, "text": ""}


def remove_descriptors_from_text(text, remove_descriptors=True):
    """
    Entfernt Descriptor-Patterns wie "Name:", "Street:", etc. aus dem Text

    Args:
        text: Der zu bereinigende Text
        remove_descriptors: Ob Descriptors entfernt werden sollen (True/False)

    Returns:
        Bereinigter Text
    """
    if not remove_descriptors:
        return text

    # Split into lines and process each line
    address_lines = text.splitlines()
    cleaned_lines = []

    # Common descriptor patterns to remove
    descriptors = [
        "name",
        "street",
        "address",
        "city",
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
    return "\n".join(cleaned_lines).strip()


def remove_name_from_address(text, remove_name=True):
    """
    Entfernt potentielle Namen (erste Zeile ohne Ziffern) aus der Adresse

    Args:
        text: Der zu bereinigende Text
        remove_name: Ob Name entfernt werden soll (True/False)

    Returns:
        Bereinigter Text
    """
    if not remove_name:
        return text

    # split address in lines again for further processing
    address_lines = text.splitlines()
    # check if longer than 2 lines
    if len(address_lines) > 2:
        # check if first line contains a name and e.g. no number.
        if address_lines[0] and not any(char.isdigit() for char in address_lines[0]):
            # First line seems to be a name and can be removed
            return text.split("\n", 1)[-1].strip()

    return text


def extract_addresses(
    pdf_path, page_number=1, bbox=None, remove_descriptors=True, remove_name=False
):
    """
    Extrahiert Text aus einer bestimmten Bounding Box einer PDF-Seite

    Args:
        pdf_path: Pfad zur PDF-Datei
        page_number: Seitennummer (0-basiert, also 1 für Seite 2)
        bbox: Bounding Box als Tuple (x0, y0, x1, y1) - wenn None, wird unten rechts verwendet
        remove_descriptors: Ob Descriptor-Patterns ("Name:", "Street:", etc.) entfernt werden sollen
        remove_name: Ob potentielle Namen (erste Zeile ohne Ziffern) entfernt werden sollen

    Returns:
        Dictionary mit 'success' (bool) und 'address' (str) Keys
    """

    # Text aus der Bounding Box extrahieren
    text_result = extract_text_from_bbox(pdf_path, page_number, bbox)

    if not text_result["success"]:
        return {"success": False, "address": ""}

    extracted_text = text_result["text"]

    try:
        # Optional: Descriptors entfernen
        if remove_descriptors:
            extracted_text = remove_descriptors_from_text(
                extracted_text, remove_descriptors
            )

        # Optional: Namen entfernen
        if remove_name:
            extracted_text = remove_name_from_address(extracted_text, remove_name)

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
        print(f"Fehler beim Verarbeiten der Adresse: {str(e)}")
        return {"success": False, "address": ""}


if __name__ == "__main__":
    # Example usage
    # pdf_path = "path/to/your/pdf/file.pdf"
    # extracted_text = extract_address_from_bbox(pdf_path, page_number=1)
    # print("Extrahierter Text aus der Bounding Box:")
    # print("=" * 40)
    # print(extracted_text)
    # print("=" * 40)
    # pass

    pdf_path = r"C:\Users\gjm\Projecte\PostCardDjango\media\postcards\08d42f7c-6fdb-423f-9792-805df61f4776.pdf"
    # postcard_74f2188c-68c8-47c6-ba66-35156d315717_print_version
    pdf_path = r"C:\Users\gjm\Projecte\PostCardDjango\media\postcards\74f2188c-68c8-47c6-ba66-35156d315717.pdf"

    # Standard: mit Descriptor- und Namenentfernung
    result = extract_addresses(pdf_path, page_number=1, remove_name=True)
    if result["success"]:
        print("Gefundene Adresse (bereinigt):")
        print(result["address"])
    else:
        print("Keine Adresse gefunden.")

    print("\n" + "=" * 50 + "\n")

    # Optional: ohne Namenentfernung
    result = extract_addresses(pdf_path, page_number=1, remove_name=False)
    if result["success"]:
        print("Gefundene Adresse (mit Namen):")
        print(result["address"])
    else:
        print("Keine Adresse gefunden.")

    print("\n" + "=" * 50 + "\n")

    # Optional: komplett unbereinigt
    result = extract_addresses(
        pdf_path, page_number=1, remove_descriptors=False, remove_name=False
    )
    if result["success"]:
        print("Gefundene Adresse (unbereinigt):")
        print(result["address"])
    else:
        print("Keine Adresse gefunden.")

    print("\n" + "=" * 50 + "\n")

    result = extract_postcard_body_text(pdf_path, page_number=1)
    if result["success"]:
        print("Gefundener Body-Text:")
        print(result["text"])
    else:
        print("Kein Body-Text gefunden.")
