# Configuration

Configuration files (`.yml` or `.yaml`) should be placed in the `config/` directory and follow YAML syntax.

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
- `k8s` (default): Renders Kubernetes YAML/Jinja files, Kustomize applications, Helmfile applications, and app-of-apps definitions. Kubernetes resources are written using filenames derived from `kind` and `metadata.name`; driver/source files such as `kustomization.yaml`, `values.yaml`, and `helmfile.yaml` preserve source-style names when staged.
- `generic`: Renders all files in the application directory as Jinja2 templates or passthrough files and preserves source-style output paths.

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
- `kustomize_common_dirs`: A list of additional directories to include when rendering a Kustomize application. See [Kustomize & Helm Applications](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/kustomize.md) for details.
- `application_name`: Controls the format of the ArgoCD `Application` CR `name` field for app-of-apps child applications. Accepted values: `short` (default, uses only the last segment of the application path and replaces underscores with dashes), `full` (uses the full application path and replaces slashes and underscores with dashes). Use `full` when multiple applications share the same directory basename to avoid name collisions.

## 🧩 Variables
Variables are used to define values that can be used in Jinja2 templates across all applications in `source/` directory.

### ✨ Reserved & Magic Variables

- Reserved: `__application`
  - **Description**: This variable is reserved for internal use and should not be overridden.
  - **Type**: Map

- Auto-defined: `env_name`, `app_name`
  - **Description**: These variables are automatically defined based on the environment and application names.
  - **Type**: String

- Auto-defined: `__application.application_name`, `__application.path`
  - **Description**: Values used by the default ArgoCD `Application` CR template. `application_name` is controlled by the `application_name` parameter. `path` points to the rendered output path for the child application.
  - **Type**: String

- Auto-defined with defaults: `argocd`
  - **Description**: Default ArgoCD settings used by `argocd_application_cr_template`. You normally set at least `argocd.source.repo_url` in config.
  - **Defaults**: `namespace: argocd`, `project: default`, `source.target_revision: HEAD`, `destination.server: https://kubernetes.default.svc`, `destination.namespace: argocd`

- Overridable: `argocd_application_cr_template`
  - **Description**: This variable can be overridden to customize the ArgoCD application CR template.
  - **Type**: String
  - **Default Value**: [ARGOCD_APPLICATION_CR_TEMPLATE in `make_argocd_fly/default.py`](https://github.com/Karandash8/make-argocd-fly/blob/main/make_argocd_fly/default.py#L19)
  - **Override Example**: [05_argocd_managed_helm_app in `examples/app_types/config/config.yml`](https://github.com/Karandash8/make-argocd-fly/blob/main/examples/app_types/config/config.yml#L13)

### 🔗 Variables Referencing Other Variables
Variables can reference other variables in the config files, using the following syntax:
- ```${var_name}```
- ```${var_name[dict_key][...]}```

Variable references can also be embedded within strings:
- ```prefix-${var_name}-suffix```

Unresolved variable references are allowed while config scopes are being merged, but rendering fails if a final template value still contains an unresolved `${...}` reference.

## Include and Exclude Patterns

Parameters such as `exclude_rendering` and `non_k8s_files_to_render` match application-relative paths by prefix or glob. Examples:

- `files` excludes `files/` and all children.
- `base/secret.yaml` matches that exact file.
- `**/secret*` matches secret-like files in any directory.
- `subdir/` includes or excludes the whole `subdir` tree.
