# Real-World Example: Monitoring Stack

This example demonstrates how to use `make-argocd-fly` to render and manage a monitoring stack in Kubernetes using ArgoCD, following the App-of-Apps pattern.
> **Note:**
> To use this example, copy the `examples/monitoring_stack` directory into your own repository.
> Make sure to set your repository URL in the `repo_url` variable inside `config/config.yml` so ArgoCD can reference the correct source location.
## 📦 Components

The monitoring stack includes:

- **Prometheus** – core monitoring and alerting engine
- **Alertmanager** – routes alerts triggered by Prometheus
- **Grafana** – for dashboards and visualization
- **Node Exporter** – collects node-level system metrics
- **Kube-State-Metrics** – exposes Kubernetes resource metrics

Each component is defined as an independent application, allowing you to manage, update, and scale them individually while maintaining centralized control.

## 🗂 Directory Structure

```text
examples/
└── monitoring_stack/
    ├── config/
    │   └── config.yml              # environment, apps, and variables
    └── source/
        ├── alertmanager/
        ├── grafana/
        ├── kube-state-metrics/
        ├── node-exporter/
        └── prometheus/
```

## ⚙️ Configuration Overview
The `config/config.yml` file defines:

- A single environment (e.g., local)

- Applications listed under that environment

- Global and app-level variables

- ArgoCD deployment parameters (repository URL, target revision, destination cluster, etc.)

- sync_wave and parent_app to control render order and nesting

## 🚀 How It Works
1. The `bootstrap_parent` application is treated specially:

   - It includes an ArgoCD Application manifest that references other applications.

   - This application is not deployed by ArgoCD initially.

2. To kick off the deployment, you apply the bootstrap app manually using `kubectl`:

```bash
kubectl apply -f output/local/bootstrap_parent/application_bootstrap-local.yml
```

3. ArgoCD picks up the Application defined in `bootstrap_parent`, which in turn deploys all other applications (prometheus, grafana, etc.) defined under it.

4. From that point onward, ArgoCD manages the sync and lifecycle of all the rendered applications.

## 💡 Benefits
- Clear separation between bootstrapping and runtime apps

- GitOps-native workflow using ArgoCD’s App-of-Apps pattern

- Scalable and reproducible observability stack for Kubernetes environments

- Extensible configuration using Jinja2, Helm, and Kustomize

## 🔁 To Regenerate Output
Run:

```bash
make-argocd-fly
```

This will populate the `output/` directory with ArgoCD-ready application manifests.
