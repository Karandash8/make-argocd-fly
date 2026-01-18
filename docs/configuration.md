# Configuration

Configuration files (`.yml`) should be placed in the `config/` directory and follow YAML syntax.

## 🗂️ Structure

```yaml
envs:  ## key for environment configuration
  <environment_name_1>:  ## environment name
    apps:  ## key for applications in the environment
      <application_name_1>:  ## application name
        params: ## key for application parameters
          <param_name_1>: <param_value_1>
          <param_name_N>: <param_value_N>  ## additional parameters
        vars:  ## key for application variables
          <variable_name_1>: <variable_value_1>
          <variable_name_N>: <variable_value_N>  ## additional variables
      <application_name_N>: {}  ## additional applications
    params:  ## key for environment parameters
      <param_name_1>: <param_value_1>
      <param_name_N>: <param_value_N>  ## additional parameters
    vars:  ## key for environment variables
      <variable_name_1>: <variable_value_1>
      <variable_name_N>: <variable_value_N>  ## additional variables
  <environment_name_N>: {}  ## additional environments
params:  ## key for global parameters
  <param_name_1>: <param_value_1>
  <param_name_N>: <param_value_N>  ## additional parameters
vars:  ## key for global variables
  <variable_name_1>: <variable_value_1>
  <variable_name_N>: <variable_value_N>  ## additional variables
```

Application names must correspond to the relative paths from the source, e.g., ```grafana```, ```path/to/grafana``` .

## Application Type

Application type defines what source files are taken into account and how output files are generated for each application. Application type is specified using the `app_type` parameter in the configuration:

```yaml
envs:
  <environment_name_1>:
    apps:
      <application_name_1>:
        params:
          app_type: <application_type>
```

Available application types:
- `k8s` (default): Renders only Kubernetes related files and outputs YAML files with `kind` and `name` fields.
- `generic`: Renders all files in the application directory as-is, using Jinja2 templating.

## ⚖️ Variable Precedence
The scope of parameters and variables determines their visibility and accessibility within the configuration.
- **Global**: Accessible across all environments and applications.
- **Environment**: Accessible within a specific environment and its applications.
- **Application**: Accessible only within a specific application.

```yaml
envs:
  <env_name>:
    apps:
      <app_name>:
        params: {...}
        vars:   {...}
    vars: {...}
vars: {...}
```
_Precedence_: `global < environment < application`.

If a variable is defined at multiple levels, the most specific level takes precedence.

In order to unset a variable or a key of a dictionary variable in a more specific scope, you can set it to `null`.

## 🛠️ Parameters
Parameters are used to configure various aspects of the applications.

Available parameters include:

- `parent_app`: The parent application for the current application.
- `parent_app_env`: The environment of the parent application.
- `app_type`: The type of the application (`k8s` or `generic`).
- `non_k8s_files_to_render`: A list of non-Kubernetes files to render.
- `exclude_rendering`: A list of files to exclude from rendering.

## 🧩 Variables
Variables are used to define values that can be used in Jinja2 templates across all applications in `source/` directory.

### ✨ Reserved & Magic Variables

- Reserved: `__application`
  - **Description**: This variable is reserved for internal use and should not be overridden.
  - **Type**: Map

- Auto-defined: `env_name`, `app_name`
  - **Description**: These variables are automatically defined based on the environment and application names.
  - **Type**: String

- Overridable: `argocd_application_cr_template`
  - **Description**: This variable can be overridden to customize the ArgoCD application CR template.
  - **Type**: String
  - **Default Value**: [ARGOCD_APPLICATION_CR_TEMPLATE in `make_argocd_fly/consts.py`](https://github.com/Karandash8/make-argocd-fly/blob/main/make_argocd_fly/consts.py#L18)
  - **Override Example**: [05_argocd_managed_helm_app in `examples/app_types/config/config.yml`](https://github.com/Karandash8/make-argocd-fly/blob/main/examples/app_types/config/config.yml#L13)

### 🔗 Variables Referencing Other Variables
Variables can reference other variables in the config files, using the following syntax:
- ```${var_name}```
- ```${var_name[dict_key][...]}```

Variable references can also be embedded within strings:
- ```prefix-${var_name}-suffix```
