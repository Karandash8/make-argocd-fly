# Kustomize & Helm Integration

Kustomize applications are rendered in two steps:
1. **Preparation**: Jinja2 templates are rendered and source manifest files are renamed to match the resource naming convention.
2. **Kustomization**: The rendered manifests are processed by Kustomize to generate the final Kubernetes manifests.

## 🏷️ Kustomize Resource Naming

Local files that are referenced in the `resources:` section of Kustomize should follow a specific resource naming convention. The referenced file names should consist of the Kubernetes resource type followed by an underscore (`_`) and the resource name.

```yaml
resources:
  - deployment_nginx.yml
  - serviceaccount_nginx-prod.yml
```

## 🧱 Kustomize Overlays

When using Kustomize overlays, the directory structure should follow these conventions:

- `base/` directory for shared definitions
- overlay folders named after environment names

## 🛠️ Helm Integration

Helm charts can be integrated into the Kustomize workflow by using helm chart inflation through the `helmCharts` field.

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

---
