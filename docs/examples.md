# Example: Monitoring Stack on a Local Kind Cluster

This example demonstrates an end-to-end workflow using **`make-argocd-fly`** to render and deploy a monitoring stack **locally with `kubectl`**.

It shows how to:
- Render **infrastructure** configuration for a local Kind cluster (Generic application type),
- Generate fully rendered **Kubernetes manifests** for applications (Prometheus, Grafana, Alertmanager, etc.),
- And deploy everything end-to-end using `kubectl`.

> 📁 Folder: [`examples/monitoring_stack`](https://github.com/Karandash8/make-argocd-fly/tree/main/examples/monitoring_stack)

---

## 🧩 Architecture Overview

The example contains two layers:

### Infrastructure Layer
- Produces the Kind cluster configuration file (`cluster.yml`) via Jinja2 templates.
- Output is placed under `output/local/infra/kind/`.

### Application Layer
- Renders Kubernetes manifests for the monitoring stack:
  - Alertmanager
  - Grafana
  - kube-state-metrics
  - node-exporter
  - Prometheus
- Output is placed under `output/local/k8s/`.

---

## ⚙️ Workflow: Render → Deploy → Verify

### Step 1. Render all manifests

Run `make-argocd-fly` from the example root:

```bash
make-argocd-fly
```

This command:
- Renders the **Kind cluster config** under `output/local/infra/kind/`
- Renders all **application manifests** under `output/local/k8s/`

### Step 2. Create the local Kind cluster

Use the rendered cluster configuration to create your Kind cluster:

```bash
kind create cluster --config output/local/infra/kind/cluster.yml --name local-kind
```

### Step 3. Deploy the stack

Apply all rendered manifests directly with `kubectl`:

```bash
kubectl apply -f output/local/k8s/common --recursive --server-side
kubectl apply -f output/local/k8s --recursive --server-side
```

Check resources:

```bash
kubectl get pods -A
```

### Step 4. Access UIs

To access Grafana, open a browser and go to [`http://localhost:30000`](http://localhost:30000).

To access Prometheus, go to [`http://localhost:30001`](http://localhost:30001).

To access Alertmanager, go to [`http://localhost:30002`](http://localhost:30002).


### Step 5. Cleanup

When you’re done:

```bash
kind delete cluster --name local-kind
```

---

## 🧠 Why This Example Matters

### Rendered Manifest Pattern
This example demonstrates the **Rendered Manifest Pattern**, where manifests are **fully generated and version-controlled** before deployment.
You can inspect, lint, and diff them — ensuring clarity about what gets deployed.

### Flexible Deployment Model
`make-argocd-fly` supports **both** deployment models:
- **Local flows:** render + deploy with `kubectl` — no ArgoCD needed.
- **GitOps flows:** render + commit + let ArgoCD deploy from the repository.

### Same Configuration, Multiple Environments
The exact same configuration can target multiple environments:
- For `local`, no ArgoCD CRs are generated; manifests are applied manually.
- For `dev`, `staging`, or `prod`, you define separate environments in `config/*.yml` and optionally use `parent_app` relations to generate ArgoCD `Application` CRs automatically.

That means:
- Local testing and production share the same templating and structure.
- ArgoCD just becomes another layer of automation — not a requirement.

---

## 🧭 Summary

This example shows that **`make-argocd-fly` is not tied to ArgoCD** —
it’s a **manifest factory** that integrates naturally into any workflow:
from lightweight local clusters to large-scale GitOps setups.
