import fitz   # pip install PyMuPDF
import html
from collections import defaultdict

def overlaps(b1, b2, tol=1.0):
    return not (b1[3] < b2[1] - tol or b1[1] > b2[3] + tol)

def pdf_to_html(pdf_path: str, html_path: str):
    doc = fitz.open(pdf_path)
    out = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>",
        "<style>",
        "  body { font-family:sans-serif; font-size:14px; line-height:1.5; }",
        "  p { margin:0.5em 0; white-space:pre-wrap; }",
        "  table { border-collapse:collapse; margin:0.5em 0; width:100%; }",
        "  td,th { border:1px solid #444; padding:4px; vertical-align:top; }",
        "</style>",
        "</head><body>"
    ]

    for page in doc:
        blocks = []

        # 1) извлечь таблицы
        for tbl in page.find_tables():
            x0, y0, x1, y1 = tbl.bbox
            # получить matrix строк через extract()
            rows = tbl.extract()  # List[List[str]]
            tbl_html = ["<table>"]
            for row in rows:
                tbl_html.append("<tr>")
                for cell in row:
                    txt = html.escape(cell or "").replace("\n","<br>")
                    tbl_html.append(f"<td>{txt}</td>")
                tbl_html.append("</tr>")
            tbl_html.append("</table>")
            blocks.append((y0, x0, "".join(tbl_html)))

        # 2) извлечь текстовые блоки вне таблиц
        table_bboxes = [t.bbox for t in page.find_tables()]
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            bb = b["bbox"]
            if any(overlaps(bb, tb) for tb in table_bboxes):
                continue
            y0, x0 = bb[1], bb[0]
            p = ["<p>"]
            for line in b["lines"]:
                for sp in line["spans"]:
                    style = (
                        f"font-family:'{sp.get('font','')}';"
                        f"font-size:{sp.get('size',0)}px;"
                        f"color:#{sp.get('color',0):06x}"
                    )
                    p.append(f"<span style=\"{style}\">{html.escape(sp['text'])}</span>")
                p.append("<br>")
            p.append("</p>")
            blocks.append((y0, x0, "".join(p)))

        # 3) сортировка по y затем x и добавление в выход
        for _, _, html_block in sorted(blocks, key=lambda x: (x[0], x[1])):
            out.append(html_block)

    out.append("</body></html>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))

# пример:
# pdf_to_html("input.pdf", "output.html")

pdf_to_html('example.pdf', 'output.html')
