# AGENTS.md

## Setup
- Target runtime is Python `>=3.11`; install both pinned files: `pip install -r requirements.txt` and `pip install -r requirements.dev.txt`.
- Versioning is dynamic via `setuptools-scm`; there is no source file version to edit.
- Python code uses 2-space indentation. CI flake8 enforces `--indent-size=2`, `--max-line-length=150`, and `--max-complexity=10`; do not reformat to Black-style 4 spaces.
- There is no Black, Ruff, mypy, or pre-commit config in this repo.

## Commands
- Run unit tests: `pytest -q`.
- Run one test: `pytest -q tests/test_config.py::test_list_filtered_envs__exact_match`.
- Run tox for one installed interpreter: `python -m tox -e py311` (or `py312`, `py313`, `py314`). Plain `python -m tox` expects all four Python envs plus coverage envs.
- CI flake8 options are only in `.github/workflows/tests.yml`; run both commands when checking lint:

```bash
flake8 make_argocd_fly --count --select=E9,F63,F7,F82 --show-source --extend-exclude=".venv,.vscode,.pytest_cache,.github,dist" --statistics
flake8 make_argocd_fly --count --indent-size=2 --max-complexity=10 --max-line-length=150 --extend-exclude=".venv,.vscode,.pytest_cache,.github,dist" --statistics
```

- Run the source CLI as `python3 main.py --root-dir <fixture> --skip-latest-version-check`; installed entrypoints are `make-argocd-fly` and `maf`.

## CI Fixture Checks
- CI rerenders committed outputs and fails if these paths become dirty:

```bash
python3 main.py --root-dir examples/app_types --skip-latest-version-check
python3 main.py --root-dir examples/monitoring_stack --skip-latest-version-check
python3 main.py --root-dir tests/e2e --skip-latest-version-check
python3 main.py --root-dir tests/e2e_deprecated --skip-latest-version-check
git status --porcelain examples/app_types/output examples/monitoring_stack/output tests/e2e/output tests/e2e_deprecated/output
```

- Kustomize/Helmfile renders require external CLIs on `PATH`; the code runs `kustomize build --enable-helm .` and `helmfile template --quiet`.
- Always use `--skip-latest-version-check` for local fixture renders, otherwise the CLI queries PyPI and may prompt on version or connection issues.

## Architecture
- Root `main.py` is only a wrapper; console scripts call `make_argocd_fly.main:cli_entry_point`.
- Runtime state is stored in singleton CLI/config objects populated by `make_argocd_fly.main.main`.
- Rendered projects default to `config/`, `source/`, `output/`, and `.tmp`; all `.yml` and `.yaml` files in `config/` are merged, and duplicate keys raise an error.
- Full renders clear `.tmp`, `.tmp.<output>`, and `<output>.old`, write into `.tmp.output`, then swap into `output`.
- Focused renders with `--render-envs` or `--render-apps` use comma-separated glob patterns and copy unfiltered apps from existing output before swapping.
- For `app_type: k8s`, source shape selects the pipeline: kustomization YAML in root/base/env means Kustomize, helmfile YAML at depth 1 means Helmfile, missing source directory means app-of-apps, otherwise simple YAML/Jinja. Kustomize is checked before Helmfile.
- Kustomize execution dir priority is current environment, then `base`, then app root; base/env layouts stage only `base/`, the current environment, and `kustomize_common_dirs`, while root-level kustomization stages all app files.
- `app_type: generic` renders all file types as Jinja/passthrough; `k8s` renders Kubernetes YAML/Jinja, Kustomize, Helmfile, and app-of-apps pipelines. Kustomize stages YAML driver/source files such as `kustomization.yaml` and `values.yaml`; explicitly listed `non_k8s_files_to_render` is for additional non-Kubernetes files in the staged Kustomize scope.

## Rendering Gotchas
- Jinja includes resolve relative to the application directory under `source/`; parent traversal is allowed but constrained by the scoped viewer.
- Custom Jinja tags are `rawinclude`, `file_list`, `include_map`, `rawinclude_map`, `include_list`, and `rawinclude_list`; older names are deprecated in `DEPRECATIONS.md`.
- Templates use `StrictUndefined`, Ansible filters, and the `dig` DNS filter; unresolved `${...}` variable references also fail during rendering.
- YAML comments are stripped during rendering.
- App-of-apps names default to the last path segment plus env; set `params.application_name: full` to avoid collisions for nested apps with the same basename.
- `--dump-context` keeps `.tmp` and writes per-stage JSON under `.tmp/context-dumps/<env>/<app>/`.

## Behavior Changes
- Update docs alongside code for CLI/config/template behavior (`docs/cli.md`, `docs/configuration.md`, `docs/templates.md`, `docs/kustomize.md`, `docs/argocd.md` as applicable).
- Update `DEPRECATIONS.md` when adding or removing deprecated CLI flags, params, or template names.
- If rendering behavior changes, rerun the affected fixture command above and intentionally commit updated `output/` files.
