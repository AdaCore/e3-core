e-core API
##########

.. toctree::
   :includehidden:
   :glob:
   :maxdepth: 1

   {# Force whitespace #}

   {%- for page in pages %}
   {%- if page.top_level_object %}
   {{ page.include_path }}
   {%- endif %}
   {%- endfor %}
