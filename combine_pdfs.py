from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from pypdf.generic import RectangleObject
import os
from typing import List, Tuple, Optional
import copy




def combine_and_merge_double_sided_pdfs(
    pdf_paths: List[str],
    output_path: str,
    layout: Tuple[int, int] = (2, 2),
    flip_on_short_edge: bool = False,
) -> bool:
    """
    Kombiniert eine beliebige Anzahl von doppelseitigen PDFs in einem Grid-Layout.
    Erstellt mehrseitige PDFs wenn mehr PDFs vorhanden sind als in ein Grid passen.

    Jedes Input-PDF sollte genau 2 Seiten haben (Vorder- und Rückseite).
    Das Output-PDF wird mehrere Seitenpaare haben wenn nötig:
    - Seite 1, 3, 5, ...: Vorderseiten im Grid-Layout
    - Seite 2, 4, 6, ...: Rückseiten im Grid-Layout

    Args:
        pdf_paths: Liste der Pfade zu den Input-PDF-Dateien (jedes sollte 2 Seiten haben)
        output_path: Pfad für das Output-PDF
        layout: Tuple (cols, rows) für das Grid-Layout, z.B. (2,2) für 2x2 Grid
        flip_on_short_edge: Falls True, wird für kurze Seite gespiegelt; Falls False, für lange Seite (Standard)

    Returns:
        bool: True wenn erfolgreich, False bei Fehler
    """
    
    try:
        cols, rows = layout
        pages_per_grid = cols * rows
        
        if not pdf_paths:
            print("Fehler: Keine PDF-Pfade angegeben")
            return False
        
        total_pdfs = len(pdf_paths)
        grids_needed = (total_pdfs + pages_per_grid - 1) // pages_per_grid  # Aufrunden
        
        print(f"Layout: {cols}x{rows} = {pages_per_grid} PDFs pro Grid")
        print(f"Gesamt PDFs: {total_pdfs}")
        print(f"Benötigte Grids: {grids_needed}")
        print(f"Output wird {grids_needed * 2} Seiten haben")
        
        # Alle PDFs laden und validieren
        all_front_pages = []
        all_back_pages = []
        
        # Referenzgröße aus erstem PDF ermitteln
        reference_width = None
        reference_height = None
        
        for i, pdf_path in enumerate(pdf_paths):
            if not os.path.exists(pdf_path):
                print(f"Warnung: PDF nicht gefunden: {pdf_path}")
                continue

            reader = PdfReader(pdf_path)

            if len(reader.pages) < 1:
                print(f"Warnung: PDF {pdf_path} hat keine Seiten")
                continue
            elif len(reader.pages) == 1:
                print(f"Info: PDF {pdf_path} hat nur 1 Seite, verwende diese als Vorder- und Rückseite")
                front_page = reader.pages[0]
                back_page = reader.pages[0]
            else:
                front_page = reader.pages[0]
                back_page = reader.pages[1]
                if len(reader.pages) > 2:
                    print(f"Info: PDF {pdf_path} hat {len(reader.pages)} Seiten, verwende nur die ersten 2")

            # Referenzgröße beim ersten gültigen PDF setzen
            if reference_width is None:
                reference_width = float(front_page.mediabox.width)
                reference_height = float(front_page.mediabox.height)
                print(f"Referenzgröße: {reference_width:.1f} x {reference_height:.1f} points")

            all_front_pages.append(front_page)
            all_back_pages.append(back_page)
        
        if not all_front_pages:
            print("Fehler: Keine gültigen PDFs gefunden")
            return False
        
        # Ausgabegröße berechnen
        output_width = reference_width * cols
        output_height = reference_height * rows
        
        print(f"Ausgabegröße: {output_width:.1f} x {output_height:.1f} points")
        
        # Flip-Logik bestimmen (aus der ursprünglichen Funktion übernommen)
        is_output_wider_than_tall = output_width > output_height
        effective_flip_on_short_edge = flip_on_short_edge
        
        if not is_output_wider_than_tall:
            effective_flip_on_short_edge = not flip_on_short_edge
            print(f"Hochformat erkannt ({output_width:.0f}x{output_height:.0f}) - Flip-Logik angepasst")
        else:
            print(f"Querformat erkannt ({output_width:.0f}x{output_height:.0f}) - Standard Flip-Logik")
        
        print(f"Original flip_on_short_edge: {flip_on_short_edge}")
        print(f"Effektive flip_on_short_edge: {effective_flip_on_short_edge}")
        
        writer = PdfWriter()
        
        # Für jedes benötigte Grid ein Seitenpaar erstellen
        for grid_index in range(grids_needed):
            start_pdf_index = grid_index * pages_per_grid
            end_pdf_index = min(start_pdf_index + pages_per_grid, len(all_front_pages))
            
            print(f"\nErstelle Grid {grid_index + 1}/{grids_needed} (PDFs {start_pdf_index + 1}-{end_pdf_index})")
            
            # PDFs für dieses Grid extrahieren
            grid_front_pages = all_front_pages[start_pdf_index:end_pdf_index]
            grid_back_pages = all_back_pages[start_pdf_index:end_pdf_index]
            
            # Mit leeren Seiten auffüllen falls nötig
            while len(grid_front_pages) < pages_per_grid:
                empty_page = PageObject.create_blank_page(
                    width=reference_width, height=reference_height
                )
                grid_front_pages.append(empty_page)
                grid_back_pages.append(empty_page)
                print(f"Leere Seite hinzugefügt für Position {len(grid_front_pages)}")
            
            # Vorderseite für dieses Grid erstellen
            front_output_page = create_grid_page_front(
                grid_front_pages,
                layout,
                (output_width, output_height),
                (reference_width, reference_height),
            )
            writer.add_page(front_output_page)
            
            # Rückseite für dieses Grid erstellen
            back_output_page = create_grid_page_back(
                grid_back_pages,
                layout,
                (output_width, output_height),
                (reference_width, reference_height),
                effective_flip_on_short_edge,
            )
            writer.add_page(back_output_page)
        
        # PDF speichern
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        print(f"\nMehrseitiges doppelseitiges PDF erfolgreich erstellt: {output_path}")
        print(f"- {grids_needed} Grid(s) mit je {pages_per_grid} PDFs im {cols}x{rows} Layout")
        print(f"- Insgesamt {grids_needed * 2} Seiten ({grids_needed} Vorderseiten, {grids_needed} Rückseiten)")
        print(f"- Verarbeitete PDFs: {len(all_front_pages)}")
        print(f"- Wendeseite (ursprünglich): {'Kurze Seite' if flip_on_short_edge else 'Lange Seite'}")
        print(f"- Wendeseite (effektiv): {'Kurze Seite' if effective_flip_on_short_edge else 'Lange Seite'}")
        return True
        
    except Exception as e:
        print(f"Fehler beim Kombinieren der PDFs: {str(e)}")
        return False


