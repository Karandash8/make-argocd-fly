# Deprecations in `make-argocd-fly`
## `v0.2.14`
### Root level config file deprecations (removed in `v0.3.0`)
CLI parameter `--config-file` is deprecated and will be removed in the future. A new parameter `--config-dir` is introduced with the default value of `config`. The new parameter allows to specify a directory with multiple `*.yml` config files, while the old parameter allowed to specify a single file. When multiple config files are found in the directory they are merged together, while any duplicate keys are reported back to the user as an error.

## `v0.2.15`
### App params deprecations
`app_deployer`, `app_deployer_env`, `non_k8s_files_to_render` and `exclude_rendering` keys defined directly under the application are deprecated and will be removed in the future. A new `params` keyword that supports scoping is introduced. Currently allowed params:
- `parent_app` - the name of the parent application
- `parent_app_env` - the name of the parent application environment
- `non_k8s_files_to_render` - a list of non-Kubernetes files to render
- `exclude_rendering` - a list of directories to exclude from rendering

### Custom Jinja2 extensions deprecations
Existing Jinja2 extensions were renamed in order to make their function more clear:
- `include_raw` -> `rawinclude`
- `include_all_as_yaml_names_list` -> `file_list`
- `include_all_as_yaml_kv` -> `include_map`
- `include_all_as_yaml_list` -> `include_list`
