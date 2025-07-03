

PROJECT_NAME=pdf_to_html
PROJECT_PATH=/opt/micros/$(PROJECT_NAME)
ACTIVATE=$(PROJECT_PATH)/venv/bin/activate
#ACTIVATE=/opt/kaba/venv/bin/activate


list:		# показать все комманды
	@grep '^[^#[:space:]].*:' Makefile
	echo "source $(ACTIVATE)"
prepare: # подготовить окружение, установить данные
	#mkdir -p /opt/pp
	mkdir -p $(PROJECT_PATH)
	python3.10 -m venv $(PROJECT_PATH)/venv
	#python3.8 -m venv $(PROJECT_PATH)/venv
	pip install --upgrade pip
	#make install
install:
	#$(BIN)pip install --upgrade pip;
	#$(BIN)pip install -r requirements.txt
	. $(ACTIVATE); pip install -r requirements.txt
i:
	make install
pdf:
	python pdf_to_html/pdf_to_html.py
im:
	python pdf_to_html/pdf_to_image_to_html.py example.pdf 0 output.png output.html