def combine_double_sided_pdfs(
    pdf_paths: List[str],
    output_path: str,
    layout: Tuple[int, int] = (2, 2),
    flip_on_short_edge: bool = False,
) -> bool:
    """
    Kombiniert mehrere doppelseitige PDFs in einem Grid-Layout.

    Jedes Input-PDF sollte genau 2 Seiten haben (Vorder- und Rückseite).
    Das Output-PDF wird ebenfalls 2 Seiten haben:
    - Seite 1: Alle Vorderseiten im Grid-Layout
    - Seite 2: Alle Rückseiten im Grid-Layout

    Args:
        pdf_paths: Liste der Pfade zu den Input-PDF-Dateien (jedes sollte 2 Seiten haben)
        output_path: Pfad für das Output-PDF
        layout: Tuple (cols, rows) für das Grid-Layout, z.B. (2,2) für 2x2 Grid
        flip_on_short_edge: Falls True, wird für kurze Seite gespiegelt; Falls False, für lange Seite (Standard)

    Returns:
        bool: True wenn erfolgreich, False bei Fehler
    """

    try:
        cols, rows = layout
        pages_needed = cols * rows

        print(f"Layout: {cols}x{rows} = {pages_needed} PDFs benötigt")

        # Alle PDFs laden und validieren
        front_pages = []
        back_pages = []

        # Referenzgröße aus erstem PDF ermitteln
        reference_width = None
        reference_height = None

        for i, pdf_path in enumerate(pdf_paths):
            if not os.path.exists(pdf_path):
                print(f"Warnung: PDF nicht gefunden: {pdf_path}")
                continue

            reader = PdfReader(pdf_path)

            if len(reader.pages) < 1:
                print(f"Warnung: PDF {pdf_path} hat keine Seiten")
                continue
            elif len(reader.pages) == 1:
                print(
                    f"Info: PDF {pdf_path} hat nur 1 Seite, verwende diese als Vorder- und Rückseite"
                )
                front_page = reader.pages[0]
                back_page = reader.pages[0]  # Gleiche Seite für Vorder- und Rückseite
            else:
                front_page = reader.pages[0]
                back_page = reader.pages[1]
                if len(reader.pages) > 2:
                    print(
                        f"Info: PDF {pdf_path} hat {len(reader.pages)} Seiten, verwende nur die ersten 2"
                    )

            # Referenzgröße beim ersten PDF setzen
            if reference_width is None:
                reference_width = float(front_page.mediabox.width)
                reference_height = float(front_page.mediabox.height)
                print(
                    f"Referenzgröße: {reference_width:.1f} x {reference_height:.1f} points"
                )

            front_pages.append(front_page)
            back_pages.append(back_page)

            if len(front_pages) >= pages_needed:
                break

        # Mit leeren Seiten auffüllen falls nötig
        if len(front_pages) < pages_needed:
            empty_pages_needed = pages_needed - len(front_pages)
            print(f"Fülle {empty_pages_needed} leere Seiten hinzu")

            for _ in range(empty_pages_needed):
                empty_page = PageObject.create_blank_page(
                    width=reference_width, height=reference_height
                )
                front_pages.append(empty_page)
                back_pages.append(empty_page)

        # Ausgabegröße berechnen
        output_width = reference_width * cols
        output_height = reference_height * rows

        print(f"Ausgabegröße: {output_width:.1f} x {output_height:.1f} points")

        # Automatisch bestimmen, welche Seite die kurze ist basierend auf dem Layout
        # und entsprechend das flip_on_short_edge anpassen
        is_output_wider_than_tall = output_width > output_height

        # Für korrekte Druckorientierung muss das Flip-Verhalten an die Ausrichtung angepasst werden
        effective_flip_on_short_edge = flip_on_short_edge

        if not is_output_wider_than_tall:  # Hochformat (output_height >= output_width)
            # Bei Hochformat (z.B. 2x3, 2x4) ist die kurze Seite horizontal
            # Das bedeutet, die ursprüngliche flip_on_short_edge Logik muss invertiert werden
            effective_flip_on_short_edge = not flip_on_short_edge
            print(
                f"Hochformat erkannt ({output_width:.0f}x{output_height:.0f}) - Flip-Logik angepasst"
            )
        else:
            print(
                f"Querformat erkannt ({output_width:.0f}x{output_height:.0f}) - Standard Flip-Logik"
            )

        print(f"Original flip_on_short_edge: {flip_on_short_edge}")
        print(f"Effektive flip_on_short_edge: {effective_flip_on_short_edge}")

        writer = PdfWriter()

        # Seite 1: Alle Vorderseiten
        front_output_page = create_grid_page_front(
            front_pages[:pages_needed],
            layout,
            (output_width, output_height),
            (reference_width, reference_height),
        )
        writer.add_page(front_output_page)

        # Seite 2: Alle Rückseiten (mit korrekter Orientierung für gewählte Wendeseite)
        back_output_page = create_grid_page_back(
            back_pages[:pages_needed],
            layout,
            (output_width, output_height),
            (reference_width, reference_height),
            effective_flip_on_short_edge,
        )
        writer.add_page(back_output_page)

        # PDF speichern
        with open(output_path, "wb") as output_file:
            writer.write(output_file)

        print(f"Doppelseitiges PDF erfolgreich erstellt: {output_path}")
        print(f"- Seite 1: {pages_needed} Vorderseiten im {cols}x{rows} Layout")
        print(f"- Seite 2: {pages_needed} Rückseiten im {cols}x{rows} Layout")
        print(
            f"- Wendeseite (ursprünglich): {'Kurze Seite' if flip_on_short_edge else 'Lange Seite'}"
        )
        print(
            f"- Wendeseite (effektiv): {'Kurze Seite' if effective_flip_on_short_edge else 'Lange Seite'}"
        )
        return True

    except Exception as e:
        print(f"Fehler beim Kombinieren der PDFs: {str(e)}")
        return False


