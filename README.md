## Description
`make-argocd-fly` is a tool to generate Kubernetes manifests that can be deployed with ArgoCD in a multi cluster environments. It makes it easier to develop and maintain ArgoCD applications by providing a way to render Jinja2 and Kustomize files, run yaml and kube linters and automatically generate ArgoCD `Application` resources.

The idea is that you write your resources in YAML, Jinja2 or Kustomize (including helmCharts), write a configuration file that describes where to deploy them and then run `make-argocd-fly` to generate the final manifests. This way it is transparent what is being deployed and where, it is easier to maintain and develop the resources and it is easier to debug issues.

## Features
- Jinja2 and Kustomize rendering
- ArgoCD `Application` resources are generated automatically
- `App-of-apps` pattern is natively supported
- Use `include` or `include_raw` in Jinja2 templates to render content of external files
- Global, per environment and per application Jinja2 variables
- Variables referencing other variables are supported
- Source resources can reside in subdirectories

## Usage
```
python3 -m venv .venv
. .venv/bin/activate
pip install make-argocd-fly

make-argocd-fly -h
usage: main.py [-h] [--root-dir ROOT_DIR] [--config-file CONFIG_FILE] [--source-dir SOURCE_DIR] [--output-dir OUTPUT_DIR] [--tmp-dir TMP_DIR] [--render-apps RENDER_APPS]
               [--render-envs RENDER_ENVS] [--skip-generate] [--preserve-tmp-dir] [--clean] [--print-vars] [--var-identifier VAR_IDENTIFIER] [--yaml-linter] [--kube-linter]
               [--loglevel LOGLEVEL]

Render ArgoCD Applications.

options:
  -h, --help            show this help message and exit
  --root-dir ROOT_DIR   Root directory (default: current directory)
  --config-file CONFIG_FILE
                        Configuration file (default: config.yaml)
  --source-dir SOURCE_DIR
                        Source files directory (default: source)
  --output-dir OUTPUT_DIR
                        Output files directory (default: output)
  --tmp-dir TMP_DIR     Temporary files directory (default: .tmp)
  --render-apps RENDER_APPS
                        Comma separate list of applications to render
  --render-envs RENDER_ENVS
                        Comma separate list of environments to render
  --skip-generate       Skip resource generation
  --preserve-tmp-dir    Preserve temporary directory
  --clean               Clean all applications in output directory
  --print-vars          Print variables for each application
  --var-identifier VAR_IDENTIFIER
                        Variable prefix in config.yml file (default: $)
  --yaml-linter         Run yamllint against output directory (https://github.com/adrienverge/yamllint)
  --kube-linter         Run kube-linter against output directory (https://github.com/stackrox/kube-linter)
  --loglevel LOGLEVEL   DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Configuration
### config.yml
Example configuration file:
```tests/manual/config.yml```

### Source directory structure
Example directory structure:
```tests/manual/source```

When kustomization overlays are used, kustomization base directory shall be named `base`, overlay directories shall be named after the corresponding environments names.

### app parameters
- `app_deployer` - name of the application that will deploy this application
- `project` - ArgoCD project name
- `destination_namespace` - namespace where the application will be deployed
- `app_deployer_env` - (OPTIONAL) environment of the application that will deploy this application
- `vars` - (OPTIONAL) application specific jinja2 variables

### Jinja2 extensions
To render a template in the current jinja2 template, use the following block:

```
{%- filter indent(width=4) %}
{% include 'app_4/files/file.json.j2' %}
{% endfilter %}
```

To include file content in the current jinja2 template, use the following block:

```
{%- filter indent(width=4) %}
{% include_raw 'app_4/files/file.json' %}
{% endfilter %}
```

To perform a DNS lookup, use the following filter:

```
{{ 'example.com' | dig }}
```

Ansible filters are supported as well: https://pypi.org/project/jinja2-ansible-filters/

### kustomization.yml
Files referenced in the `resources` section shall be named after Kubernetes resource type + `_` + resource name. Example:

```
resources:
  - deployment_nginx.yml
  - serviceaccount_nginx-prod.yml
```
### Initial app-of-apps application
`bootstrap` application shall be deployed externally

### Variable names
The folloving variable names are reserved (at the root level) and shall not be used in the configuration file:
- __application
- env_name
- app_name

### Referencing variables in config.yml
Variables can be referenced in the configuration file (including *app parameters*) using the following syntax:
```${var_name}``` and  ```${var_name[subvar_name][...]}```.

Variables can also be used as substring values:
```prefix-${var_name}-suffix```.


### Expected variables
The folloving variables are expected to be provided:
- argocd.api_server
- argocd.namespace
- argocd.repo_url
- argocd.target_revision

### Optional variables
- argocd.sync_policy
- argocd.finalizers
- argocd.ignoreDifferences

## Caveats
- `kustomize` and `helm` are expected to be installed locally.
- `kube-linter` is expected to be installed locally (https://github.com/stackrox/kube-linter).
- `libyaml` is expected to be installed locally for speeding up YAMLs generation.
- Comments are not rendered in the final output manifests.

## For developers
### Build instructions
https://setuptools.pypa.io/en/latest/userguide/quickstart.html
https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html
https://setuptools.pypa.io/en/latest/userguide/datafiles.html
https://packaging.python.org/en/latest/tutorials/packaging-projects/
https://packaging.python.org/en/latest/guides/single-sourcing-package-version/#single-sourcing-the-version
https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/

### Preparation
```
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r dev_requirements.txt
```

### Execution
```
python main.py --root-dir <path>
```

### Packaging
```
<tag HEAD>
python -m build
python -m twine upload  dist/*
```

### Profiling
```
python -m cProfile -o profile.pstats main.py --root-dir <path>
gprof2dot log.pstats [-z <function>] | dot -Tsvg -o profile.svg
```
