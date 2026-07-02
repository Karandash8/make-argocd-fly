# Kustomize & Helmfile Applications

`make-argocd-fly` supports multiple Kubernetes application types that build on top of native CLI tools.
These application types allow you to structure, template, and render your Kubernetes resources before GitOps deployment.

---

## 🧱 Kustomize Applications

Kustomize applications are detected before Helmfile applications. A `k8s` application is treated as Kustomize when it contains one of these files at the app root, in `base/`, or in an environment-named directory: `kustomization.yml`, `kustomization.yaml`, `Kustomization.yml`, or `Kustomization.yaml`.

Kustomize applications are rendered in two steps:
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

For `base/` and environment overlay layouts, `make-argocd-fly` renders only the `base/` directory and the current environment directory when preparing files for Kustomize. If the kustomization is at the app root and there is no `base/` or environment overlay layout, the whole application directory is rendered. If your overlay references additional shared directories — for example, a `common/` directory with patches or resources used across multiple overlays — declare them with the `kustomize_common_dirs` parameter:

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

YAML values files such as `values.yml`, `values.yaml`, and their `.j2` variants are YAML resources and are discovered during Kustomize staging when they are under the searched Kustomize directories. They are staged with source-style filenames in the temporary Kustomize workspace so Kustomize can reference them; for example, `values.yaml.j2` is rendered and staged as `values.yaml`.

Non-YAML values files under the searched Kustomize directories can be explicitly included with `non_k8s_files_to_render`. Use an application-relative path or glob:

```yaml
envs:
  <environment_name>:
    apps:
      <application_name>:
        params:
          non_k8s_files_to_render: ['base/values.txt']
```

And then reference it in your Helm chart configuration:

```yaml
helmCharts:
  - name: my-chart
    version: 1.0.0
    valuesFile: values.txt
```

If the file is in a shared directory outside `base/` and the environment overlay, add that directory with `kustomize_common_dirs` as well.

## ⛵ Helmfile Applications

Helmfile applications are detected when a `k8s` application has a `helmfile.yaml` or `helmfile.yaml.j2` file at depth 1 and no Kustomize file was detected first. YAML files in the application are staged, Jinja2 templates are rendered, and then `helmfile template --quiet` is executed from the staged application directory.

```yaml
envs:
  <environment_name>:
    apps:
      <application_name>:
        params: {}
```

Non-YAML files required by Helmfile are not staged by the Helmfile pipeline. Keep Helmfile inputs as YAML files, or use Kustomize with `non_k8s_files_to_render` if you need to stage arbitrary files.
