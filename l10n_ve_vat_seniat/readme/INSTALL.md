The RIF OCR lookup needs the Python packages `requests`, `Pillow` and
`pytesseract`, plus the `tesseract` binary on the server PATH. The module
can be installed without Tesseract; SENIAT queries that use OCR will fail
until the binary is present.

On Debian or Ubuntu:

    apt install tesseract-ocr
    pip install requests Pillow pytesseract
