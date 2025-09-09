# Constants for standard postcard sizes (in mm)
# TODO Besprechen
paper_Standards = {
    "A0": (841, 1189),
    "A1": (594, 841),
    "A2": (420, 594),
    "A3": (297, 420),
    "A4": (210, 297),
    "A4+": (210, 297),
    "A5": (148, 210),
    "A5+": (148, 210),
    "A6": (105, 148),
    "A6": (105 + 3, 148 + 3),  # Including bleed area
    "A7": (74, 105),
    "A8": (52, 74),
    "A9": (37, 52),
    "A10": (26, 37),
}


supported_formats = ["A6+"]  # Supported postcard formats
