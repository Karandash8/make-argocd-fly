# Deprecations in `make-argocd-fly`
## `v0.2.14`
### Root level config file deprecation (removed in `v0.3.0`)
CLI parameter `--config-file` was removed. Use `--config-dir` with the default value of `config`. The new parameter allows specifying a directory with multiple YAML config files. When multiple config files are found in the directory they are merged together, while duplicate keys are reported back to the user as an error.

## `v0.2.15`
### App params deprecation (removed in `v0.4.0`)
`app_deployer`, `app_deployer_env`, `non_k8s_files_to_render` and `exclude_rendering` keys defined directly under the application were removed. Use the `params` keyword, which supports global, environment, and application scoping. Currently allowed params:
- `parent_app` - the name of the parent application
- `parent_app_env` - the name of the parent application environment
- `non_k8s_files_to_render` - a list of non-Kubernetes files to render
- `exclude_rendering` - a list of directories to exclude from rendering

### Custom Jinja2 extensions deprecation (removed in `v0.4.0`)
Older Jinja2 extension names were removed. Use the clearer names:
- `include_raw` -> `rawinclude`
- `include_all_as_yaml_names_list` -> `file_list`
- `include_all_as_yaml_kv` -> `include_map`
- `include_all_as_yaml_list` -> `include_list`

## `v0.4.4`
### Variables debugging CLI parameter deprecation
`--print-vars` CLI parameter is deprecated and still accepted. Use `--dump-context` instead to dump the entire relevant context including variables.

## `v0.4.6`
### Output directory removal CLI parameter deprecation
`--remove-output-dir` CLI parameter is deprecated and still accepted. The output directory is fully regenerated when no filters are applied, so there is no need to remove it before rendering.
