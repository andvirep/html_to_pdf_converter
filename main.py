
import fitz  # PyMuPDF
import camelot
import os
import re
from collections import defaultdict, Counter

PDF_PATH = 'example.pdf'
OUTPUT_HTML = 'output.html'

# 1. Extract tables with Camelot (both flavors)
def extract_tables(pdf_path):
    tables = []
    for flavor in ['lattice', 'stream']:
        try:
            t = camelot.read_pdf(pdf_path, pages='all', flavor=flavor, strip_text='\n')
            tables.extend(t)
        except Exception as e:
            print(f'Camelot {flavor} error:', e)
    # Deduplicate tables by bbox and page
    seen = set()
    unique_tables = []
    for table in tables:
        key = (table.page, tuple(table._bbox))
        if key not in seen:
            seen.add(key)
            unique_tables.append(table)
    return unique_tables

print('Extracting tables with Camelot...')
tables = extract_tables(PDF_PATH)

# Store table regions per page for later exclusion
# Also store table HTML and Y position for interleaving
per_page_tables = defaultdict(list)
for table in tables:
    page = table.page - 1  # Camelot pages are 1-indexed, PyMuPDF is 0-indexed
    bbox = table._bbox  # (x1, y1, x2, y2)
    y_top = bbox[1]
    per_page_tables[page].append({'bbox': bbox, 'y': y_top, 'html': table.to_html()})

def is_in_table(x0, y0, x1, y1, table_bboxes):
    for bx0, by0, bx1, by1 in table_bboxes:
        if (x0 >= bx0-2 and y0 >= by0-2 and x1 <= bx1+2 and y1 <= by1+2):
            return True
    return False

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def detect_headers_footers(all_lines, page_height, num_pages):
    # Find lines that appear at the top/bottom of many pages (likely header/footer)
    top_lines = []
    bottom_lines = []
    for lines in all_lines:
        if not lines:
            continue
        # Top 5% and bottom 5% of page
        tops = [l for l in lines if l['y0'] < 0.05 * page_height]
        bots = [l for l in lines if l['y1'] > 0.95 * page_height]
        top_lines.extend([l['text'] for l in tops])
        bottom_lines.extend([l['text'] for l in bots])
    top_counts = Counter(top_lines)
    bot_counts = Counter(bottom_lines)
    # If a line appears on >60% of pages, treat as header/footer
    header = set([t for t, c in top_counts.items() if c > 0.6 * num_pages])
    footer = set([t for t, c in bot_counts.items() if c > 0.6 * num_pages])
    return header, footer

def extract_lines(doc, per_page_tables):
    all_page_lines = []
    for page_num, page in enumerate(doc):
        lines = []
        table_bboxes = [t['bbox'] for t in per_page_tables.get(page_num, [])]
        for l in page.get_text('lines'):
            x0, y0, x1, y1, text, *_ = l
            text = clean_text(text)
            if not text:
                continue
            if is_in_table(x0, y0, x1, y1, table_bboxes):
                continue
            lines.append({'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'text': text})
        all_page_lines.append(lines)
    return all_page_lines

def group_paragraphs(lines, y_gap=10):
    # Group lines into paragraphs by vertical gap and indentation
    if not lines:
        return []
    lines = sorted(lines, key=lambda l: (l['y0'], l['x0']))
    paragraphs = []
    para = []
    last_y = None
    for l in lines:
        if last_y is not None and abs(l['y0'] - last_y) > y_gap:
            if para:
                paragraphs.append(para)
                para = []
        para.append(l)
        last_y = l['y1']
    if para:
        paragraphs.append(para)
    return paragraphs

def html_escape(text):
    return (
        text.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
    )

print('Extracting non-table text with PyMuPDF...')
doc = fitz.open(PDF_PATH)
all_page_lines = extract_lines(doc, per_page_tables)
header, footer = detect_headers_footers(all_page_lines, doc[0].rect.height, len(doc))


# 3. Merge tables and text into HTML, preserving order by Y
print('Writing output HTML...')
with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
    f.write('<!DOCTYPE html>\n<html lang="zh">\n<head>\n<meta charset="utf-8">\n<title>PDF to HTML</title>\n<style>table, th, td { border: 1px solid #888; border-collapse: collapse; } th, td { padding: 4px; } body { font-family: sans-serif; } p { margin: 0.5em 0; }</style>\n</head>\n<body>\n')
    for page_num, page in enumerate(doc):
        f.write(f'<div class="page" id="page-{page_num+1}">\n')
        # Prepare all content blocks (paragraphs and tables) with their Y position
        content_blocks = []
        # Paragraphs
        lines = [l for l in all_page_lines[page_num] if l['text'] not in header and l['text'] not in footer]
        for para in group_paragraphs(lines):
            y = para[0]['y0']
            para_text = ''.join([html_escape(l['text']) for l in para])
            content_blocks.append({'y': y, 'type': 'p', 'html': f'<p>{para_text}</p>'})
        # Tables
        for t in per_page_tables.get(page_num, []):
            table_html = re.sub(r'<(/?)(html|body)[^>]*>', '', t['html'])
            content_blocks.append({'y': t['y'], 'type': 'table', 'html': table_html})
        # Sort by Y position
        content_blocks.sort(key=lambda b: b['y'])
        for block in content_blocks:
            f.write(block['html'] + '\n')
        f.write('</div>\n')
    f.write('</body>\n</html>\n')


print(f'Done! Output written to {OUTPUT_HTML}')
