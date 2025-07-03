import fitz  # PyMuPDF
import re
import html

INPUT_PDF = "example.pdf"
OUTPUT_HTML = "output.html"

CSS = '''<style type="text/css">
.ev-t_table { border-collapse: collapse; border-top: 2px solid black; border-bottom: 2px solid black; border-right: none; border-left: none; width: 100%; margin-top: 3px; margin-bottom: 3px; font: 11px SimSun }
.ev-t_th { border-top: 1px solid black; border-bottom: 1px solid black; border-right: 1px solid black; border-left: 1px solid black; text-align: left; padding: 8px; }
.ev-t_td { border-top: 1px solid black; border-bottom: 1px solid black; border-right: 1px solid black; border-left: 1px solid black; text-align: left; padding: 8px; }
.ev-t_page{position:relative; overflow: hidden;margin: 67px 0px 61px 92px;padding: 0px;border: none;width:650px;}
.ev-t_h1{text-align: center;margin-top: 30px;margin-bottom: 20px; font-size: 26px; font-family: SimSun; font-weight: bold;}
.ev-t_par{text-align: justify;padding-right: 0px;margin-top: 0px;margin-bottom: 0px; font-size: 14px; font-family: SimSun;line-height: 24px;}
.ev-t_spacer {height: 24px;}
</style>'''

def extract_tables(page):
    tables = []
    for table in page.find_tables():
        x0, y0, x1, y1 = table.bbox
        rows = table.extract()
        cell_bboxes = getattr(table, 'cells', None)
        tables.append({
            'bbox': (x0, y0, x1, y1),
            'rows': rows,
            'cell_bboxes': cell_bboxes,
            'y': y0,
            'x': x0
        })
    return tables

def extract_blocks_lines_spans(page):
    blocks = []

    for block in page.get_text("dict")['blocks']:
        if block['type'] != 0:
            continue
        block_lines = []
        for line in block['lines']:
            line_spans = []
            for span in line['spans']:
                text = span['text']
                if text.strip():
                    line_spans.append({
                        'text': text,
                        'size': span['size'],
                        'font': span['font'],
                        'bbox': span['bbox'],
                        'y': span['bbox'][1],
                        'x': span['bbox'][0]
                    })
            if line_spans:
                block_lines.append(line_spans)
        if block_lines:
            blocks.append(block_lines)
    return blocks

