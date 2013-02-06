#!python
from coverity.email import main

# If you want to add your own reporting format, you can do
# something like this::
#
#       from coverity.templates import available_formats
#       from coverity.templates.cim_charts import CSVTemplate
#       available_formats['custom'] = CSVTemplate('cid')
#
# See coverity.templates.cim_charts for more info.

if __name__ == '__main__':
    main()
