"""
PDF Millimeterpapier Generator
============================

Dieses Modul erstellt PDFs mit Millimeterpapier-Raster und konfigurierbarem Rand.
"""

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import Color, black, red, blue, green, yellow, white, gray
from reportlab.lib.pagesizes import A4
import argparse
import os
from typing import Tuple, Optional


class MillimeterPaperGenerator:
    """Generator für PDF-Millimeterpapier mit konfigurierbarem Rand."""

    def __init__(self, width_mm: float, height_mm: float):
        """
        Initialisiert den Generator.

        Args:
            width_mm: Breite der Seite in mmF
            height_mm: Höhe der Seite in mm
        """
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.width_points = width_mm * mm
        self.height_points = height_mm * mm

    def create_border(
        self, c: canvas.Canvas, border_width_mm: float, border_color: Color = red
    ) -> None:
        """
        Erstellt einen farbigen Rand um das PDF.

        Args:
            c: ReportLab Canvas-Objekt
            border_width_mm: Dicke des Randes in mm
            border_color: Farbe des Randes (ReportLab Color-Objekt)
        """
        border_width_points = border_width_mm * mm

        if border_width_points <= 0:
            print(
                "Border width is zero or negative, skipping border creation.",
                border_width_points,
            )
            return

        # Rand-Rechteck zeichnen
        c.setStrokeColor(border_color)
        c.setLineWidth(border_width_points)

        # Rand um die gesamte Seite
        c.rect(
            border_width_points / 2,
            border_width_points / 2,
            self.width_points - border_width_points,
            self.height_points - border_width_points,
        )

    def draw_millimeter_grid(
        self,
        c: canvas.Canvas,
        fine_line_color: Color = Color(0.8, 0.8, 0.8),
        thick_line_color: Color = Color(0.5, 0.5, 0.5),
    ) -> None:
        """
        Zeichnet das Millimeterpapier-Raster bis zum Rand.

        Args:
            c: ReportLab Canvas-Objekt
            fine_line_color: Farbe der feinen 1mm-Linien
            thick_line_color: Farbe der dicken 10mm-Linien
        """
        # Feine Linien (1mm Abstand)
        c.setStrokeColor(fine_line_color)
        c.setLineWidth(0.2)

        # Vertikale Linien (1mm)
        for x_mm in range(1, int(self.width_mm)):
            x_points = x_mm * mm
            c.line(x_points, 0, x_points, self.height_points)

        # Horizontale Linien (1mm)
        for y_mm in range(1, int(self.height_mm)):
            y_points = y_mm * mm
            c.line(0, y_points, self.width_points, y_points)

        # Dicke Linien (10mm Abstand)
        c.setStrokeColor(thick_line_color)
        c.setLineWidth(0.8)

        # Vertikale Linien (10mm)
        for x_mm in range(10, int(self.width_mm), 10):
            x_points = x_mm * mm
            c.line(x_points, 0, x_points, self.height_points)

        # Horizontale Linien (10mm)
        for y_mm in range(10, int(self.height_mm), 10):
            y_points = y_mm * mm
            c.line(0, y_points, self.width_points, y_points)

    def add_coordinate_system(self, c: canvas.Canvas, font_size: int = 8) -> None:
        """
        Fügt ein Koordinatensystem in der Mitte des Papiers hinzu.

        Args:
            c: ReportLab Canvas-Objekt
            font_size: Schriftgröße für die Koordinaten
        """
        c.setFont("Helvetica", font_size)
        c.setFillColor(black)

        # Mittelpunkt berechnen
        center_x = self.width_points / 2
        center_y = self.height_points / 2
        center_x_mm = self.width_mm / 2
        center_y_mm = self.height_mm / 2

        # Koordinatenachsen zeichnen (dickere Linien)
        c.setStrokeColor(Color(0.3, 0.3, 0.3))
        c.setLineWidth(1.0)

        # X-Achse
        c.line(0, center_y, self.width_points, center_y)
        # Y-Achse
        c.line(center_x, 0, center_x, self.height_points)

        # Beschriftung der X-Achse (alle 10mm)
        for x_mm in range(0, int(self.width_mm), 10):
            if x_mm != center_x_mm:  # Nicht bei (0,0)
                x_points = x_mm * mm
                # Koordinate relativ zur Mitte berechnen
                relative_x = x_mm - center_x_mm
                if relative_x != 0:  # Keine Beschriftung bei 0
                    # Oberhalb der X-Achse
                    c.drawCentredString(x_points, center_y + 3, f"{relative_x:.0f}")

        # Beschriftung der Y-Achse (alle 10mm)
        for y_mm in range(0, int(self.height_mm), 10):
            if y_mm != center_y_mm:  # Nicht bei (0,0)
                y_points = y_mm * mm
                # Koordinate relativ zur Mitte berechnen
                relative_y = y_mm - center_y_mm
                if relative_y != 0:  # Keine Beschriftung bei 0
                    # Rechts von der Y-Achse
                    c.drawString(center_x + 3, y_points - 2, f"{relative_y:.0f}")

        # Ursprung (0,0) markieren
        c.drawCentredString(center_x - 8, center_y + 3, "0")
        c.drawString(center_x + 3, center_y - 2, "0")

    def generate_pdf(
        self,
        output_path: str,
        border_width_mm: float = 2.0,
        border_color: Color = red,
        fine_line_color: Color = Color(0.8, 0.8, 0.8),
        thick_line_color: Color = Color(0.5, 0.5, 0.5),
        add_labels: bool = True,
    ) -> None:
        """
        Generiert das komplette PDF mit Millimeterpapier und Rand.

        Args:
            output_path: Pfad für die Ausgabedatei
            border_width_mm: Dicke des Randes in mm
            border_color: Farbe des Randes
            fine_line_color: Farbe der feinen Linien
            thick_line_color: Farbe der dicken Linien
            add_labels: Ob Maßangaben hinzugefügt werden sollen
        """
        # Canvas erstellen
        c = canvas.Canvas(output_path, pagesize=(self.width_points, self.height_points))

        # Millimeterpapier zeichnen (bis zum Rand)
        self.draw_millimeter_grid(c, fine_line_color, thick_line_color)

        # Koordinatensystem hinzufügen (optional)
        if add_labels:
            self.add_coordinate_system(c)

        # Rand zeichnen (kommt zuletzt, damit er über allem liegt)
        self.create_border(c, border_width_mm, border_color)

        # PDF speichern
        c.save()
        print(f"PDF erstellt: {output_path}")


