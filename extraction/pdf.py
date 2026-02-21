import PyPDF2
from .ocr import extract_text_from_pdf_ocr


def extract_text_from_pdf(file):

    try:

        reader = PyPDF2.PdfReader(file)

        text = ""

        for page in reader.pages:

            content = page.extract_text()

            if content:

                text += content

        if len(text.strip()) < 20:

            file.seek(0)

            text = extract_text_from_pdf_ocr(file)

        return text

    except:

        file.seek(0)

        return extract_text_from_pdf_ocr(file)

