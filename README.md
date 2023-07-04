# make_argocd_fly
A project to generate ArgoCD application resources

# Install
```
python -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

# Run
```
python make_argocd_fly/main.py --root-dir <path>
```

# Build instructions
https://setuptools.pypa.io/en/latest/userguide/quickstart.html
https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
https://setuptools.pypa.io/en/latest/userguide/datafiles.html
https://packaging.python.org/en/latest/tutorials/packaging-projects/

```
<change version in pyproject.toml>
python -m build
python -m twine upload  dist/*
```
