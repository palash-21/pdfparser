from operator import itemgetter
import fitz
import json
import numpy as np
import math
import tabula
import re
import pprint
import os


def fonts(doc, granularity=False):
    """Extracts fonts and their usage in PDF documents.

    :param doc: PDF document to iterate through
    :type doc: <class 'fitz.fitz.Document'>
    :param granularity: also use 'font', 'flags' and 'color' to discriminate text
    :type granularity: bool

    :rtype: [(font_size, count), (font_size, count}], dict
    :return: most used fonts sorted by count, font style information
    """
    styles = {}
    font_counts = {}

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:  # iterate through the text blocks
            if b['type'] == 0:  # block contains text
                for l in b["lines"]:  # iterate through the text lines
                    for s in l["spans"]:  # iterate through the text spans
                        if granularity:
                            identifier = "{0}_{1}_{2}_{3}".format(s['size'], s['flags'], s['font'], s['color'])
                            styles[identifier] = {'size': s['size'], 'flags': s['flags'], 'font': s['font'],
                                                  'color': s['color']}
                        else:
                            identifier = "{0}".format(s['size'])
                            styles[identifier] = {'size': s['size'], 'font': s['font']}

                        font_counts[identifier] = font_counts.get(identifier, 0) + 1  # count the fonts usage

    font_counts = sorted(font_counts.items(), key=itemgetter(1), reverse=True)

    if len(font_counts) < 1:
        raise ValueError("Zero discriminating fonts found!")

    return font_counts, styles


def get_deviation(inp_data, p_size):
    """Returns deviation from the given value(para_size)
    """
    data = np.array(inp_data)
    n = len(data)
    # mean = sum(data) / n
    deviations = [(x - p_size) ** 2 for x in data]
    variance = sum(deviations) / n
    std_dev = round(math.sqrt(variance),2)
    # print(std_dev)
    return std_dev


def font_tags(font_counts, styles):
    """Returns dictionary with font sizes as keys and tags as value.

    :param font_counts: (font_size, count) for all fonts occuring in document
    :type font_counts: list
    :param styles: all styles found in the document
    :type styles: dict

    :rtype: dict
    :return: all element tags based on font-sizes
    """
    p_style = styles[font_counts[0][0]]  # get style for most used font by count (paragraph)
    p_size = p_style['size']  # get the paragraph's size

    # sorting the font sizes high to low, so that we can append the right integer to each tag
    font_sizes = []
    for (font_size, count) in font_counts:
        font_sizes.append(float(font_size))
    font_sizes.sort(reverse=True)
    dev_font_sizes = get_deviation(font_sizes, p_size)
    # aggregating the tags for each font size
    idx = 0
    size_tag = {}
    for size in font_sizes:
        idx += 1
        if size == p_size:
            idx = 0
            size_tag[size] = 'para'
        if size > p_size:
          if size - p_size < dev_font_sizes :
              size_tag[size] = 'para'
          else:
              if idx in (0,1):
                  size_tag[size] = 'header/title'
              else:
                size_tag[size] = 'sub-title'
        elif size < p_size:
            if p_size - size < dev_font_sizes :
                size_tag[size] = 'para'
            else:
                size_tag[size] = 's'
    return size_tag


def check_footers(blocks, size_tag):
    """Checks for footers
    """
    footers = []
    len_blocks = len(blocks)
    for index,b in enumerate(blocks[::-1]):
        if b['type'] == 0:
            for l in b["lines"]:
                for s in l["spans"]:
                    if s['text'].strip():
                        if "s" in size_tag[s['size']]:
                            footers.append(len_blocks - index - 1)
                        else:
                            return footers
                    else:
                        return footers

def extract_tables_from_pdf(pdf_path, pages="all"):
    """ Extract all tables from the PDF
    """
    tables = []
    extracted_tables = tabula.read_pdf(pdf_path, pages=pages, multiple_tables=True)
    if extracted_tables:
      tables = extracted_tables
    return tables


pattern_heading = "^\d+[)\.\sa-zA-Z0-9]+\\n"  # Like 1. Header, 1) Header, 1 header, etc
pattern_subheading = "^(\d+\.\d+[\)\.]?\s*)(.+)\n"  # Like 1.1 Header, 1.2) Header, 1.4. header, etc


