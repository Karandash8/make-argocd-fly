# Getting Started

This guide walks you through installing `make-argocd-fly`, setting up dependencies, and running your first render.

## ⚙️ Prerequisites

Ensure the following tools are installed if you use the related features:

- `python 3.11+`
- `helm` if Helm chart rendering is needed
- `helmfile` if Helmfile support is needed
- `kustomize` if Kustomize overlays are needed
- `libyaml` if faster YAML parsing is needed
- `yamllint` if linting YAML files is needed
- `kube-linter` if linting Kubernetes manifests is needed

## 📦 Installation

Create a virtual environment and install `make-argocd-fly`:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install make-argocd-fly
```

## 📁 Project Structure

A typical project consists of three main directories:

### `config/`
This directory contains **any number of `.yml` files** defining your environments, applications, and variables.
All configuration files in this directory are **merged together at runtime**.

Example:
```
config/
  ├── environments.yml
  ├── variables.yml
  └── apps-dev.yml
```

For a reference structure, see the [example project](https://github.com/Karandash8/make-argocd-fly/tree/main/examples/app_types).

### `source/`
This is where you place the **source code of your applications**.
Applications can be defined in:
- Plain Kubernetes YAML
- Jinja2 templates
- Kustomize overlays (with or without Helm integration)

### `output/`
After running `make-argocd-fly`, this directory is **automatically populated** with the rendered application manifests.
The structure will mirror your environment and application layout for easy navigation.

For a reference project structure, see the [example under `examples/app_types`](https://github.com/Karandash8/make-argocd-fly/tree/main/examples/app_types).

## 🚀 First Run
To render your applications, run the following command:

```bash
make-argocd-fly [OPTIONS]
```

## 5-Minute Quick Start
```bash
pip install make-argocd-fly
make-argocd-fly --config-dir config --source-dir source --output-dir output
```
> See also: [Examples](examples.md)

### Project layout recap
- `config/` — one or more `.yml` files that define environments, applications, and variables. All files are **merged** at runtime.
- `source/` — application sources in YAML/Jinja/Kustomize/Helm; Generic apps can contain any text assets.
- `output/` — fully rendered manifests, organized per environment.
