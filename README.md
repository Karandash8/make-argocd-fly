# make-argocd-fly
  [![cov](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Karandash8/26eb92c97bbfac22b938afebac85e7cd/raw/covbadge.json)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Karandash8/26eb92c97bbfac22b938afebac85e7cd/raw/covbadge.json)

## Description
`make-argocd-fly` is a tool designed to simplify the generation of Kubernetes manifests for deployment in complex, multi-cluster, and multi-application environments. By leveraging YAML, Jinja2 templates, Kustomize files, and Helm charts via Kustomize. This tool streamlines the process of creating and maintaining Kubernetes resources. While the generated manifests can be deployed using any external deployment tool, such as kubectl, `make-argocd-fly` offers native integration with ArgoCD, enhancing the deployment experience.

With `make-argocd-fly`, you can develop your resources in various formats, write a configuration file to specify deployment details, generate the final manifests effortlessly, and then push them to a repository for ArgoCD to deploy them in a Kubernetes cluster. This approach ensures transparency in what is being deployed and where, simplifies maintenance and development, and aids in debugging issues.

## Features
- **Jinja2 and Kustomize Rendering:** Seamlessly render Kubernetes manifests using Jinja2 templates and Kustomize, including Helm charts.
- **ArgoCD App-of-Apps Pattern Support:** Native support of the app-of-apps pattern for organizing complex applications with automatic generation of ArgoCD `Application` resources for streamlined deployment.
- **External File Inclusion:** Use `include` or `include_raw` in Jinja2 templates to render content from external files.
- **Flexible Variable Management:** Support for global, per-environment, and per-application Jinja2 variables, with the ability to reference other variables.
- **Subdirectory Resource Management:** Source resources can reside in subdirectories for better organization and management.

## How to start
### Prerequisites
- `libyaml` is expected to be installed locally for speeding up YAMLs generation.
- `kustomize` (IF USED) is expected to be installed locally.
- `helm` (IF USED) is expected to be installed locally.
- `yamllint` (IF USED) is expected to be installed locally (https://github.com/adrienverge/yamllint).
- `kube-linter` (IF USED) is expected to be installed locally (https://github.com/stackrox/kube-linter).

### Configuration file (`config.yml`)
The following structure is expected:
```
envs:
  <environment_name_1>:
    apps:
      <application_name_1>: {}
      #<application_name_N>: {}  ## additional applications for the environment
  #<environment_name_N>:  ## additional environments

vars:
  <variable_name_1>: <variable_value_1>
  #<variable_name_N>: <variable_value_N>  ## additional variables
```

Application names shall correspond to the relative paths from the source directory to the application directory, e.g., ```grafana```, ```path/to/grafana``` .

Example configuration file:
```tests/examples/app_types/config.yml```

### Source directory structure
Example directory structure:
```tests/examples/app_types/source```

## Execution
```
python3 -m venv .venv
. .venv/bin/activate
pip install make-argocd-fly

make-argocd-fly -h
usage: main.py [-h] [--root-dir ROOT_DIR] [--config-file CONFIG_FILE] [--source-dir SOURCE_DIR] [--output-dir OUTPUT_DIR] [--tmp-dir TMP_DIR] [--render-apps RENDER_APPS]
               [--render-envs RENDER_ENVS] [--skip-generate] [--preserve-tmp-dir] [--clean] [--print-vars] [--var-identifier VAR_IDENTIFIER] [--skip-latest-version-check]
               [--yaml-linter] [--kube-linter] [--loglevel LOGLEVEL]

Render ArgoCD Applications.

options:
  -h, --help            show this help message and exit
  --root-dir ROOT_DIR   Root directory (default: current directory)
  --config-file CONFIG_FILE
                        Configuration file (default: config.yml)
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
  --remove-output-dir   Remove output directory
  --print-vars          Print variables for each application
  --var-identifier VAR_IDENTIFIER
                        Variable prefix in config.yml file (default: $)
  --skip-latest-version-check
                        Skip latest version check
  --yaml-linter         Run yamllint against output directory (https://github.com/adrienverge/yamllint)
  --kube-linter         Run kube-linter against output directory (https://github.com/stackrox/kube-linter)
  --loglevel LOGLEVEL   DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Advanced usage
### ArgoCD integration
ArgoCD app-of-apps pattern (https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/) is one of the ways to deploy applications in a Kubernetes cluster. `make-argocd-fly` supports this pattern by generating ArgoCD `Application` resources for each application in the configuration file. The generated resources can be deployed in the cluster using ArgoCD, which will automatically deploy the applications specified in the `Application` resources. The app-of-apps pattern can be nested, which allows for organizing applications in a hierarchical structure, where only the top-level application needs to be deployed externally.

To make use of ArgoCD app-of-apps pattern in `make-argocd-fly`, specify the following variables and application parameters:
```
envs:
  <environment_name>:
    apps:
      <bootstrap_application>: {}  ## application that shall be deployed externally that will deploy other applications
      <application_name>:
        app_deployer: <bootstrap_application>  ## application that will deploy this application
        app_deployer_env: <environment_name>  ## (OPTIONAL) for multi-environments with single ArgoCD deployment
vars:
  argocd:
    namespace: <argocd_namespace>  ## (OPTIONAL) namespace for ArgoCD `Application` resource, default: argocd
    sync_wave: <application_sync_wave>  ## (OPTIONAL) `sync_wave` annotation for ArgoCD `Application` resource
    finalizers: <argocd_finalizers>  ## (OPTIONAL) default: []
    project: <project_name>  ## (OPTIONAL) ArgoCD project name, default: default
    source:
      repo_url: <argocd_repo_url>  ## URL to the Git repository
      target_revision: <argocd_target_revision>  ## target revision for the Git repository
      directory:
        recurse: <true|false>  ## (OPTIONAL) not set by default
    destination:
      server: <kube_apiserver>  ## kube-apiserver address
      namespace: <namespace>  ## (OPTIONAL) default namespace where the application resources will be deployed, default: argocd
    sync_policy: <argocd_sync_policy>  ## (OPTIONAL) default: {}
    ignoreDifferences: <argocd_ignoreDifferences>  ## (OPTIONAL) default: []
```

### Magic variables
The folloving variable names are reserved for internal purposes and shall not be used in the configuration file:
- __application

The folloving variable are automatically populated and can be referenced without explicit definition:
- env_name
- app_name

### Variables scopes
Variables can be defined at the root level, per-environment, and per-application. Variables defined at the root level are global and can be referenced in any application. Variables defined per-environment are specific to the environment and can be referenced in any application within that environment. Variables defined per-application are specific to the application and can be referenced only in that application.

When a variable is defined in multiple scopes the following priority rules apply: global variable < environment variable < application variable

```
envs:
  <environment_name>:
    apps:
      <application_name>:
        vars:
          <variable_name>: <variable_value>
    vars:
      <variable_name>: <variable_value>
vars:
  <variable_name>: <variable_value>
```

In order to unset a key of a dictionary variable that is set at a higher level, use the `null` value:
```
envs:
  <environment_name>:
    vars:
      <variable_name>:
        <key>: null
vars:
  <variable_name>:
    <key>: <value>
```

### Variables in `config.yml`
Variables can be referenced in the configuration file using the following syntax:
```${var_name}``` and  ```${var_name[dict_key][...]}```.

Variables can also be used as substring values:
```prefix-${var_name}-suffix```.

The following variable resolution rules apply:
- Variable referenced in global scope is resolved using global variables.
- Variable referenced in per-environment scope is resolved using global and per-environment variables.
- Variable referenced in per-application scope is resolved using global, per-environment, and per-application variables.

### Jinja2 templates
All standard Jinja2 features are supported.

For example:
- To render a template in the current jinja2 template, use the following block:

  ```
  {%- filter indent(width=4) %}
  {% include 'files/file.json.j2' %}
  {% endfilter %}
  ```

  Example:
  ```tests/manual/source/app_5```

In addition, the following features are available:
- To include file content in the current Jinja2 template, use the following block:

  ```
  {%- filter indent(width=4) %}
  {% include_raw 'files/file.json' %}
  {% endfilter %}
  ```

  Example:
  ```tests/manual/source/app_4```

- To render files from a subdirectory as YAML key-value pairs (where file name would be the key and file content would be the value),
use the following block:

  ```
  {%- filter indent(width=2) %}
  {% include_all_as_yaml_kv 'files/' %}
  {% endfilter %}
  ```

  Example:
  ```tests/manual/source/app_15```

- To render files from a subdirectory as YAML list (where file content would be the value),
use the following block:

  ```
  {%- filter indent(width=4) %}
  {% include_all_as_yaml_list 'files/' %}
  {% endfilter %}
  ```

  Example:
  ```tests/manual/source/app_16```

- To perform a DNS lookup, use the following filter:

  ```
  {{ 'example.com' | dig }}
  ```

- Ansible filters are supported as well: https://pypi.org/project/jinja2-ansible-filters/

### Kustomize
Local files referenced in the `resources` section shall be named after Kubernetes resource type + `_` + resource name:

```
resources:
  - deployment_nginx.yml
  - serviceaccount_nginx-prod.yml
```

Example:
```tests/manual/source/app_1```

When kustomization overlays are used, kustomization base directory shall be named `base`, overlay directories shall be named after the corresponding environments names.
Example:
```tests/manual/source/app_2```

When Helm `values.yml` file is used, the file shall be named `values.yml` and reside in the application directory.
On top of that the file shall be explicitly set for rendering in the configuration file:
```
envs:
  <environment_name>:
    apps:
      <application_name>:
        non_k8s_files_to_render: [<filename>]  ## (OPTIONAL) list of files to render that are not Kubernetes resources (e.g., values.yml)
```
### Exclude certain directories
In case you have certain files in source application directory that you would like to not be rendered, you can use `exclude_rendering` application parameter in your configuration to exclude it from rendering
```
envs:
  <environment_name>:
    apps:
      <application_name>:
        exclude_rendering: [<directory>]  ## (OPTIONAL) list of directories to exclude from rendering (e.g., unit test files for opa)
```

## Caveats
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
pip install -r requirements-dev.txt
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
