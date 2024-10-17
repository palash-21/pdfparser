# pdfparser
Extract information from pdf like Headers, Paragraphs, Tables, Images, Footers

# TO run the file , need to install pymupdf and tabula in your python3 env
- pip install pymupdf
- pip install tabula-py

# Keep your pdf file in the same directory as the python file or provide the full path when asked for file
- I have kept both the notebook and python file option
- Give file as input to the script, default document.pdf
- The output will be stored in json format in a json file
- The images and tables (csv) will also be stored in a folder with same name as the pdf

# Tools used :
There wide range of tools available to extract text, tables, images from pdf.
I tried some of them namely PyMuPDF, camelot-py, tabula-py, pdfplumber, pikepdf, pdfminer.six
Finally i used PyMuPDF for extracting texts and images, tabula-py for extracting tables beacuse of following reasons:
  - PyMuPDF (fitz) works best for raster images (like JPEG or PNG) that are embedded in PDFs. The improved code helps in capturing more images and handling failures more gracefully.
  - Tabula : It works well for both structured tables with gridlines and unstructured tables without gridlines.

# Scope of improvemnet :
- Categorizing textual data into headers, sub-titles, footers using font style as well as font-size.
- Use OCR for image recognition.
- Convert each page to image using pdf2image and then using AI to extract data from the pages.
- For large pdfs process multiple pages in parallel to reduce the execution time considereably.