def create_grid_page_front(
    pages: List[PageObject],
    layout: Tuple[int, int],
    output_size: Tuple[float, float],
    cell_size: Tuple[float, float],
) -> PageObject:
    """
    Erstellt eine Vorderseite mit den gegebenen Seiten in einem Grid-Layout.
    Normale Reihenfolge von oben links nach unten rechts.

    Args:
        pages: Liste der zu platzierenden Seiten
        layout: (cols, rows) Layout
        output_size: (width, height) der Ausgabeseite
        cell_size: (width, height) einer einzelnen Zelle

    Returns:
        PageObject: Die erstellte Vorderseite
    """
    cols, rows = layout
    output_width, output_height = output_size
    cell_width, cell_height = cell_size

    temp_writer = PdfWriter()
    output_page = temp_writer.add_blank_page(width=output_width, height=output_height)

    # Grid füllen - normale Reihenfolge
    for row in range(rows):
        for col in range(cols):
            page_index = row * cols + col

            if page_index < len(pages):
                # Position berechnen (Y-Koordinate von oben nach unten)
                x_offset = col * cell_width
                y_offset = (rows - 1 - row) * cell_height

                print(
                    f"Vorderseite: Platziere Seite {page_index + 1} an Position ({col}, {row}) -> Offset: ({x_offset:.1f}, {y_offset:.1f})"
                )

                source_page = pages[page_index]
                output_page.merge_transformed_page(
                    source_page, Transformation().translate(tx=x_offset, ty=y_offset)
                )

    return output_page


