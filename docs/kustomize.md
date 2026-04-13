# Kustomize & Helm Applications

`make-argocd-fly` supports multiple Kubernetes application types that build on top of native CLI tools.
These application types allow you to structure, template, and render your Kubernetes resources before GitOps deployment.

---

## 🧱 Kustomize Applications

Kustomize applications are defined by creating a `kustomization.yml` file and are rendered in two steps:
1. **Preparation**: Jinja2 templates are rendered and source Kubernetes manifests are normalized.
2. **Kustomization**: The rendered manifests are processed by Kustomize to produce final manifests.

### Resource Naming Convention

Local files that are referenced in the `resources:` section of Kustomize should follow a specific resource naming convention. The referenced file names should consist of the Kubernetes resource type followed by an underscore (`_`) and the resource name.

```yaml
resources:
  - deployment_nginx.yml
  - serviceaccount_nginx-prod.yml
```

### Directory Structure

When using Kustomize overlays, the directory structure should follow these conventions:

- `base/` directory for shared definitions
- overlay folders named after environment names

Example:
```
my-app/
  base/
    kustomization.yml
  dev/
    kustomization.yml
  prod/
    kustomization.yml
```

### Common Directories

By default, `make-argocd-fly` renders only the `base/` and current environment directories when preparing files for Kustomize. If your application references additional shared directories — for example, a `common/` directory with patches or resources used across multiple overlays — you can declare them with the `kustomize_common_dirs` parameter:

```yaml
envs:
  <environment_name>:
    apps:
      <application_name>:
        params:
          kustomize_common_dirs: ['common', 'crds']
```

Directories listed in `kustomize_common_dirs` are rendered into the temporary working directory alongside `base/` and the environment overlay, making them available for Kustomize to reference.

**Example structure:**
```
my-app/
  base/
    kustomization.yml
  common/
    patch-resources.yml
  dev/
    kustomization.yml
  prod/
    kustomization.yml
```

With `kustomize_common_dirs: ['common']`, the `common/` directory will be rendered and available for `dev/kustomization.yml` and `prod/kustomization.yml` to reference.

> **Note:** If a directory listed in `kustomize_common_dirs` does not exist in the application's source directory, it is skipped with a warning rather than causing an error. This makes it safe to define the parameter at the global or environment scope where not all applications will have every listed directory.

> **Note:** Jinja2 variables used inside common directories must be defined for all environments that render that application. If a variable is only available in some environments, use `kustomize_common_dirs` selectively at the environment or application scope rather than globally.

### Helm Integration Inside Kustomize

Kustomize supports Helm chart inflation via:

```yaml
helmCharts:
  - name: my-helm-chart
    chart: charts/my-helm-chart
    version: 1.0.0
    valuesInline:
      replicaCount: 2
```

### Helm Values File Handling

`values.yml` files are not automatically rendered by `make-argocd-fly` as they are not Kubernetes manifests. However, you can specify them in the `non_k8s_files_to_render` parameter to include them in the rendering process:

```yaml
envs:
  <environment_name>:
    apps:
      <application_name>:
        params:
          non_k8s_files_to_render: ['values.yml']
```

And then reference it in your Helm chart configuration:

```yaml
helmCharts:
  - name: my-chart
    version: 1.0.0
    valuesFile: values.yml
```

## ⛵ Helmfile Applications

Helmfile applications are similar to Kustomize applications and are defined by creating a `helmfile.yaml` file. `helmfile.yaml` file needs to be added to `non_k8s_files_to_render` parameter to be rendered by `make-argocd-fly`.

```yaml
envs:
  <environment_name>:
    apps:
      <application_name>:
        params:
          non_k8s_files_to_render: ['helmfile.yaml']
```
