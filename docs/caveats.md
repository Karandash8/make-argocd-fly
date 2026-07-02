# Troubleshooting & Known Limitations

- YAML comments are stripped during rendering because YAML resources are parsed and re-emitted.
- Jinja2 uses `StrictUndefined`; missing variables fail rendering.
- Unresolved `${...}` references that survive config merging fail during final template rendering.
- Duplicate keys across merged config files fail config loading instead of silently overriding.
- The latest-version check queries PyPI and may prompt on connectivity or version issues. Use `--skip-latest-version-check` in CI and local fixture renders.
- Kustomize and Helmfile rendering require external CLIs on `PATH`: `kustomize` and `helmfile` respectively.
- Full renders regenerate the output directory via a temporary output swap. Partial renders with `--render-envs` or `--render-apps` copy unfiltered apps from the existing output first.
- `--dump-context` keeps `.tmp` and writes debug JSON under `.tmp/context-dumps/<env>/<app>/`.