def extract_elements(doc, size_tag, out_folder, doc_path):
    """Scrapes headers & paragraphs from PDF and return texts with element tags.

    :param doc: PDF document to iterate through
    :type doc: <class 'fitz.fitz.Document'>
    :param size_tag: textual element tags for each size
    :type size_tag: dict

    :rtype: list
    :return: texts with pre-prended element tags
    """
    elements = []
    first = True  # boolean operator for first header
    previous_s = {}  # previous span
    for page_number, page in enumerate(doc):

        # Extracting images
        images = page.get_images(full=True)
        for img_index, img in enumerate(images):
            xref = img[0]  # The image reference
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]  # Image format (e.g., 'png', 'jpeg')

            # Save the extracted image
            image_filename = f"page_{page_number+1}_image_{img_index + 1}.{image_ext}"
            image_file_path = os.path.join(out_folder, image_filename)
            with open(image_file_path, "wb") as image_file:
                image_file.write(image_bytes)
            element= {"type": "image",
                       "text": image_file_path,
                       "page": page_number + 1}
            elements.append(element)

        # Extracting tables
        extracted_tables = extract_tables_from_pdf(doc_path, pages=(page_number + 1,))
        for i, table in enumerate(extracted_tables):
            # Save each table as a CSV file
            csv_file_name = f"page_{page_number+1}_table_{i+1}.csv"
            csv_file_path = os.path.join(out_folder, csv_file_name)
            table.to_csv(csv_file_path, index=False)
            # print(f"Extracted table {i+1}")
            element= {"type": "table",
                       "text": csv_file_path,
                       "page": page_number + 1}
            elements.append(element)

        # Extracting text elements
        blocks = page.get_text("dict")["blocks"]
        # checking if footer is present
        footer_indexes = check_footers(blocks, size_tag)
        for index,b in enumerate(blocks):  # iterate through the text blocks
            if b['type'] == 0:  # this block contains text
                block_string = ""  # text found in block
                for l in b["lines"]:  # iterate through the text lines
                    for s in l["spans"]:  # iterate through the text spans
                        if s['text'].strip():  # removing whitespaces:
                            if first:
                                previous_s = s
                                first = False
                                block_size_tag = size_tag[s['size']]
                                block_string = s['text']
                            else:
                                if s['size'] == previous_s['size']:
                                    if block_string and all((c == "|") for c in block_string):
                                        # block_string only contains pipes
                                        block_size_tag = size_tag[s['size']]
                                        if "s" in block_size_tag and index in footer_indexes:
                                            block_size_tag = "footer"
                                        elif block_size_tag in ("sub-title", "header/title"):
                                            if len(s['text']) > 60:
                                                block_size_tag = "para"
                                            elif re.match(pattern_subheading, s['text']):
                                                block_size_tag = "sub-heading"
                                            elif re.match(pattern_heading, s['text']):
                                                block_size_tag = "heading"
                                            else:
                                                block_size_tag = "para"
                                        elif block_size_tag == "para" and len(s['text']) < 60:
                                            block_size_tag = "sub-title"
                                        block_string = s['text']
                                    if block_string == "":
                                        # new block has started, so append size tag
                                        block_size_tag = size_tag[s['size']]
                                        if "s" in block_size_tag and index in footer_indexes:
                                            block_size_tag = "footer"
                                        elif block_size_tag in ("sub-title", "header/title"):
                                            if len(s['text']) > 60:
                                                block_size_tag = "para"
                                            elif re.match(pattern_subheading, s['text']):
                                                block_size_tag = "sub-heading"
                                            elif re.match(pattern_heading, s['text']):
                                                block_size_tag = "heading"
                                            else:
                                                block_size_tag = "para"
                                        elif block_size_tag == "para" and len(s['text']) < 60:
                                            block_size_tag = "other"
                                        block_string = s['text']
                                    else:  # in the same block, so concatenate strings
                                        block_string += " " + s['text']

                                else:
                                    if len(block_string) >= 4:
                                        element = {"type": block_size_tag,
                                                   "text": block_string,
                                                   "page": page_number + 1}
                                        elements.append(element)
                                        # if block_size_tag in element_dict:
                                        #     element_dict[block_size_tag].append(block_string)
                                        # else:
                                        #   element_dict[block_size_tag] = [block_string]
                                    # header_para.append(block_string)
                                    block_size_tag = size_tag[s['size']]
                                    if "s" in block_size_tag and index in footer_indexes:
                                            block_size_tag = "footer"
                                    elif block_size_tag in ("sub-title", "header/title"):
                                        if len(s['text']) > 60:
                                            block_size_tag = "para"
                                        elif re.match(pattern_subheading, s['text']):
                                            block_size_tag = "sub-heading"
                                        elif re.match(pattern_heading, s['text']):
                                            block_size_tag = "heading"
                                        else:
                                            block_size_tag = "para"
                                    elif block_size_tag == "para" and len(s['text']) < 60:
                                        block_size_tag = "other"
                                    block_string = s['text']

                                previous_s = s

                    # new block started, indicating with a pipe
                    # block_string += "|"
                if len(block_string) >= 4:
                    element = {"type": block_size_tag,
                                "text": block_string,
                                "page": page_number + 1}
                    elements.append(element)
    return elements


def is_pdf(file_path):
    # Check if the file has a PDF extension
    if not file_path.lower().endswith('.pdf'):
        return False

    # Check the PDF header
    try:
        with open(file_path, 'rb') as file:
            header = file.read(4)
            # The PDF header should start with %PDF
            return header == b'%PDF'
    except Exception:
        return False


def main(pdf_path):
    file_name = os.path.basename(pdf_path)
    doc = fitz.open(pdf_path)
    font_counts, styles = fonts(doc, granularity=False)
    size_tag = font_tags(font_counts, styles)
    output_folder_name = file_name.split(".")[0]
    if not os.path.exists(output_folder_name):
        os.mkdir(output_folder_name)
    elements = extract_elements(doc, size_tag, output_folder_name, pdf_path)
    elememts_dict = {"elements": elements}
    print(json.dumps(elememts_dict, indent=4))
    out_file = f"{output_folder_name}_elements.json"
    with open(out_file, 'w+') as json_file:
        json.dump(elememts_dict, json_file, indent=4)

if __name__ == "__main__":
    pdf_path = str(input("Enter the PDF filename(or press ENTER if filename is document.pdf):"))
    if not pdf_path:
        pdf_path = "document.pdf"
    if not is_pdf(pdf_path):
            print(f"Please give a valid pdf file as input")
    if not os.path.isfile(pdf_path):
        print(f"PDF file not found in current directory: {pdf_path}")
    else:
        main(pdf_path)
