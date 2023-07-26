## Description
A tool to generate on the user side per environemnt Kubernetes manifests that can be deployed with ArgoCD.

ArcoCD resources of type `Application` are generated automatically based on the provided configuration.

## Motivation
Manifests that are written in kustomize/helm/jsonnet might easily become hard to read and debug. The development lifecycle becomes longer when after each change you need to commit, wait for ArgoCD to pick it up and deploy it. Only after that you see the actual end manifest in ArcoCD UI.

With this tool you can quickly render jinja2/kustomize files, run yaml linter and continuer development.

## Benefits
- Application resources are generated automatically
- Easier to grasp end manifests
- Shared variables between applications
- Use `include` or `include_raw` in templates to render content of an external file
- Use per environment `vars` block to override global variables

## Configuration
### config.yml
Expected file structure
```
source_dir: source
output_dir: output
tmp_dir: .tmp

envs:
  dev:
    apps:
      bootstrap: {}
      app_1: {app_deployer: bootstrap, project: default, destination_namespace: namespace_1}
      app_2: {app_deployer: bootstrap, project: default, destination_namespace: namespace_2}
    params:
      argocd_namespace: argocd
      repo_url: url
      target_revision: revision
      api_server: management-api-server
    vars:
      var_3: value_X
  prod:
    apps:
      app_1: {app_deployer: bootstrap, project: default, destination_namespace: namespace_1}
vars:
  var_1:
    var_2: value_2
  var_3: value_3
```

With such configuration file you can have kustomize overlays for `dev/prod` and use jinja2 variables like `{{ var_1.var_2 }} and {{ var_3 }}` in your source files.

## Caveats
### Requirements
`kubectl` is expected to be installed locally.

### Currently supported directory structure
```
repo
  source
    app_1
      base
        yaml.yml(.j2)
        kustomization.yml(.j2)
      dev
        yaml.yml(.j2)
        kustomization.yml(.j2)
      prod
        yaml.yml(.j2)
        kustomization.yml(.j2)
    app_2
      yaml.yml(.j2)
      kustomization.yml(.j2)
    app_3
      yaml.yml(.j2)
    app_4
      yaml.yml(.j2)
      files
        file.json(.j2)
```

When kustomization overlays are used, kustomization base directory shall be called `base`, overlay directories shall be named after the corresponding environments names.

To include an external template in a jinja2 template, use the following block:

```
{%- filter indent(width=4) %}
{% include 'app_4/files/file.json' %}
{% endfilter %}
```

To include an external file without rendering it in a jinja2 template, use the following block:

```
{%- filter indent(width=4) %}
{% include_raw 'app_4/files/file.json' %}
{% endfilter %}
```

### kustomization.yml
Files referenced in the `resources` section shall be named after Kubernetes resource type + `_` + resource name. Example:

```
resources:
  - Deployment_nginx.yml
  - ServiceAccount_nginx-prod.yml
```
### Initial app-of-apps application
`bootstrap` application shall be deployed externally

### Multiple ArgoCD deployments referencing the same repo
If there is an argocd deployment per environment then app_deployer applications shall have different names for different environments

### Variable names
The folloving variable names are resenved:
- _application_name
- _argocd_namespace
- _project
- _repo_url
- _target_revision
- _path
- _api_server
- _destination_namespace

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
pip install -r dev_requirements.txt
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
