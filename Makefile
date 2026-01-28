.PHONY: dev install app dmg clean

dev:
	python run.py

install:
	pip install -r requirements.txt

app:
	python setup_app.py py2app

dmg:
	bash scripts/build_dmg.sh

clean:
	rm -rf build dist *.dmg *.egg-info .eggs
