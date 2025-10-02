#!/usr/bin/env python3
"""
PDF Vertical Black Line Detector and Remover

This script detects and removes vertical black lines from PDF files.
It analyzes the PDF content to find vertical lines (especially around the middle)
and removes them while preserving other content.

Dependencies:
- PyMuPDF (fitz): pip install PyMuPDF
- Pillow: pip install Pillow
- numpy: pip install numpy

Author: Generated for PostCard Django Project
"""

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
import argparse
import os
import sys
from typing import List, Tuple, Optional


class VerticalLineRemover:
    def __init__(self, tolerance: float = 5.0, min_line_length: float = 60.0):
        """
        Initialize the vertical line remover.

        Args:
            tolerance: Tolerance for detecting vertical lines (degrees from vertical)
            min_line_length: Minimum length of line to be considered for removal
        """
        self.tolerance = tolerance
        self.min_line_length = min_line_length

    def detect_vertical_lines_in_image(
        self, image_array: np.ndarray, page_width: float
    ) -> List[Tuple[float, float, float]]:
        """
        Detect vertical black lines in an image array.

        Args:
            image_array: Image as numpy array
            page_width: Width of the page in points

        Returns:
            List of tuples (x_position, top_y, bottom_y) for detected lines
        """
        # Convert to grayscale if needed
        if len(image_array.shape) == 3:
            gray = np.mean(image_array, axis=2)
        else:
            gray = image_array

        # Threshold to find black pixels (adjust threshold as needed)
        black_threshold = 50  # Pixels darker than this are considered black
        black_pixels = gray < black_threshold

        height, width = black_pixels.shape
        detected_lines = []

        # Look for vertical lines by scanning columns
        for x in range(width):
            column = black_pixels[:, x]

            # Find continuous black segments in this column
            black_runs = self._find_continuous_runs(column)

            for start_y, end_y in black_runs:
                line_length = end_y - start_y

                # Convert pixel coordinates to PDF coordinates
                pdf_x = (x / width) * page_width
                pdf_y_start = (
                    start_y / height
                ) * page_width  # Assuming square aspect ratio
                pdf_y_end = (end_y / height) * page_width

                # Check if this line is long enough and potentially in the middle area
                if line_length > self.min_line_length:
                    # Prioritize lines near the middle of the page
                    middle_x = page_width / 2
                    distance_from_middle = abs(pdf_x - middle_x)

                    # If the line is reasonably close to the middle or very long
                    if (
                        distance_from_middle < page_width * 0.3
                        or line_length > height * 0.5
                    ):
                        detected_lines.append((pdf_x, pdf_y_start, pdf_y_end))

        return detected_lines

    def _find_continuous_runs(self, boolean_array: np.ndarray) -> List[Tuple[int, int]]:
        """Find continuous runs of True values in a boolean array."""
        runs = []
        in_run = False
        start = 0

        for i, val in enumerate(boolean_array):
            if val and not in_run:
                start = i
                in_run = True
            elif not val and in_run:
                runs.append((start, i))
                in_run = False

        # Handle case where run continues to end
        if in_run:
            runs.append((start, len(boolean_array)))

        return runs

    def detect_lines_from_pdf_objects(
        self, page: fitz.Page
    ) -> List[Tuple[float, float, float, float]]:
        """
        Detect vertical lines by analyzing PDF drawing objects.

        Args:
            page: PyMuPDF page object

        Returns:
            List of tuples (x1, y1, x2, y2) for detected vertical lines
        """
        detected_lines = []

        # Get all drawing paths from the page
        paths = page.get_drawings()

        for path in paths:
            for item in path["items"]:
                if item[0] == "l":  # Line command
                    x1, y1 = item[1]  # Start point
                    x2, y2 = item[2]  # End point

                    # Check if it's a vertical line
                    if abs(x2 - x1) <= self.tolerance:  # Vertical line
                        line_length = abs(y2 - y1)

                        if line_length >= self.min_line_length:
                            # Check if it's black (or very dark)
                            stroke_color = path.get("stroke", [0, 0, 0])

                            # Consider it black if RGB values are all low
                            if (
                                isinstance(stroke_color, list)
                                and len(stroke_color) >= 3
                            ):
                                if all(
                                    c <= 0.2 for c in stroke_color[:3]
                                ):  # Dark enough
                                    detected_lines.append((x1, y1, x2, y2))
                            elif stroke_color == [0, 0, 0] or stroke_color is None:
                                detected_lines.append((x1, y1, x2, y2))

        return detected_lines

    def remove_lines_from_page(
        self, page: fitz.Page, lines_to_remove: List[Tuple]
    ) -> int:
        """
        Remove detected lines from a PDF page by drawing white rectangles over them.

        Args:
            page: PyMuPDF page object
            lines_to_remove: List of line coordinates to remove

        Returns:
            Number of lines removed
        """
        removed_count = 0

        if not lines_to_remove:
            return 0

        print(f"Attempting to remove {len(lines_to_remove)} lines from page")

        # For each line to remove, draw a white rectangle over it
        for line in lines_to_remove:
            if len(line) == 4:
                x1, y1, x2, y2 = line

                # Create a rectangle that covers the line with some padding
                # Make it slightly wider to ensure complete coverage
                padding = 2.0
                rect_x1 = min(x1, x2) - padding
                rect_y1 = min(y1, y2) - padding
                rect_x2 = max(x1, x2) + padding
                rect_y2 = max(y1, y2) + padding

                # Create rectangle
                rect = fitz.Rect(rect_x1, rect_y1, rect_x2, rect_y2)

                # Draw a white filled rectangle over the line
                page.draw_rect(rect, color=None, fill=(1, 1, 1), width=0)

                removed_count += 1
                print(f"Covered line at ({x1:.1f}, {y1:.1f}) to ({x2:.1f}, {y2:.1f})")

        return removed_count

    def remove_lines_by_content_modification(
        self, page: fitz.Page, lines_to_remove: List[Tuple]
    ) -> int:
        """
        Alternative method to remove lines by modifying page content stream.
        This is more complex but might work better for some PDFs.

        Args:
            page: PyMuPDF page object
            lines_to_remove: List of line coordinates to remove

        Returns:
            Number of lines processed
        """
        if not lines_to_remove:
            return 0

        try:
            # Get the page's content stream
            content = page.get_contents()
            if not content:
                return 0

            # This is a more advanced approach that would require parsing
            # and modifying the PDF content stream directly
            # For now, we'll stick with the rectangle overlay method
            print("Content stream modification not implemented, using overlay method")
            return 0

        except Exception as e:
            print(f"Error in content modification: {str(e)}")
            return 0

    def process_pdf(self, input_path: str, output_path: str) -> bool:
        """
        Process a PDF file to remove vertical black lines.

        Args:
            input_path: Path to input PDF
            output_path: Path to output PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open the PDF
            doc = fitz.open(input_path)
            total_lines_removed = 0

            print(f"Processing PDF: {input_path}")
            print(f"Number of pages: {len(doc)}")

            for page_num in range(len(doc)):
                page = doc[page_num]
                print(f"\nProcessing page {page_num + 1}...")

                # Method 1: Detect lines from PDF drawing objects
                pdf_lines = self.detect_lines_from_pdf_objects(page)
                print(f"Found {len(pdf_lines)} potential vertical lines in PDF objects")

                # Method 2: Render page as image and detect lines
                # Get page as image for analysis
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better detection
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")

                # Convert to PIL Image and then to numpy array
                pil_img = Image.open(io.BytesIO(img_data))
                img_array = np.array(pil_img)

                # Detect lines in the image
                page_rect = page.rect
                image_lines = self.detect_vertical_lines_in_image(
                    img_array, page_rect.width
                )
                print(
                    f"Found {len(image_lines)} potential vertical lines in rendered image"
                )

                # Combine and filter detected lines
                all_lines = pdf_lines + [(x, y1, x, y2) for x, y1, y2 in image_lines]

                # Filter lines that are near the middle of the page
                middle_x = page_rect.width / 2
                filtered_lines = []

                for line in all_lines:
                    if len(line) == 4:
                        x1, y1, x2, y2 = line
                        line_x = (x1 + x2) / 2
                        distance_from_middle = abs(line_x - middle_x)

                        # Keep lines that are reasonably close to the middle
                        if distance_from_middle < page_rect.width * 0.4:
                            filtered_lines.append(line)

                print(f"Filtered to {len(filtered_lines)} lines near the middle")

                # Remove the detected lines
                if filtered_lines:
                    removed = self.remove_lines_from_page(page, filtered_lines)
                    total_lines_removed += removed
                    print(f"Removed {removed} lines from page {page_num + 1}")

            # Save the modified PDF
            doc.save(output_path)
            doc.close()

            print(f"\nProcessing complete!")
            print(f"Total lines removed: {total_lines_removed}")
            print(f"Output saved to: {output_path}")

            return True

        except Exception as e:
            print(f"Error processing PDF: {str(e)}")
            return False


if __name__ == "__main__":
    # Import required modules
    import io

    remover = VerticalLineRemover(tolerance=5.0, min_line_length=350.0)
    remover.process_pdf(
        # r"C:\Users\gjm\Downloads\f194b9d4-c072-4868-a42b-892a968d5d0_single_page.pdf",
        # file:///c%3A/Users/gjm/Projecte/PostCardDjango/postcard_with_qr.pdf
        r"C:\Users\gjm\Projecte\PostCardDjango\postcard_with_qr.pdf",
        "sample_output.pdf",
    )
