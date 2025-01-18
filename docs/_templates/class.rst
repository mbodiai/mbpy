
{%- if show_headings %}
{{- basename | heading }}
{% endif -%}
.. autoclass:: {{ qualname }}
   :members:
   :undoc-members:
   :show-inheritance:
