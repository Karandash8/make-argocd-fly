# make-argocd-fly
  [![cov](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Karandash8/26eb92c97bbfac22b938afebac85e7cd/raw/covbadge.json)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Karandash8/26eb92c97bbfac22b938afebac85e7cd/raw/covbadge.json)

## Description
`make-argocd-fly` is a tool designed to simplify the generation of Kubernetes manifests for deployment in complex, multi-cluster, and multi-application environments. It leverages YAML, Jinja2 templates, Kustomize files, and Helm charts through Kustomize, streamlining the process of creating and maintaining Kubernetes resources. Although the generated manifests can be deployed using any external tool, such as kubectl, `make-argocd-fly` provides native integration with ArgoCD, enhancing the overall deployment experience.

With `make-argocd-fly`, you can develop resources in various formats, specify deployment details in a configuration file, generate the final manifests effortlessly, and push them to a repository for ArgoCD to deploy to a Kubernetes cluster. This approach promotes transparency in what is being deployed and where, simplifies both maintenance and development, and assists in debugging issues.

## Features
- **ArgoCD App-of-Apps Pattern Support:** Native support for the app-of-apps pattern to organize complex applications, with automatic generation of ArgoCD `Application` resources for streamlined deployment.
- **Jinja2 and Kustomize Rendering:** Effortlessly render Kubernetes manifests using Jinja2 templates and Kustomize, including support for Helm charts.
- **Extended Jinja2 Functionality:** Includes additional Jinja2 extensions and filters, such as `include_raw`, to render content from external files.
- **Flexible Variable Management:** Manage global, per-environment, and per-application Jinja2 variables, with support for referencing other variables.
- **Subdirectory Resource Management:** Organize resources within subdirectories for improved structure and management.

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

Application names must correspond to the relative paths from the source directory to the application directory, e.g., ```grafana```, ```path/to/grafana``` .

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
```

```
make-argocd-fly -h
usage: make-argocd-fly [-h] [--root-dir ROOT_DIR] [--config-file CONFIG_FILE] [--source-dir SOURCE_DIR] [--output-dir OUTPUT_DIR] [--tmp-dir TMP_DIR] [--render-apps RENDER_APPS]
                       [--render-envs RENDER_ENVS] [--skip-generate] [--preserve-tmp-dir] [--remove-output-dir] [--print-vars] [--var-identifier VAR_IDENTIFIER]
                       [--skip-latest-version-check] [--yaml-linter] [--kube-linter] [--loglevel LOGLEVEL] [--version]

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
  --version             Show version
```

## Advanced usage
### ArgoCD integration
The [ArgoCD app-of-apps pattern](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/) is a method for deploying applications in a Kubernetes cluster. `make-argocd-fly` supports this pattern by generating ArgoCD `Application` resources for each application specified in the configuration file. These resources can be deployed in the cluster using ArgoCD, which will automatically handle the deployment of all applications referenced in the `Application` resources. The app-of-apps pattern supports nesting, enabling hierarchical organization of applications, where only the top-level application needs to be deployed manually.

To leverage the ArgoCD app-of-apps pattern in `make-argocd-fly`, specify the following variables and application parameters:

```
envs:
  <environment_name>:
    apps:
      <bootstrap_application>: {}  ## application that needs be deployed externally that will deploy other applications
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
The folloving variable names are reserved for internal purposes and must not be used in the configuration file:
- __application

The folloving variable are automatically populated and can be referenced without explicit definition:
- env_name
- app_name

### Variables scopes
Variables can be defined at three levels: root (global), per-environment, and per-application.

- Global variables (defined at the root level) are accessible by all applications.
- Environment-specific variables apply only to a specific environment but can be used by any application within that environment.
- Application-specific variables are restricted to the application in which they are defined.

If a variable is defined at multiple levels, the following priority rules apply: global < environment < application.


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
- ```${var_name}```
- ```${var_name[dict_key][...]}```

Variables can also be embedded within strings:
- ```prefix-${var_name}-suffix```

The following rules apply for variable resolution:
- Variables referenced in the global scope are resolved using global variables.
- Variables referenced in the per-environment scope are resolved using global and per-environment variables.
- Variables referenced in the per-application scope are resolved using global, per-environment, and per-application variables.

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
Local files referenced in the `resources` section should be named following this convention: the Kubernetes resource type followed by an underscore (`_`) and the resource name. For example:
```
resources:
  - deployment_nginx.yml
  - serviceaccount_nginx-prod.yml
```

Example:
```tests/manual/source/app_1```

When using Kustomize overlays, the base directory should be named `base`, and overlay directories should be named after the corresponding environment names.
Example:
```tests/manual/source/app_2```

If using a Helm `values.yml` file, it must be named `values.yml` and placed within the application directory. Additionally, the file must be explicitly specified for rendering in the configuration file:
```
envs:
  <environment_name>:
    apps:
      <application_name>:
        non_k8s_files_to_render: [<filename>]  ## (OPTIONAL) list of files to render that are not Kubernetes resources (e.g., values.yml)
```
### Exclude certain directories
If there are certain files in the source application directory that you do not want to render, you can use the `exclude_rendering` parameter in your configuration to exclude them from the rendering process:
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
pip install -r requirements.dev.txt
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

### Code coverage HTML report
```
python -m tox
```