def create_grid_page_back(
    pages: List[PageObject],
    layout: Tuple[int, int],
    output_size: Tuple[float, float],
    cell_size: Tuple[float, float],
    flip_on_short_edge: bool = False,
) -> PageObject:
    """
    Erstellt eine Rückseite mit den gegebenen Seiten in einem Grid-Layout.
    Reihenfolge angepasst für Druck mit Wenden auf der gewählten Seite.

    Wenden auf langer Seite (flip_on_short_edge=False):
    Für 2x2: Vorderseite [1,2,3,4] -> Rückseite [3,4,1,2]
    Für 4x4: Vorderseite Zeilen [1-4,5-8,9-12,13-16] -> Rückseite Zeilen [13-16,9-12,5-8,1-4]

    Wenden auf kurzer Seite (flip_on_short_edge=True):
    Für 2x2: Vorderseite [1,2,3,4] -> Rückseite [2,1,4,3]
    Für 4x4: Vorderseite Spalten [1,5,9,13,2,6,10,14,3,7,11,15,4,8,12,16] -> Rückseite Spalten [13,9,5,1,14,10,6,2,15,11,7,3,16,12,8,4]

    Args:
        pages: Liste der zu platzierenden Seiten
        layout: (cols, rows) Layout
        output_size: (width, height) der Ausgabeseite
        cell_size: (width, height) einer einzelnen Zelle
        flip_on_short_edge: Falls True, spiegelt für kurze Seite; Falls False, für lange Seite

    Returns:
        PageObject: Die erstellte Rückseite
    """
    cols, rows = layout
    output_width, output_height = output_size
    cell_width, cell_height = cell_size

    temp_writer = PdfWriter()
    output_page = temp_writer.add_blank_page(width=output_width, height=output_height)

    # Grid füllen - Orientierung abhängig von der gewählten Wendeseite
    if flip_on_short_edge:
        # Für kurze Seite: Spalten in umgekehrter Reihenfolge
        for row in range(rows):
            for col in range(cols):
                # Berechne den Index der Seite in umgekehrter Spaltenreihenfolge
                source_col = cols - 1 - col  # Umgekehrte Spalte
                page_index = row * cols + source_col

                if page_index < len(pages):
                    # Position berechnen (Y-Koordinate von oben nach unten)
                    x_offset = col * cell_width
                    y_offset = (rows - 1 - row) * cell_height

                    print(
                        f"Rückseite (kurze Seite): Platziere Seite {page_index + 1} an Position ({col}, {row}) -> Offset: ({x_offset:.1f}, {y_offset:.1f})"
                    )

                    source_page = pages[page_index]
                    output_page.merge_transformed_page(
                        source_page,
                        Transformation().translate(tx=x_offset, ty=y_offset),
                    )
    else:
        # Für lange Seite: Zeilen in umgekehrter Reihenfolge
        for row in range(rows):
            for col in range(cols):
                # Berechne den Index der Seite in umgekehrter Zeilenreihenfolge
                source_row = rows - 1 - row  # Umgekehrte Zeile
                page_index = source_row * cols + col

                if page_index < len(pages):
                    # Position berechnen (Y-Koordinate von oben nach unten)
                    x_offset = col * cell_width
                    y_offset = (rows - 1 - row) * cell_height

                    print(
                        f"Rückseite (lange Seite): Platziere Seite {page_index + 1} an Position ({col}, {row}) -> Offset: ({x_offset:.1f}, {y_offset:.1f})"
                    )

                    source_page = pages[page_index]
                    output_page.merge_transformed_page(
                        source_page,
                        Transformation().translate(tx=x_offset, ty=y_offset),
                    )

    return output_page


