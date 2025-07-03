import paddle
print(paddle.__version__)
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='ch')