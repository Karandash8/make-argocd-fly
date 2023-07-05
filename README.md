## Description
A project to generate on the user side per environemnt Kubernetes manifests that can be deployed with ArgoCD.

## Motivation
Manifests that are written in kustomize/helm/jsonnet might easily become hard to read and debug. The development lifecycle becomes longer when after each change you need to commit, wait for ArgoCD to pick it up and deploy it. Only after that you see the actual end manifest in ArcoCD UI.

With this tool you can quickly render jinja2/kustomize files, run yaml linter and continuer development.

## Benefits
- Easier to grasp end manifests
- Shared variables between applications

## Configuration
### config.yml
Expected file structure
```
config:
  source_dir: source
  output_dir: output
  tmp_dir: .tmp

envs:
  - dev
  - stage
  - prod

vars:
  var_1:
    var_2: value_2
  var_3: value_3
```

## Caveats
### Currently supported directory structure
```
repo
  source
    app_1
      base
        yaml.yml
        kustomization.yml
      dev
        yaml.yml
        kustomization.yml
      stage
        yaml.yml
        kustomization.yml
      prod
        yaml.yml
        kustomization.yml
    app_2
      yaml.yml
      kustomization.yml
    app_3
      yaml.yml.j2
      kustomization.yml.j2
    app_4
      yaml.yml
```

With such configuration file you can have kustomize overlays for `dev/stage/prod` and jinja2 variables like `{{ var_1.var_2 }} and {{ var_3 }}` in your source files.

### kustomization.yml
Files referenced in the `resources` section shall be named after Kubernetes resource types with lower case letters as a single word. Example:

```
resources:
  - deployment.yml
  - serviceaccount.yml
```

## For developers
### Build instructions
https://setuptools.pypa.io/en/latest/userguide/quickstart.html
https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
https://setuptools.pypa.io/en/latest/userguide/datafiles.html
https://packaging.python.org/en/latest/tutorials/packaging-projects/

### Preparation
```
python -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r build_requirements.txt
```

### Execution
```
python main.py --root-dir <path>
```

### Packaging
```
<change version in pyproject.toml>
python -m build
python -m twine upload  dist/*
```