def create_grid_page(
    pages: List[PageObject],
    layout: Tuple[int, int],
    output_size: Tuple[float, float],
    cell_size: Tuple[float, float],
) -> PageObject:
    """
    Erstellt eine Seite mit den gegebenen Seiten in einem Grid-Layout.

    Veraltete Funktion - verwende create_grid_page_front() oder create_grid_page_back()
    für korrekte doppelseitige Druckorientierung.

    Args:
        pages: Liste der zu platzierenden Seiten
        layout: (cols, rows) Layout
        output_size: (width, height) der Ausgabeseite
        cell_size: (width, height) einer einzelnen Zelle

    Returns:
        PageObject: Die erstellte Seite
    """
    return create_grid_page_front(pages, layout, output_size, cell_size)


def print_layout_example(
    layout: Tuple[int, int], flip_on_short_edge: bool = False
) -> None:
    """
    Druckt ein Beispiel der Seitenlayouts für gegebene Dimensionen.

    Args:
        layout: (cols, rows) Layout-Dimensionen
        flip_on_short_edge: Falls True, zeigt Layout für kurze Seite; Falls False, für lange Seite
    """
    cols, rows = layout
    pages_needed = cols * rows

    edge_type = "kurzer Seite" if flip_on_short_edge else "langer Seite"
    print(
        f"\n=== Layout-Beispiel für {cols}x{rows} ({pages_needed} Seiten) - Wenden auf {edge_type} ==="
    )

    # Vorderseite
    print("Vorderseite:")
    for row in range(rows):
        row_str = ""
        for col in range(cols):
            page_num = row * cols + col + 1
            row_str += f"{page_num:2d} "
        print(f"  {row_str}")

    # Rückseite
    if flip_on_short_edge:
        print("Rückseite (nach Wenden auf kurzer Seite):")
        for row in range(rows):
            row_str = ""
            for col in range(cols):
                source_col = cols - 1 - col  # Umgekehrte Spalte
                page_num = row * cols + source_col + 1
                row_str += f"{page_num:2d} "
            print(f"  {row_str}")
    else:
        print("Rückseite (nach Wenden auf langer Seite):")
        for row in range(rows):
            row_str = ""
            for col in range(cols):
                source_row = rows - 1 - row  # Umgekehrte Zeile
                page_num = source_row * cols + col + 1
                row_str += f"{page_num:2d} "
            print(f"  {row_str}")
    print()


# Convenience-Funktionen für häufige Anwendungsfälle
def combine_a6_postcards_to_a4(
    pdf_paths: List[str], output_path: str, flip_on_short_edge: bool = False
) -> bool:
    """4 A6 Postkarten-PDFs zu 1 A4 PDF (2x2 Layout)"""
    return combine_double_sided_pdfs(
        pdf_paths, output_path, layout=(2, 2), flip_on_short_edge=flip_on_short_edge
    )


def combine_a6_postcards_to_a3(
    pdf_paths: List[str], output_path: str, flip_on_short_edge: bool = False
) -> bool:
    """8 A6 Postkarten-PDFs zu 1 A3 PDF (2x4 Layout)"""
    return combine_double_sided_pdfs(
        pdf_paths, output_path, layout=(2, 4), flip_on_short_edge=flip_on_short_edge
    )


def combine_a5_to_a4(
    pdf_paths: List[str], output_path: str, flip_on_short_edge: bool = False
) -> bool:
    """2 A5 PDFs zu 1 A4 PDF (1x2 Layout)"""
    return combine_double_sided_pdfs(
        pdf_paths, output_path, layout=(1, 2), flip_on_short_edge=flip_on_short_edge
    )


