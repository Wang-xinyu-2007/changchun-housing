PYTHON ?= python3

.PHONY: all demo run test clean

all: demo run

demo:
	$(PYTHON) -m src.demo_data

run:
	$(PYTHON) -m src.pipeline

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	$(PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('data/processed', 'reports/figures')]"
