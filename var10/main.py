import fitz
from collections import defaultdict


def pdf_to_html(pdf_path, html_path):
    doc = fitz.open(pdf_path)
    html = []

    html.append('''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PDF Conversion</title>
    <style>
        body { 
            font-family: Arial, sans-serif;
            line-height: 1.4;
            white-space: pre-wrap;
        }
        .page {
            margin: 0 auto;
            padding: 20px;
            max-width: 100%;
        }
        .text-block {
            margin-bottom: 0.5em;
        }
        .table-wrapper {
            margin: 1em 0;
            overflow-x: auto;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 0.5em 0;
        }
        td, th {
            border: 1px solid #ddd;
            padding: 4px 8px;
            vertical-align: top;
        }
        .indent {
            margin-left: 2em;
        }
    </style>
</head>
<body>''')

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_IMAGES)["blocks"]

        html.append(f'<div class="page" data-page="{page_num + 1}">')

        # Собираем все элементы страницы
        elements = []

        for block in blocks:
            if block["type"] == 0:  # Text block
                text_lines = []
                for line in block["lines"]:
                    line_text = []
                    for span in line["spans"]:
                        style = {
                            "font-family": span["font"],
                            "font-size": f"{span['size']}px",
                            "font-weight": "bold" if span["flags"] & 2 ** 0 else "normal",
                            "font-style": "italic" if span["flags"] & 2 ** 1 else "normal"
                        }
                        style_str = "; ".join(f"{k}: {v}" for k, v in style.items())
                        line_text.append(f'<span style="{style_str}">{span["text"]}</span>')
                    text_lines.append("".join(line_text))
                elements.append({
                    "type": "text",
                    "bbox": block["bbox"],
                    "content": "<br>".join(text_lines),
                    "indent": block["bbox"][0] > 50  # Простое определение отступа
                })

            elif block["type"] == 1:  # Image block
                pass  # Пропускаем изображения для этого примера

        # Обрабатываем таблицы
        tables = page.find_tables()
        for table in tables:
            cells = table.extract()
            table_html = ['<table>']
            for row in cells:
                table_html.append('<tr>')
                for cell in row:
                    table_html.append(f'<td>{cell}</td>')
                table_html.append('</tr>')
            table_html.append('</table>')

            elements.append({
                "type": "table",
                "bbox": table.bbox,
                "content": "".join(table_html)
            })

        # Сортируем элементы по вертикальной позиции
        elements.sort(key=lambda x: x["bbox"][1])

        # Группируем близкие по вертикали элементы
        grouped_elements = []
        current_group = []
        last_y = None

        for elem in elements:
            if last_y is None or abs(elem["bbox"][1] - last_y) < 15:  # Группировка с допуском 15px
                current_group.append(elem)
            else:
                if current_group:
                    grouped_elements.append(current_group)
                current_group = [elem]
            last_y = elem["bbox"][1]

        if current_group:
            grouped_elements.append(current_group)

        # Рендерим элементы
        for group in grouped_elements:
            # Сортируем элементы в группе по горизонтали
            group.sort(key=lambda x: x["bbox"][0])

            for elem in group:
                if elem["type"] == "text":
                    wrapper_class = "indent" if elem["indent"] else ""
                    html.append(f'<div class="text-block {wrapper_class}">{elem["content"]}</div>')
                elif elem["type"] == "table":
                    html.append(f'<div class="table-wrapper">{elem["content"]}</div>')

        html.append('</div>')

    html.append('</body></html>')

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html))


# пример запуска
pdf_to_html('example.pdf', 'output.html')
