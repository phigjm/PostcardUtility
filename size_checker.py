from pdfutilities.page_size import get_page_size_mm


def process_and_check_pdf(
    pdf_path: str,
) -> dict:
    """this method checks the pdf for printability and returns a json with checks and possible issues."""
    # please implement this method:
    # create/use helpter Methods and make the code modular and configuratable. create a method to proccess every page. Make where meaningfull the changes configuratable (e.g. instead of scaling: add white space, instead of stretching add whitespace, )
    # A6 and A6+ are just examples. where A6 is the actually size and A6+ is the bleach size calculated by a6+3mm, where 3mm should also be a variable. The code should be easily adaptable to other sizes and formats.

    # check if pdf has two pages
    # if not add a warning to json output and only use the first two pages and ignore the rest.

    # the following needs to be done for each page

    # first check if the pdf is in postcard format (A6+) (only the aspect ratio matters, Landscape or portrait is ok)
    # if A6+ ratio make a note to json output that it is A6+
    # if pdf needs to be scaled to A6+ make a note to json output that it is scaled to A6+
    # check if pdf has a boarder (no matter what color) and make a note to json output that boarder is detected, color and how big it is.
    # if the boarder is smaller than 5mm+3mm (5mm if it would be scaled to A6+) make a warning note to json output that the boarder is too small and might be cut off. (an option would be to scale the pdf down so that the boarder is at least 5mm+3mm if it would be scaled to A6+ and pad with the correct color)

    # if not exactly A6+ assume pdf is A6
    # scale pdf as best as possible to A6 without overscalling it. Make a note to json output that it is scaled to A6
    # check if pdf has a boarder (no matter what color) and make a note to json output that boarder is detected, color and how big it is.
    # if the boarder is smaller than 5mm+3mm (5mm if it would be scaled to A6+) make a warning note to json output that the boarder is too small and might be cut off. (an option would be to scale the pdf down so that the boarder is at least 5mm+3mm if it would be scaled to A6+ and pad with the correct color)

    # if no boarder is detected: scale the pdf to A6+ at the best possible way (centered, with  overscaling), and add a note to json output that it is scaled to A6+ and cut away the edges so that it fits A6+.

    # now the first two pdf pages should be a6+
    # check if pdf is cmyk. if not add a note to json output and convert to cmyk
