
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

def generate_precise_html(pdf_path, output_html):
    doc = fitz.open(pdf_path)
    soup = BeautifulSoup('<html><head><meta charset="utf-8"><style>body{margin:0;position:relative;} .txt{position:absolute;white-space:pre;}</style></head><body></body></html>', 'html.parser')
    body = soup.body

    for page_num, page in enumerate(doc, start=1):
        page_div = soup.new_tag('div', **{'style': f'position:relative; width:{page.rect.width}px; height:{page.rect.height}px; border-bottom:1px dashed #ccc; margin-bottom:20px;'})

        text_blocks = page.get_text("dict")["blocks"]
        for block in text_blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        style = (
                            f"left:{span['bbox'][0]}px;"
                            f"top:{span['bbox'][1]}px;"
                            f"font-size:{span['size']}px;"
                            f"font-family:'{span['font']}';"
                            f"color:#{int(span['color']):06x};"
                        )
                        span_tag = soup.new_tag("div", **{"class": "txt", "style": style})
                        span_tag.string = span["text"]
                        page_div.append(span_tag)
            elif "image" in block:
                # опционально вставка изображения — можно расширить здесь
                pass

        body.append(page_div)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(str(soup.prettify()))
    print(f"✅ HTML сохранён: {output_html}")

generate_precise_html("pdf2html_test_tables-3.pdf", "exact_output.html")


