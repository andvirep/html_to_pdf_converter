import fitz  # PyMuPDF
from bs4 import BeautifulSoup


def pdf_to_html(pdf_path, output_html_path):
    doc = fitz.open(pdf_path)
    soup = BeautifulSoup(features='html.parser')
    html = soup.new_tag('html')
    soup.append(html)
    head = soup.new_tag('head')
    html.append(head)
    meta = soup.new_tag('meta', charset='UTF-8')
    head.append(meta)
    title = soup.new_tag('title')
    title.string = 'PDF to HTML'
    head.append(title)
    style = soup.new_tag('style')
    style.string = '''
        body { position: relative; }
        .page { position: relative; margin-bottom: 20px; }
        .text { position: absolute; white-space: pre; font-family: monospace; }
    '''
    head.append(style)
    body = soup.new_tag('body')
    html.append(body)
    for page_num, page in enumerate(doc):
        # Получаем размеры страницы
        width, height = page.rect.width, page.rect.height
        page_div = soup.new_tag('div', **{'class': 'page', 'style': f'width:{width}pt; height:{height}pt;'})
        body.append(page_div)
        # Извлекаем текст с координатами
        text_instances = page.get_text("dict")["blocks"]
        for block in text_instances:
            if block['type'] == 0:  # текст
                for line in block["lines"]:
                    for span in line["spans"]:
                        x, y = span["origin"]
                        text = span["text"]
                        span_tag = soup.new_tag('div', **{'class': 'text'})
                        span_tag.string = text
                        # Координаты в PDF: (0,0) в левом нижнем углу, в HTML - в левом верхнем.
                        # Поэтому преобразуем y: y_pdf -> y_html = height - y_pdf - высота_текста?
                        # Но в span["bbox"] есть координаты: [x0, y0, x1, y1]
                        # Мы можем использовать bbox для позиционирования и размера.
                        # Однако, для простоты используем только origin и игнорируем высоту строки.
                        # Точнее: позиционируем по верхнему левому углу, но в PDF координата origin - это базовая линия.
                        # Чтобы упростить, используем bbox.
                        bbox = span["bbox"]
                        # Высота элемента: bbox[3] - bbox[1]
                        # Но в HTML мы хотим позиционировать по верхнему левому углу.
                        # Координата y в HTML: bbox[1] (но в PDF y растет снизу вверх, а в HTML сверху вниз)
                        # Поэтому: top = bbox[1]
                        # Но тогда текст будет перевернут. Надо: top = height - bbox[3]
                        top = height - bbox[3]  # верхний край блока
                        left = bbox[0]
                        span_tag['style'] = f'left:{left}pt; top:{top}pt;'
                        page_div.append(span_tag)
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    doc.close()

# Использование функции
pdf_path = 'pdf2html_test_tables-3.pdf'  # Замените на путь к вашему PDF
output_html_path = 'output.html'  # Путь для сохранения HTML
pdf_to_html(pdf_path, output_html_path)