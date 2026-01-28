.PHONY: dev install dmg clean

dev:
	python run.py

install:
	pip install -r requirements.txt

dmg:
	bash scripts/build_dmg.sh

clean:
	rm -rf build dist *.dmg *.egg-info .eggs
