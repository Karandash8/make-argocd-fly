# ✈️ make-argocd-fly

A powerful tool for generating **ArgoCD Applications** and their **rendered Kubernetes resources** from **Helm**, **Kustomize**, and **Jinja2** — across multiple environments, at scale.

[![tests](https://img.shields.io/github/actions/workflow/status/Karandash8/make-argocd-fly/coverage.yml?branch=main)](https://github.com/Karandash8/make-argocd-fly/actions/workflows/coverage.yml)
[![cov](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Karandash8/26eb92c97bbfac22b938afebac85e7cd/raw/covbadge.json)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/Karandash8/26eb92c97bbfac22b938afebac85e7cd/raw/covbadge.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🔧 What It Does

**`make-argocd-fly`** lets you:

- Render **Helm charts** and **Kustomize overlays** into plain Kubernetes manifests, so you know exactly what will be deployed
- Add **Jinja2-based templating** for reusable parametrization
- Automatically generate **ArgoCD Application** resources
- Organize applications into a **well-defined directory structure**
- Define multiple environments and control **what gets deployed where**

Think of it as a static GitOps generator for Kubernetes — rendering, organizing, and wiring your apps for ArgoCD.

---

## 💡 Key Features

* ✅ **Helm rendering**
Render Helm charts into raw manifests.

* ✅ **Kustomize overlays**
Render Kustomize overlays into fully resolved Kubernetes manifests. See the full, flattened configuration before deployment.

* ✅ **Jinja2 templating**
Use variables, logic, and partials to build composable app definitions.

* ✅ **Multi-environment support**
Define once and deploy to multiple environments (e.g. `dev`, `staging`, `prod`) with clean separation of concerns.

* ✅ **ArgoCD Application generation**
Automatically generate Application CRs based on your configuration and environment layout.

* ✅ **Repeatable & Git-friendly**
Fully GitOps-compatible. Output is deterministic and fits naturally into pull request workflows.

---

## 📦 Installation

```bash
pip install make-argocd-fly
```

---

## 📁 Project Structure (Example)

```
config/
  ├── my_vars.yml              # Config file
  └── my_apps.yml              # Config file
source/
  ├── my_awesome_app/          # Application source resources
  └── monitoring/
        ├── prometheus/        # Application source resources
        └── grafana/           # Application source resources
output/
  └── my_env/                  # Environment name
        ├── my_awesome_app/    # Application YAML resources
        └── monitoring/
            ├── prometheus/    # Application YAML resources
            └── grafana/       # Application YAML resources
```

---

## 🔄 Example Workflow

```
make-argocd-fly
```

What it does:
- Renders Helm or Kustomize into raw manifests
- Applies Jinja2 templates with the right variables
- Generates `Application` manifests for ArgoCD
- Organizes everything under `./output/`

---

## 📘 Documentation

- [Getting Started](docs/getting-started.md)
- [Configuration](docs/configuration.md)
- [Argocd Application Generation](docs/argocd.md)
- [Kustomize & Helm Integration](docs/kustomize.md)
- [Using Jinja2 Templates](docs/templates.md)
- [CLI Reference](docs/cli.md)
- [Caveats & Limitations](docs/caveats.md)

---

## 📣 Community & Feedback

- Found a bug or have a feature request? [Open an issue](https://github.com/Karandash8/make-argocd-fly/issues)
- Want to contribute? Check out [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 🛡 License

MIT License – see [LICENSE](https://github.com/Karandash8/make-argocd-fly/blob/main/LICENSE) for full text.