def create_test_pdf(
    width_mm=105, height_mm=148, border_width_mm=5.0, border_color=red, output_path=None
):
    import tempfile

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
    generator = MillimeterPaperGenerator(width_mm, height_mm)
    generator.generate_pdf(
        output_path=output_path,
        border_width_mm=border_width_mm,
        border_color=border_color,
        add_labels=True,
    )
    return output_path


def get_color_from_name(color_name: str) -> Color:
    """
    Konvertiert einen Farbnamen zu einem ReportLab Color-Objekt.

    Args:
        color_name: Name der Farbe (z.B. 'red', 'blue', 'green', 'black')

    Returns:
        Color-Objekt
    """
    color_map = {
        "red": red,
        "blue": blue,
        "green": green,
        "black": black,
        "gray": Color(0.5, 0.5, 0.5),
        "lightgray": Color(0.8, 0.8, 0.8),
        "darkgray": Color(0.3, 0.3, 0.3),
    }

    return color_map.get(color_name.lower(), red)


def main():
    """Hauptfunktion für die Kommandozeilen-Nutzung."""
    parser = argparse.ArgumentParser(description="PDF Millimeterpapier Generator")

    parser.add_argument(
        "--width", type=float, default=210, help="Breite in mm (Standard: 210 für A4)"
    )
    parser.add_argument(
        "--height", type=float, default=297, help="Höhe in mm (Standard: 297 für A4)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="millimeter_paper.pdf",
        help="Ausgabedatei (Standard: millimeter_paper.pdf)",
    )
    parser.add_argument(
        "--border-width",
        type=float,
        default=2.0,
        help="Randdicke in mm (Standard: 2.0)",
    )
    parser.add_argument(
        "--border-color",
        type=str,
        default="red",
        help="Randfarbe (red, blue, green, black, gray, lightgray, darkgray)",
    )
    parser.add_argument(
        "--no-labels", action="store_true", help="Keine Maßangaben hinzufügen"
    )

    args = parser.parse_args()

    # Generator erstellen
    generator = MillimeterPaperGenerator(args.width, args.height)

    # Farbe konvertieren
    border_color = get_color_from_name(args.border_color)

    # PDF generieren
    generator.generate_pdf(
        output_path=args.output,
        border_width_mm=args.border_width,
        border_color=border_color,
        add_labels=not args.no_labels,
    )


if __name__ == "__main__":
    # Beispiel-Nutzung, wenn das Skript direkt ausgeführt wird
    if len(os.sys.argv) == 1:
        # Standardbeispiel erstellen
        print("Erstelle Beispiel-PDFs...")

        generator = MillimeterPaperGenerator(210, 297)  # A4
        basepath = "Examples/Crop_Tests/"
        # A4 mit rotem Rand
        generator.generate_pdf(
            basepath + "millimeter_paper_a4_red_rotated.pdf",
            border_width_mm=2.0,
            border_color=red,
        )

        generator = MillimeterPaperGenerator(297, 210)  # A4
        basepath = "Examples/Crop_Tests/"
        # A4 mit rotem Rand
        generator.generate_pdf(
            basepath + "millimeter_paper_a4_white.pdf",
            border_width_mm=1.0,
            border_color=white,
        )

        # Kleineres Format mit blauem Rand
        generator_small = MillimeterPaperGenerator(100, 148)  # A6
        generator_small.generate_pdf(
            basepath + "millimeter_paper_a6_blue_rotated.pdf",
            border_width_mm=1.5,
            border_color=blue,
        )

        # Postkartenformat mit grünem Rand
        generator_postcard = MillimeterPaperGenerator(148, 105)
        generator_postcard.generate_pdf(
            basepath + "millimeter_paper_postcard_green.pdf",
            border_width_mm=3.0,
            border_color=green,
        )

        # Postkartenformat mit grünem Rand
        generator_postcard = MillimeterPaperGenerator(148, 100)
        generator_postcard.generate_pdf(
            basepath + "millimeter_paper_A6_green.pdf",
            border_width_mm=10.0,
            border_color=green,
        )

        # A6+ Format mit gelbem Rand
        generator_postcard = MillimeterPaperGenerator(148 + 3, 105 + 3)
        generator_postcard.generate_pdf(
            basepath + "millimeter_paper_A6+_yellow.pdf",
            border_width_mm=10.0,
            border_color=yellow,
        )

        # A6+ Format mit gelbem Rand
        generator_postcard = MillimeterPaperGenerator(148 + 7, 105 + 7)
        generator_postcard.generate_pdf(
            basepath + "millimeter_paper_A6+7_yellow.pdf",
            border_width_mm=1.0,
            border_color=yellow,
        )

        print("Beispiel-PDFs erstellt in " + basepath)
    else:
        main()
