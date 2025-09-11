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
    "A6+": (105 + 2 * 3, 148 + 2 * 3),  # Including bleed area
    "A7": (74, 105),
    "A8": (52, 74),
    "A9": (37, 52),
    "A10": (26, 37),
}


supported_formats = ["A6+"]  # Supported postcard formats

default_format = "A6"  # Default postcard format
default_format_with_bleed = "A6+"  # Default postcard format with bleed area


def get_postcard_size(format_name):  # in postcard style...
    """Get the dimensions of the postcard format in mm."""
    if format_name in paper_Standards:
        return (paper_Standards[format_name][1], paper_Standards[format_name][0])
    else:
        raise ValueError(f"Unsupported postcard format: {format_name}")


def get_default_postcard_size():
    """Get the default postcard size in mm."""
    return get_postcard_size(default_format)


def get_default_cutting_size():
    """returns the default cutting size in mm: bleed area - default postcard size"""
    bleed_area = get_postcard_size(default_format_with_bleed)
    postcard_size = get_postcard_size(default_format)
    return (
        (bleed_area[0] - postcard_size[0]) / 2,
        (bleed_area[1] - postcard_size[1]) / 2,
    )


def get_default_postcard_size_with_bleeding():
    """Get the default postcard size with bleed area in mm."""
    return get_postcard_size(default_format_with_bleed)
