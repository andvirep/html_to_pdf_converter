import glob
import os
from pathlib import Path

import img2pdf
from pdf2image import convert_from_path
from PIL import Image

pdf_path = 'example.pdf'
img_path = "tmp_images/page_001.png"

# # find current path
# current_path = os.path.dirname(os.path.abspath(__file__))
# print('current_path =', current_path)
# # print all pdfs in current path
# all_pdfs = glob.glob(f".example.pdf")
# print('all_pdfs =', all_pdfs)
#
# # find target pdf
# # target_pdf_path = input("input target pdf path:")
# target_pdf_path = '.'
#
# # make path for images
# images_path = os.path.join(current_path, "book_images")
# print("images will be here =", images_path)
# Path(images_path).mkdir(exist_ok=True)
#
# dpi = input("input dpi, default is 500:")
# dpi = dpi or 500
# # convert pdf to images
# pages = convert_from_path(target_pdf_path, 500)
# images = list()
# for count, page in enumerate(pages):
#     image_path = os.path.join(images_path, f"out{count}.jpg")
#     images.append(image_path)
#     page.save(image_path, "JPEG")
#
# print(f"Successfully made pdf file {pdf_path}")




import cv2
import numpy as np
import pytesseract
from pytesseract import Output
import html

def detect_table_cells(img, debug=False):
    # 1. Серый + бинаризация инверсией
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    binar = cv2.adaptiveThreshold(
        ~gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY, 15, -2
    )

    # 2. Горизонтальные линии
    horiz = binar.copy()
    cols = horiz.shape[1]
    size = cols // 40
    kern_h = cv2.getStructuringElement(cv2.MORPH_RECT, (size, 1))
    horiz = cv2.erode(horiz, kern_h)
    horiz = cv2.dilate(horiz, kern_h)

    # 3. Вертикальные линии
    vert = binar.copy()
    rows = vert.shape[0]
    size = rows // 40
    kern_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, size))
    vert = cv2.erode(vert, kern_v)
    vert = cv2.dilate(vert, kern_v)

    # 4. Пересечение = маска клеток
    mask = cv2.bitwise_and(horiz, vert)
    if debug:
        cv2.imwrite("table_mask.png", mask)

    # 5. Поиск контуров ячеек
    cnts, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(c) for c in cnts]
    # отбрасываем слишком мелкие
    cells = [b for b in boxes if b[2] > 30 and b[3] > 20]

    # 6. Группируем ячейки в строки по y
    cells.sort(key=lambda b:(b[1], b[0]))
    rows = []
    tol = 10
    for x,y,w,h in cells:
        placed = False
        for row in rows:
            if abs(row[0][1] - y) < tol:
                row.append((x,y,w,h))
                placed = True
                break
        if not placed:
            rows.append([(x,y,w,h)])
    # сортируем столбцы по x
    grid = [sorted(r, key=lambda b:b[0]) for r in rows]
    return grid, mask

def ocr_cell(img, box, lang='chi_sim+chi_tra+eng+rus'):
    x,y,w,h = box
    crop = img[y:y+h, x:x+w]
    txt = pytesseract.image_to_string(
        crop, lang=lang, config='--psm 6'
    )
    txt = html.escape(txt.strip()).replace('\n','<br/>')
    return txt

def ocr_free_text(img, table_mask, lang='chi_sim+chi_tra+eng+rus'):
    # удаляем области таблиц
    inv = cv2.bitwise_not(table_mask)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bg = cv2.bitwise_and(gray, gray, mask=inv)

    data = pytesseract.image_to_data(
        bg, lang=lang, output_type=Output.DICT
    )
    spans = []
    n = len(data['text'])
    for i in range(n):
        txt = data['text'][i].strip()
        if not txt: continue
        conf = int(data['conf'][i])
        if conf < 50: continue
        x,y,w,h = (data['left'][i], data['top'][i],
                   data['width'][i], data['height'][i])
        spans.append({
            'text': html.escape(txt).replace(' ','&nbsp;'),
            'x': x, 'y': y
        })
    return spans

def image_to_html(img_path, out_html="out.html"):
    img = cv2.imread(img_path)
    grid, mask = detect_table_cells(img)
    spans = ocr_free_text(img, mask)
    tables = []
    for row in grid:
        cells = [ocr_cell(img, box) for box in row]
        tables.append((row, cells))

    # Начинаем формировать HTML
    html_out = ['<html><head><meta charset="utf-8"></head><body>']

    # 1) свободный текст
    html_out.append('<div style="position:relative;">')
    for sp in spans:
        style = f'position:absolute; left:{sp["x"]}px; top:{sp["y"]}px;'
        html_out.append(f'<span style="{style}">{sp["text"]}</span>')
    html_out.append('</div>')

    # 2) таблицы с линиями
    for row_boxes, row_texts in tables:
        # определяем координаты таблицы
        xs = [x for x,_,_,_ in row_boxes]
        ys = [y for _,y,_,_ in row_boxes]
        left, top = min(xs), min(ys)
        # рисуем HTML-таблицу
        tbl_style = (
            f'position:absolute; left:{left}px; top:{top}px; '
            'border-collapse:collapse;'
        )
        html_out.append(f'<table style="{tbl_style}" '
                        'border="1" cellspacing="0" cellpadding="4">')
        # по одной строке (только по примеру)
        html_out.append('<tr>')
        for cell_html in row_texts:
            html_out.append(f'<td style="border:1px solid #000;">'
                            f'{cell_html}</td>')
        html_out.append('</tr></table><br/>')

    html_out.append('</body></html>')

    with open(out_html, "w", encoding="utf-8") as f:
        f.write("\n".join(html_out))



if __name__=="__main__":
    # Передайте сюда свой PNG/JPG, полученный из PDF
    image_to_html(img_path, "page.html")
