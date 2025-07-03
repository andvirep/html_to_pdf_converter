

pdf2htmlEX  poppler

у либы есть впечатляющий результат, правда пне table тегов, рисуется картинкой


исходная команда 
    
    docker run -ti --rm -v ~/pdf:/pdf bwits/pdf2htmlex-alpine pdf2htmlEX --zoom 1.3 example.pdf


нужно указать файл

    pwd
__результат pwd подставить вместо  ~/pdf__

команда генератор 

    docker run -ti --rm -v ~/Documents/pp/micros/pdf_to_html:/pdf bwits/pdf2htmlex-alpine pdf2htmlEX --zoom 1.3 pdf2html_test_tables-3.pdf