def group_lines_to_paragraphs(lines, indent_tol=20, break_factor=1.5):
    paragraphs = []
    current_para = []
    last_y = None
    last_x = None
    line_gaps = []
    for i, line in enumerate(lines):
        line_y = min(span['y'] for span in line)
        if last_y is not None:
            gap = line_y - last_y
            line_gaps.append(gap)
        last_y = line_y
    # Calculate median gap
    median_gap = sorted(line_gaps)[len(line_gaps)//2] if line_gaps else 12
    last_y = None
    last_x = None
    for i, line in enumerate(lines):
        line_y = min(span['y'] for span in line)
        line_x = min(span['x'] for span in line)
        if last_y is not None:
            gap = line_y - last_y
            indent = line_x - last_x if last_x is not None else 0
            if gap > break_factor * median_gap or indent > indent_tol:
                if current_para:
                    paragraphs.append(current_para)
                current_para = [line]
            else:
                current_para.append(line)
        else:
            current_para.append(line)
        last_y = line_y
        last_x = line_x
    if current_para:
        paragraphs.append(current_para)
    return paragraphs

def is_overlap(b1, b2, tol=1.0):
    return not (b1[2] < b2[0] - tol or b1[0] > b2[2] + tol or b1[3] < b2[1] - tol or b1[1] > b2[3] + tol)

def classify_paragraph(paragraph):
    first_line = paragraph[0] if isinstance(paragraph[0], list) else paragraph[0]['line']
    first_span = first_line[0]
    size = first_span['size']
    text = ''.join(span['text'] for line in (l if isinstance(l, list) else l['line'] for l in paragraph) for span in line)
    if size >= 20 or (re.match(r'[表|图]\d', text) and size >= 16):
        return 'h1'
    if '注:' in text or '资料来源' in text:
        return 'note'
    if re.match(r'\s*$', text):
        return 'spacer'
    return 'par'

def detect_merged_cells(table_rows):
    n_rows = len(table_rows)
    n_cols = max(len(row) for row in table_rows)
    # Build a grid to mark merged cells
    grid = [[{'text': table_rows[r][c] if c < len(table_rows[r]) else '', 'rowspan': 1, 'colspan': 1, 'used': False}
             for c in range(n_cols)] for r in range(n_rows)]
    # Detect colspan (horizontal merge)
    for r in range(n_rows):
        c = 0
        while c < n_cols:
            cell = grid[r][c]
            if cell['text'] == '' and c > 0 and grid[r][c-1]['text'] != '' and not grid[r][c-1]['used']:
                grid[r][c-1]['colspan'] += 1
                cell['used'] = True
            c += 1
    # Detect rowspan (vertical merge)
    for c in range(n_cols):
        r = 0
        while r < n_rows:
            cell = grid[r][c]
            if cell['text'] == '' and r > 0 and grid[r-1][c]['text'] != '' and not grid[r-1][c]['used']:
                grid[r-1][c]['rowspan'] += 1
                cell['used'] = True
            r += 1
    return grid, n_rows, n_cols

def detect_merged_cells_bbox(table_rows, cell_bboxes):
    n_rows = len(table_rows)
    n_cols = max(len(row) for row in table_rows)

    # Build a 2D grid of cell indices to bbox
    grid = [[{'text': '', 'rowspan': 1, 'colspan': 1, 'used': False, 'bbox': None}
             for c in range(n_cols)] for r in range(n_rows)]

    # Map each non-empty cell to its bbox and text, skipping empty cells for merged regions
    bbox_idx = 0
    for r in range(n_rows):
        for c in range(len(table_rows[r])):
            cell_text = table_rows[r][c]
            grid[r][c]['text'] = cell_text
            if cell_text and str(cell_text).strip() != '':
                bbox = cell_bboxes[bbox_idx] if cell_bboxes and bbox_idx < len(cell_bboxes) else None
                grid[r][c]['bbox'] = tuple(bbox) if bbox is not None else None
                bbox_idx += 1
            else:
                grid[r][c]['bbox'] = None

    # Group all cells by bbox
    bbox_to_cells = {}
    for r in range(n_rows):
        for c in range(n_cols):
            bbox = grid[r][c]['bbox']
            if bbox is None:
                continue
            bbox_to_cells.setdefault(bbox, []).append((r, c))

    # For each bbox group, find the min/max row/col to determine span
    for bbox, cells in bbox_to_cells.items():
        rows = [r for r, c in cells]
        cols = [c for r, c in cells]
        min_r, max_r = min(rows), max(rows)
        min_c, max_c = min(cols), max(cols)
        rowspan = max_r - min_r + 1
        colspan = max_c - min_c + 1
        # Mark all but the top-left cell as used
        for r, c in cells:
            if (r, c) == (min_r, min_c):
                grid[r][c]['rowspan'] = rowspan
                grid[r][c]['colspan'] = colspan
            else:
                grid[r][c]['used'] = True

    # Debug print
    print('DEBUG: Merged cell structure (after bbox analysis):')
    for r in range(n_rows):
        row_repr = []
        for c in range(n_cols):
            cell = grid[r][c]
            if cell['used']:
                row_repr.append('X')
            else:
                rc_info = ''
                if cell['rowspan'] > 1:
                    rc_info += f'R{cell["rowspan"]}'
                if cell['colspan'] > 1:
                    rc_info += f'C{cell["colspan"]}'
                row_repr.append(rc_info or '1')
        print(' '.join(row_repr))

    return grid, n_rows, n_cols

def render_table(table):
    table_rows = table['rows']
    cell_bboxes = table.get('cell_bboxes', None)
    if cell_bboxes:
        print(f"DEBUG: table['cell_bboxes'] = {cell_bboxes}")
        print("DEBUG: Using bbox-based merged cell detection.")
        grid, n_rows, n_cols = detect_merged_cells_bbox(table_rows, cell_bboxes)
    else:
        print("DEBUG: No cell_bboxes found for table, using text-based merge heuristic.")
        grid, n_rows, n_cols = detect_merged_cells(table_rows)
    html_out = ["<table class='ev-t_table'><tbody class='ev-t_tbody'>"]
    for r in range(n_rows):
        html_out.append("<tr class='ev-t_tr'>")
        for c in range(n_cols):
            cell = grid[r][c]
            if cell.get('used'):
                continue
            attrs = []
            if cell.get('rowspan', 1) > 1:
                attrs.append(f"rowspan='{cell['rowspan']}'")
            if cell.get('colspan', 1) > 1:
                attrs.append(f"colspan='{cell['colspan']}'")
            cell_lines = (cell['text'] or '').split('\n')
            cell_html = '<br>'.join(html.escape(line.strip()) for line in cell_lines if line.strip())
            html_out.append(f"<td class='ev-t_td' {' '.join(attrs)}><p class='ev-t_tcell'>{cell_html}</p></td>")
        html_out.append("</tr>")
    html_out.append("</tbody></table>")
    return "\n".join(html_out)

def detect_alignment(paragraph, page_width=650):
    # Use all lines in the paragraph for alignment detection
    all_spans = []
    for line in paragraph:
        if isinstance(line, dict) and line.get('br'):
            line = line['line']
        all_spans.extend(line)
    if not all_spans:
        return 'left'
    x0 = min(span['x'] for span in all_spans)
    x1 = max(span['x'] + (span['bbox'][2] - span['bbox'][0]) for span in all_spans)
    text_width = x1 - x0
    left_margin = x0
    right_margin = page_width - x1
    # Heuristics
    if abs(left_margin - right_margin) < page_width * 0.08:
        return 'center'
    elif right_margin < page_width * 0.15:
        return 'right'
    else:
        return 'left'

def merge_heading_spans(line):
    # Merge consecutive digit spans into a single number string
    merged = []
    i = 0
    while i < len(line):
        if line[i]['text'].isdigit():
            num_str = line[i]['text']
            j = i + 1
            while j < len(line) and line[j]['text'].isdigit():
                num_str += line[j]['text']
                j += 1
            merged.append({'text': num_str})
            i = j
        else:
            merged.append(line[i])
            i += 1
    return ''.join(span['text'] for span in merged)

def render_paragraph(paragraph, page_width=650):
    cls = classify_paragraph(paragraph)
    align = detect_alignment(paragraph, page_width)
    align_style = ''
    if align == 'center':
        align_style = ' style="text-align:center;"'
    elif align == 'right':
        align_style = ' style="text-align:right;"'
    lines_html = []
    for idx, line in enumerate(paragraph):
        if isinstance(line, dict) and line.get('br'):
            lines_html.append('<br>')
            line = line['line']
        # Always sort by x for headings and normal paragraphs
        sorted_line = sorted(line, key=lambda span: span['x'])
        line_text = html.escape(''.join(span['text'] for span in sorted_line))
        lines_html.append(line_text)
    text = ' '.join(lines_html)
    if cls == 'h1':
        return f"<p class='ev-t_h1'{align_style}>{text}</p>"
    elif cls == 'note':
        return f"<p class='ev-t_par'{align_style}>{text}</p>"
    elif cls == 'spacer':
        return f"<p class='ev-t_spacer'></p>"
    else:
        return f"<p class='ev-t_par'{align_style}>{text}</p>"

def is_mostly_cjk(text):
    cjk_count = len(re.findall(r'[\u4e00-\u9fff]', text))
    return cjk_count > 0 and cjk_count / max(len(text), 1) > 0.5

def best_cjk_order(line):
    # Try both original and x-sorted order, pick the one with the longest run of CJK
    orig = ''.join(span['text'] for span in line)
    sorted_line = sorted(line, key=lambda span: span['x'])
    xsort = ''.join(span['text'] for span in sorted_line)
    def max_cjk_run(s):
        runs = re.findall(r'[\u4e00-\u9fff]+', s)
        return max((len(run) for run in runs), default=0)
    return orig if max_cjk_run(orig) >= max_cjk_run(xsort) else xsort

def extract_visual_page_number(page):
    height = page.rect.height
    blocks = page.get_text("blocks")
    bottom_blocks = [b for b in blocks if b[1] > height * 0.85]
    for b in bottom_blocks:
        text = b[4].strip()
        m = re.match(r'^\d{1,3}$', text)
        if m:
            return text
    return None

def process_page(page, page_num):
    tables = extract_tables(page)
    table_bboxes = [t['bbox'] for t in tables]
    blocks = extract_blocks_lines_spans(page)
    filtered_blocks = []
    page_number_elements = []
    heading_elements = []

    for index, block in enumerate(blocks):
        block_bbox = [
            min(span['x'] for line in block for span in line),
            min(span['y'] for line in block for span in line),
            max(span['x'] + (span['bbox'][2] - span['bbox'][0]) for line in block for span in line),
            max(span['y'] + (span['bbox'][3] - span['bbox'][1]) for line in block for span in line)
        ]
        first_line = block[0]
        sorted_spans = sorted(first_line, key=lambda span: span['x'])
        text = ''.join(span['text'] for span in sorted_spans).strip()
        is_digits = text.isdigit()
        is_top = block_bbox[1] < 100
        is_large = first_line[0]['size'] > 16 if first_line else False
        # Heuristic: CJK heading
        orig = ''.join(span['text'] for span in first_line)
        cjk_heading = is_top and is_mostly_cjk(orig) and len(orig) > 6
        if is_digits and is_top and is_large:
            page_number_elements.append({'type': 'pagenum', 'y': block_bbox[1], 'x': block_bbox[0], 'text': text})
        elif cjk_heading:
            best_text = best_cjk_order(first_line)
            heading_elements.append({'type': 'heading', 'y': block_bbox[1], 'x': block_bbox[0], 'text': best_text})
        else:
            if not any(is_overlap(block_bbox, tb) for tb in table_bboxes):
                filtered_blocks.append(block)
    elements = []
    for t in tables:
        elements.append({'type': 'table', 'y': t['y'], 'x': t['x'], 'table': t})
    for elem in page_number_elements:
        elements.append(elem)
    for elem in heading_elements:
        elements.append(elem)
    for block in filtered_blocks:
        lines = block
        paragraphs = group_lines_to_paragraphs(lines)
        for p in paragraphs:
            y = p[0][0]['y'] if isinstance(p[0], list) else p[0]['line'][0]['y']
            x = p[0][0]['x'] if isinstance(p[0], list) else p[0]['line'][0]['x']
            elements.append({'type': 'text', 'y': y, 'x': x, 'paragraph': p})
    elements.sort(key=lambda e: (e['y'], e['x']))
    html_out = [f'<pagemark number="{page_num+1}" pagepdf="{INPUT_PDF}"/>']
    html_out.append("<div class='ev-t_page'>")
    for el in elements:
        if el['type'] == 'table':
            html_out.append(render_table(el['table']))
        elif el['type'] == 'pagenum':
            html_out.append(f"<p class='ev-t_pnum' style='text-align:center;'>{html.escape(el['text'])}</p>")
        elif el['type'] == 'heading':
            html_out.append(f"<p class='ev-t_h1' style='text-align:center;'>{html.escape(el['text'])}</p>")
        else:
            html_out.append(render_paragraph(el['paragraph']))
    html_out.append("</div>")
    visual_num = extract_visual_page_number(page)
    if visual_num:
        html_out.append(f"<div class='ev-t_footer' style='text-align:center;color:#888;font-size:12px;margin-top:20px;'>Страница {visual_num}</div>")
    return "\n".join(html_out)

def main():
    doc = fitz.open(INPUT_PDF)
    html_out = ["<!DOCTYPE html>", "<html lang='zh'>", "<head>", "<meta charset='UTF-8' />", "<title>PDF to HTML</title>", CSS, "</head>", "<body>"]
    for i, page in enumerate(doc):
        html_out.append(process_page(page, i))
    html_out.append("</body></html>")
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(html_out))
    print(f"Wrote {OUTPUT_HTML}")

if __name__ == "__main__":
    main() 