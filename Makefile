PYTHON ?= python

.PHONY: all setup update backfill run test clean

all: run

setup:
	$(PYTHON) -m pip install -r requirements.txt

update:
	$(PYTHON) -m src.update --months 2

backfill:
	$(PYTHON) -m src.update --backfill 48 --force

run:
	$(PYTHON) -m src.pipeline

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('data/processed', 'reports/figures')]"
