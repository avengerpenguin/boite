.PHONY: clean test deploy-test deploy-live

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/py.test
PEP8 := $(VENV)/bin/pep8

PYSRC := $(shell find boite -iname '*.py' ; find test -iname '*.py')


###############
# Boilerplate #
###############

default: test

clean:
	rm -rf htmlcov .coverage .eggs results node_modules


##############
# Virtualenv #
##############

$(VENV)/deps.touch: $(PIP) requirements.txt
	$(PIP) install -r requirements.txt
	touch $(VENV)/deps.touch

$(VENV)/bin/%: $(PIP)
	$(PIP) install $*

$(VENV)/bin/py.test: $(PIP)
	$(PIP) install pytest pytest-cov pytest-xdist pytest-django

$(PYTHON) $(PIP):
	virtualenv -p python3 venv
	$(PIP) install virtualenv

$(VENV)/bin/pip-sync $(VENV)/bin/pip-compile: $(PIP)
	$(PIP) install --upgrade pip setuptools pip-tools

requirements.txt: requirements.in venv/bin/pip-compile
	venv/bin/pip-compile requirements.in


################
# Code Quality #
################

pep8.errors: $(PEP8) $(PYSRC)
	$(PEP8) --exclude="venv" . | tee /pep8.errors || true


################
# Unit Testing #
################

test: $(PYSRC) $(PYTHON) venv/bin/pip-sync requirements.txt $(PYTEST)
	source venv/bin/activate \
	    && venv/bin/pip-sync \
	    && export PYTHONPATH=$(PWD):$(PYTHONPATH) \
	    && $(PYTEST) test/*.py
