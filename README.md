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

## 🧩 The Rendered Manifest Pattern

The Kubernetes GitOps community recently introduced the [Rendered Manifest Pattern](https://www.youtube.com/watch?v=TonN-369Qfo) as a best practice for managing applications with ArgoCD.

Instead of letting ArgoCD invoke Helm or Kustomize internally, you **pre-render manifests outside the cluster** and commit only plain YAML to Git.
This makes your Git repo the *single source of truth* for the exact Kubernetes resources being deployed.

### Why this matters

When ArgoCD runs Helm or Kustomize directly, you may hit problems like:
- **Version drift** – different clusters use different plugin versions and render inconsistently
- **Debugging blind spots** – failures happen inside ArgoCD, with no access to the rendered YAML
- **Unreviewable diffs** – Git diffs show template changes, not the actual manifests applied
- **Limited portability** – CI/CD, linters, and policy tools can’t easily check resources
- **Operational surprises** – subtle plugin/env differences lead to unexpected drift

With pre-rendered manifests you gain:
- **Single source of truth** – Git shows exactly what ArgoCD applies
- **Deterministic builds** – no hidden differences across environments
- **Transparent reviews** – PR diffs show actual Kubernetes changes
- **Pluggable checks** – run linters and security scanners on YAML in CI
- **Simpler ops** – ArgoCD only syncs plain YAML, reducing complexity

**`make-argocd-fly` is a practical implementation of the Rendered Manifest Pattern.**
It automates rendering of Helm charts, Kustomize overlays, and Jinja2 templates, organizes them by environment, and generates ArgoCD `Application` resources pointing to the rendered output.


---

## 💡 Key Features

* **Helm rendering**
Render Helm charts into raw manifests.

* **Kustomize overlays**
Render Kustomize overlays into fully resolved Kubernetes manifests. See the full, flattened configuration before deployment.

* **Jinja2 templating**
Use variables, logic, and partials to build composable app definitions.

* **Multi-environment support**
Define once and deploy to multiple environments (e.g. `dev`, `staging`, `prod`) with clean separation of concerns.

* **ArgoCD Application generation**
Automatically generate Application CRs based on your configuration and environment layout.

* **Repeatable & Git-friendly**
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

**Shortcut:** you can also use `maf` as an alias for `make-argocd-fly`.

What it does:
- Applies Jinja2 templates with the right variables
- Renders Helm and Kustomize into raw manifests
- Generates `Application` manifests for ArgoCD
- Organizes everything under `./output/`

---

## 📘 Documentation

- [Getting Started](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/getting-started.md)
- [Configuration Reference](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/configuration.md)
- [Application Templates](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/templates.md)
- [Kustomize & Helm Applications](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/kustomize.md)
- [ArgoCD Integration](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/argocd.md)
- [CLI Reference](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/cli.md)
- [Examples](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/examples.md)
- [Troubleshooting & Limitations](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/caveats.md)

---

## 📣 Community & Feedback

- Found a bug or have a feature request? [Open an issue](https://github.com/Karandash8/make-argocd-fly/issues)
- Want to contribute? Check out [CONTRIBUTING.md](https://github.com/Karandash8/make-argocd-fly/blob/main/CONTRIBUTING.md)

---

## 🛡 License

MIT License – see [LICENSE](https://github.com/Karandash8/make-argocd-fly/blob/main/LICENSE) for full text.
