# Templating with Jinja2

All standard Jinja2 features are supported. For example, to render a Jinja2 template from a file in the current jinja2 template, use the following block:
```
{%- filter indent(width=4) %}
{% include 'files/file.json.j2' %}
{% endfilter %}
```

## 🧪 Custom Jinja2 Extensions and Filters
`make-argocd-fly` provides several custom Jinja2 extensions and filters to enhance your templating experience. These extensions and filters are designed to simplify common tasks and improve the readability of your templates.


- `rawinclude` - to include literal file content (without rendering) in the current jinja2 template, use the following block:
  ```
  {%- filter indent(width=4) %}
  {% rawinclude 'files/file.json' %}
  {% endfilter %}
  ```
- `include_map` - to render templates from a subdirectory as YAML key-value pairs (where file name would be the key and rendered file content would be the value), use the following block:
  ```
  {%- filter indent(width=2) %}
  {% include_map 'files/' %}
  {% endfilter %}
  ```

- `rawinclude_map` - to include literal file content from a subdirectory as YAML key-value pairs (where file name would be the key and file content would be the value), use the following block:
  ```
  {%- filter indent(width=2) %}
  {% rawinclude_map 'files/' %}
  {% endfilter %}
  ```

- `include_list` - to render templates from a subdirectory as YAML list (where list elements would be rendered file content), use the following block:
  ```
  {%- filter indent(width=2) %}
  {% include_list 'files/' %}
  {% endfilter %}
  ```

- `rawinclude_list` - to include literal file content from a subdirectory as YAML list (where list elements would be file content), use the following block:
  ```
  {%- filter indent(width=2) %}
  {% rawinclude_list 'files/' %}
  {% endfilter %}
  ```

- `file_list` - to render file names in a subdirectory as YAML list (where list elements would be file names), use the following block:
  ```
  {%- filter indent(width=6) %}
  {% file_list 'files/' [<prefix>] %}
  {% endfilter %}
  ```
  Note that there is an optional second parameter, which is a prefix that will be added to each file name in the list. This can be useful for constructing full paths or URLs.

- `dig` - to perform a DNS lookup, use the following filter:
  ```
  {{ 'example.com' | dig }}
  ```

- [Ansible filters](https://pypi.org/project/jinja2-ansible-filters/) are supported as well

---