# Convenience-Funktionen für mehrseitige Variante
def combine_multiple_a6_postcards_to_a4(
    pdf_paths: List[str], output_path: str, flip_on_short_edge: bool = False
) -> bool:
    """Beliebige Anzahl A6 Postkarten-PDFs zu mehrseitigem A4 PDF (2x2 Layout pro Seite)"""
    return combine_and_merge_double_sided_pdfs(
        pdf_paths, output_path, layout=(2, 2), flip_on_short_edge=flip_on_short_edge
    )


def combine_multiple_a6_postcards_to_a3(
    pdf_paths: List[str], output_path: str, flip_on_short_edge: bool = False
) -> bool:
    """Beliebige Anzahl A6 Postkarten-PDFs zu mehrseitigem A3 PDF (2x4 Layout pro Seite)"""
    return combine_and_merge_double_sided_pdfs(
        pdf_paths, output_path, layout=(2, 4), flip_on_short_edge=flip_on_short_edge
    )


def combine_multiple_a5_to_a4(
    pdf_paths: List[str], output_path: str, flip_on_short_edge: bool = False
) -> bool:
    """Beliebige Anzahl A5 PDFs zu mehrseitigem A4 PDF (1x2 Layout pro Seite)"""
    return combine_and_merge_double_sided_pdfs(
        pdf_paths, output_path, layout=(1, 2), flip_on_short_edge=flip_on_short_edge
    )


if __name__ == "__main__":
    # Layout-Beispiele anzeigen
    print("Layout-Beispiele für doppelseitigen Druck:")
    print_layout_example((2, 2), flip_on_short_edge=False)  # 2x2 Layout, lange Seite
    print_layout_example((2, 2), flip_on_short_edge=True)  # 2x2 Layout, kurze Seite
    print_layout_example((4, 4), flip_on_short_edge=False)  # 4x4 Layout, lange Seite
    print_layout_example((4, 4), flip_on_short_edge=True)  # 4x4 Layout, kurze Seite
    print_layout_example((2, 4), flip_on_short_edge=False)  # 2x4 Layout, lange Seite

    # Beispiel-Verwendung
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

    # 4 A6 Postkarten-PDFs zu 1 A4 PDF (2x2) - Wenden auf langer Seite
    success = combine_a6_postcards_to_a4(
        pdf_files[:4], "Examples/postcards_a4_long_side.pdf", flip_on_short_edge=False
    )
    if success:
        print("A4 Postkarten-PDF (lange Seite) erfolgreich erstellt!")

    # 4 A6 Postkarten-PDFs zu 1 A4 PDF (2x2) - Wenden auf kurzer Seite
    success = combine_a6_postcards_to_a4(
        pdf_files[:4], "Examples/postcards_a4_short_side.pdf", flip_on_short_edge=True
    )
    if success:
        print("A4 Postkarten-PDF (kurze Seite) erfolgreich erstellt!")

    # Oder mit benutzerdefinierten Parametern
    success = combine_double_sided_pdfs(
        pdf_files[:4],
        "Examples/custom_postcards.pdf",
        layout=(2, 2),
        flip_on_short_edge=False,
    )

    # NEUE mehrseitige Funktion - alle 8 PDFs in einem mehrseitigen Dokument
    print("\n=== Teste mehrseitige Funktion ===")
    success = combine_multiple_a6_postcards_to_a4(
        pdf_files, "Examples/multipage_postcards_a4.pdf", flip_on_short_edge=False
    )
    if success:
        print("Mehrseitiges A4 Postkarten-PDF erfolgreich erstellt!")

    # Test mit 10 PDFs (wird 3 Seiten erstellen: 4+4+2 PDFs)
    extended_pdf_files = pdf_files + [
        r"Examples/postcard9.pdf",
        r"Examples/postcard10.pdf"
    ]
    success = combine_and_merge_double_sided_pdfs(
        extended_pdf_files,
        "Examples/extended_multipage_postcards.pdf",
        layout=(2, 2),
        flip_on_short_edge=False,
    )

    # fails on short side: layout=(2, 3), flip_on_short_edge=False
    # Fails on (2,4)
    # Fails on (2,2) # korrekt

    # layout=(2, 4) is for a3
    # layout=(2, 2) is for a4
