# CLI Reference

This section explains how to use the `make-argocd-fly` command-line interface. You can always display the full help with:

```bash
make-argocd-fly -h
```

## 🔁 Input & Output Paths

| Flag               | Description                                              |
|--------------------|----------------------------------------------------------|
| `--root-dir`       | Root directory (default: current directory)              |
| `--config-dir`     | Directory containing config files (default: `config`)    |
| `--source-dir`     | Directory containing source files (default: `source`)    |
| `--output-dir`     | Directory for rendered output (default: `output`)        |
| `--tmp-dir`        | Directory for temporary files (default: `.tmp`)          |

---

## 🎯 Render Control

| Flag                   | Description                                                              |
|------------------------|--------------------------------------------------------------------------|
| `--render-envs`        | Comma-separated list of environments to render                           |
| `--render-apps`        | Comma-separated list of applications to render                           |
| `--skip-generate`      | Skip resource generation step                                            |
| `--remove-output-dir`  | Remove existing output directory before rendering                        |
| `--preserve-tmp-dir`   | Keep temporary directory after execution                                 |

---

## 🔍 Debug & Inspection

| Flag                      | Description                                                                      |
|---------------------------|----------------------------------------------------------------------------------|
| `--dump-context`          | Dump per-stage context snapshots for debugging                                   |
| `--stats`                 | Print execution time statistics per stage and per application                   |
| `--var-identifier`        | Prefix used for variable interpolation in config files (default: `$`)           |
| `--loglevel`              | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`               |
| `--skip-latest-version-check` | Suppress remote version check                                                |

---

## 🔎 Linting & Validation

| Flag             | Description                                                                 |
|------------------|-----------------------------------------------------------------------------|
| `--yaml-linter`  | Run [`yamllint`](https://github.com/adrienverge/yamllint) on the output     |
| `--kube-linter`  | Run [`kube-linter`](https://github.com/stackrox/kube-linter) on the output  |

---

## 📦 Misc

| Flag            | Description                     |
|-----------------|---------------------------------|
| `-h`, `--help`  | Show CLI help                   |
| `--version`     | Show current version and exit   |
| `--max-concurrent-apps` | Max number of apps to render concurrently (default: 8) |
| `--max-subproc` | Max number of subprocesses to run concurrently (default: number of CPU cores) |
| `--max-io`      | Max number of I/O operations to run concurrently (default: 32) |
