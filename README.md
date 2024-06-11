## Description
`make-argocd-fly` is a tool to generate Kubernetes manifests that can be deployed with ArgoCD in a multi cluster environments. It makes it easier to develop and maintain ArgoCD applications by providing a way to render Jinja2 and Kustomize files, run yaml and kube linters and automatically generate ArgoCD `Application` resources.

The idea is that you write your resources in YAML, Jinja2 or Kustomize (including helmCharts), write a configuration file that describes where to deploy them and then run `make-argocd-fly` to generate the final manifests. This way it is transparent what is being deployed and where, it is easier to maintain and develop the resources and it is easier to debug them.

## Features
- Jinja2 and Kustomize rendering
- ArgoCD `Application` resources are generated automatically
- `App-of-apps` pattern is natively supported
- Use `include` or `include_raw` in Jinja2 templates to render content of external files
- Global, per environment and per application Jinja2 variables
- Source resources can reside in subdirectories

## Usage
```
python3 -m venv .venv
. .venv/bin/activate
pip install make-argocd-fly

make-argocd-fly -h
usage: main.py [-h] [--root-dir ROOT_DIR] [--config-file CONFIG_FILE] [--render-apps RENDER_APPS] [--render-envs RENDER_ENVS] [--skip-generate] [--preserve-tmp-dir] [--yaml-linter] [--kube-linter]
               [--loglevel LOGLEVEL]

Render ArgoCD Applications.

options:
  -h, --help            show this help message and exit
  --root-dir ROOT_DIR   Root directory
  --config-file CONFIG_FILE
                        Configuration file
  --render-apps RENDER_APPS
                        Comma separate list of applications to render
  --render-envs RENDER_ENVS
                        Comma separate list of environments to render
  --skip-generate       Skip resource generation
  --preserve-tmp-dir    Preserve temporary directory
  --yaml-linter         Run yamllint against output directory (https://github.com/adrienverge/yamllint)
  --kube-linter         Run kube-linter against output directory (https://github.com/stackrox/kube-linter)
  --loglevel LOGLEVEL   DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Configuration
### config.yml
Example:
```
source_dir: source
output_dir: output
tmp_dir: .tmp

envs:
  dev:
    apps:
      bootstrap: {}
      extra_app_deployer: {app_deployer: bootstrap, project: default, destination_namespace: namespace_1}
      app_1:
        app_deployer: bootstrap
        project: default
        destination_namespace: namespace_1
        vars:
          argocd:
            target_revision: custom_branch
      subdirectory/app_2: {app_deployer: extra_app_deployer, project: default, destination_namespace: namespace_2}
    vars:
      argocd:
        api_server: dev-api-server
      var_3: value_X
  prod:
    apps:
      app_1: {app_deployer: bootstrap, project: default, destination_namespace: namespace_1}
    vars:
      argocd:
        api_server: prod-api-server
vars:
  argocd:
    namespace: argocd
    repo_url: https://example.com/repo.git
    target_revision: HEAD
    sync_policy:
      automated:
        selfHeal: true
        prune: true
        allowEmpty: true
      # https://www.arthurkoziel.com/fixing-argocd-crd-too-long-error/
      syncOptions:
        - ServerSideApply=true
    finalizers:
      - resources-finalizer.argocd.argoproj.io
  var_1:
    var_2: value_2
  var_3: value_3
```

With this configuration file you can have kustomize overlays for `dev/prod` and use jinja2 variables like `{{ var_1.var_2 }} and {{ var_3 }}` in your source files.

### app parameters
- `app_deployer` - name of the application that will deploy this application
- `project` - ArgoCD project name
- `destination_namespace` - namespace where the application will be deployed
- `app_deployer_env` - (OPTIONAL) environment of the application that will deploy this application
- `vars` - (OPTIONAL) application specific jinja2 variables

## Jinja2 extensions
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

## Caveats
### Requirements
- `kustomize` and `helm` are expected to be installed locally.
- `kube-linter` is expected to be installed locally (https://github.com/stackrox/kube-linter).
- `libyaml` is expected to be installed locally for speeding up YAMLs generation.
- Comments are not rendered in the final output manifests.

### Currently supported directory structure
```
repo
  source
    (subdirectory/)app_1
      base
        yaml.yml(.j2)
        kustomization.yml(.j2)
      dev
        yaml.yml(.j2)
        kustomization.yml(.j2)
      prod
        yaml.yml(.j2)
        kustomization.yml(.j2)
    (subdirectory/)app_2
      yaml.yml(.j2)
      kustomization.yml(.j2)
    (subdirectory/)app_3
      yaml.yml(.j2)
    (subdirectory/)app_4
      yaml.yml(.j2)
      files
        file.json(.j2)
```

When kustomization overlays are used, kustomization base directory shall be named `base`, overlay directories shall be named after the corresponding environments names.

### kustomization.yml
Files referenced in the `resources` section shall be named after Kubernetes resource type + `_` + resource name. Example:

```
resources:
  - Deployment_nginx.yml
  - ServiceAccount_nginx-prod.yml
```
### Initial app-of-apps application
`bootstrap` application shall be deployed externally

### Variable names
The folloving variable names are reserved:
- __application

### Expected variables
The folloving variables are expected to be present:
- argocd.api_server
- argocd.namespace
- argocd.repo_url
- argocd.target_revision

### Optional variables
- argocd.sync_policy
- argocd.finalizers
- argocd.ignoreDifferences

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
