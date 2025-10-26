# Templating with Jinja2

`make-argocd-fly` applies Jinja2 templating at the **application level**.
This means templates are rendered **relative to the application directory**, not the repository root.

For example, if your application lives under:
```
source/monitoring/grafana/
```

then:

```
{% include "dashboards/cpu-overview.json.j2" %}
```

is resolved relative to `source/monitoring/grafana/`.

There is **no need to prefix paths with the full source directory**.

---

## 📁 Application Directory Boundaries

Previously, includes were restricted to application-local paths.
Now, **parent directory traversal is allowed** when needed:

```
{% include "../shared/common-labels.yml.j2" %}
```

This allows:
- Reusing shared template fragments across multiple apps
- Maintaining organization without duplicating resources

### ⚠️ Important Notes
- Parent traversal is **intentional**, not accidental.
  If a template references a path outside the controlled source tree, rendering will raise an error.
- This ensures the feature is powerful but **safe and predictable**.

---

## 🧙 Jinja2 Features You Can Use

### Including another template

```
{%- filter indent(width=4) %}
{% include 'files/file.json.j2' %}
{% endfilter %}
```

### Raw include (no templating on included file)

```
{%- filter indent(width=4) %}
{% rawinclude 'files/file.json' %}
{% endfilter %}
```

### Mapping files as YAML key-value pairs (where file name would be the key and rendered file content would be the value)

```
{%- filter indent(width=2) %}
{% include_map 'files/' %}
{% endfilter %}
```

### Raw mapping (no templating on included file)

```
{%- filter indent(width=2) %}
{% rawinclude_map 'files/' %}
{% endfilter %}
```

### Listing files content as YAML list (where list elements would be rendered file content)

```
{%- filter indent(width=2) %}
{% include_list 'files/' %}
{% endfilter %}
```

### Raw listing (no templating on included file)

```
{%- filter indent(width=2) %}
{% rawinclude_list 'files/' %}
{% endfilter %}
```

### Listing file names as YAML list (where list elements would be file names)

```
{%- filter indent(width=6) %}
{% file_list 'files/' [<prefix>] %}
{% endfilter %}
```

Note that there is an optional second parameter, which is a prefix that will be added to each file name in the list. This can be useful for constructing full paths or URLs.

## 🌍 Ansible Filters & Utilities

Your templates also have access to:

- Full [`jinja2-ansible-filters`](https://pypi.org/project/jinja2-ansible-filters/) set
- DNS lookup helper:

  ```
  {{ 'example.com' | dig }}
  ```

---

## Application Types Overview

| Type | Source | Engine | Typical use |
|------|--------|--------|-------------|
| `generic` | text file / Jinja2 | Jinja2 | infra files (e.g., kind config), passthrough assets |
| `k8s` | YAML / Jinja2 | Jinja2 + Kustomize or Helmfile | plain Kubernetes manifests |

> See also: [kustomize.md](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/kustomize.md) and [Examples](https://github.com/Karandash8/make-argocd-fly/blob/main/docs/examples.md)
