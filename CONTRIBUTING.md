# Developer Guide

## Environment Setup

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements.dev.txt
```

## Run from Source

```
python main.py --root-dir <path>
```

## Packaging & Release

```
<tag HEAD>
python -m build
python -m twine upload  dist/*
```

### Build instructions
https://setuptools.pypa.io/en/latest/userguide/quickstart.html
https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
https://setuptools.pypa.io/en/latest/userguide/datafiles.html
https://packaging.python.org/en/latest/tutorials/packaging-projects/
https://packaging.python.org/en/latest/guides/single-sourcing-package-version/#single-sourcing-the-version
https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/

## Profiling

```
python -m cProfile -o profile.pstats main.py --root-dir <path>
gprof2dot profile.pstats [-z <function>] | dot -Tsvg -o profile.svg
```

## Coverage Report

```
python -m tox
```

---

## Development Workflow
```bash
python -m tox
pytest -q
```
