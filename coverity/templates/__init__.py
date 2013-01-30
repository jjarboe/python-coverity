# To add custom report formats, just add a member named like "render_as_x", where
# "x" will be the name of the report format when invoking the email_defects.py
# script.  You can use the templite syntax like these built-in reports, or you
# can use any other format you like (assuming you have the appropriate templating
# system installed).  The "render_as_x" member will be called as a function from
# the email_defects.py script.  See that script for details of the parameters
# passed to the function.

# Seek to "TEMPLATE_START" to view the existing templates.
# Seek to "TEMPLATE_END" to add new templates.

from cim_charts import defect_counts, Template, CSVTemplate, ChartTemplate, MetricsChartTemplate, CircleChartTemplate, XMLTemplate

#=========================================================
# Template classes to be used for the individual reports
class SingleLineTemplate(Template):
    '''
    A wrapper for Template that strips carraige returns and linefeeds
    '''
    def __init__(self, template, factory=None, **kw):
        super(SingleLineTemplate, self).__init__(template, factory=factory, **kw)

    def __call__(self, __namespace=None, **kw):
        return super(SingleLineTemplate, self).__call__(__namespace, **kw).replace('\r','').replace('\n','').strip()

###########################################################################
#
# Templates start here.  The string "TEMPLATE_START" serves as a
# bookmark for users to find this section quickly.
#

#=============================================================
# Basic templates

# The subject of the message
render_subject = SingleLineTemplate(
'''
${if user in (None, 'Unassigned'): }$
    Un${relationship}$ed defects found
${:else:}$
    ${intro}$
${:endif}$
'''
)
 
# The intro text of the message
render_intro = SingleLineTemplate(
'''
${intro}$
${if options.days:}$
   in the past ${"%d"%(options.days,)}$ day${
        if options.days > 1:}$s${:endif}$
${:endif}$

${if options.project or options.stream:}$
   in
   ${if options.project:}$ project ${options.project}$
   ${:elif options.stream:}$ stream ${options.stream}$
   ${:endif}$
${:elif options.snapshot:}$
        ${if options.snapshot_op == 'new':}$ new in
        ${:else:}$ fixed by
        ${:endif}$
        snapshot ${options.snapshot}$
${:endif}$
'''
)
    
# List the defects in a simple XML format
render_as_xml = XMLTemplate('cid','status','checkerName','classification','owner','severity','action','firstDetected.strftime("%Y-%m-%d")','componentName','filePathname','scope',
    columns=('cid','status','checker','classification','owner','severity','action','first_detected','component','file','scope')
)

# List the defects in a simple CSV format.
render_as_csv = CSVTemplate('cid','status','checkerName','classification','owner','severity','action','firstDetected.strftime("%Y-%m-%d")','componentName','filePathname','scope',
    columns=('CID','Status','Checker','Classification','Owner','Severity','Action','FirstDetected','Component','File','Scope')
)
render_as_metrics_csv = CSVTemplate('metricsDate', 'projectId.name',"totalCount","newCount","outstandingCount","resolvedCount","dismissedCount","fixedCount","inspectedCount","triagedCount",
    columns=('Date', 'Project',"Total","New","Outstanding","Resolved","Dismissed","Fixed","Inspected","Triaged")
)
render_as_compmetrics_csv = CSVTemplate('componentId.name',"totalCount","newCount","outstandingCount","resolvedCount","dismissedCount","fixedCount","inspectedCount","triagedCount",
    columns=('Date', 'Component',"Total","New","Outstanding","Resolved","Dismissed","Fixed","Inspected","Triaged")
)
render_as_clean_csv = CSVTemplate('cid','status','checkerName','classification','owner','severity','action','firstDetected.strftime("%Y-%m-%d")','componentName','filePathname','scope',
    columns=('CID','Status','Checker','Classification','Owner','Severity','Action','FirstDetected','Component','File','Scope'),
    clean = True
)
render_as_clean_metrics_csv = CSVTemplate('metricsDate', 'projectId.name',"totalCount","newCount","outstandingCount","resolvedCount","dismissedCount","fixedCount","inspectedCount","triagedCount",
    columns=('Date', 'Project',"Total","New","Outstanding","Resolved","Dismissed","Fixed","Inspected","Triaged"),
    clean=True
)
render_as_compowner_csv = CSVTemplate('cid','status','classification','owner','componentName','component.defectRules and getattr(v.defectRules[0],"defaultOwner","") or ""',
    columns=('CID','Status','Classification','Owner','Component','CompOwner')
)
render_as_multcomp_csv = CSVTemplate('cid','status','classification','owner','componentName','occurrenceCount', '!defectInstances v and len(filter(None, [x.function.fileId.filePathname for x in v])) or "UNKNOWN"',
    columns=('CID','Status','Classification','Owner','Components','Count','Instances')
)



#=========================================================
# More complex reports

# List the defects in an HTML table format.
render_as_table = Template(
    '''
    <html><body>
    <p>${intro}$</p>
    <table>
    <tr><th>CID</th>
        <th>Type</th>
        <th>Status</th>
        <th>Owner</th>
        <th>1st Detected</th>
        <th>File</th>
        <th>Function</th>
    </tr>
    ${for defect in defects:}$
        <tr>
        <td><a href="${defect.url}$">${defect.cid}$</a></td>
        <td>${defect.checkerName}$</td>
        <td>${defect.status}$</td>
        <td>${defect.owner}$</td>
        <td>${defect.firstDetected.strftime("%Y-%m-%d")}$</td>
        <td>${defect.filePathname}$</td>
        <td>${defect.scope}$</td>
        </tr>
    ${:end-for}$
    </table>
    </body></html>
    '''
    )

# List the defects in an HTML list format.

render_as_list = Template(
'''
<html><body>
<p>${intro}$</p>
<ul>
${for defect in defects:
}$<li><div>
<a href="${defect.url}$">${defect.cid}$</a> ${
defect.checkerName}$ / ${defect.status}$ ${defect.owner}$ ${
defect.firstDetected.strftime("%Y-%m-%d")}$
<div>${defect.filePathname}$</div>
<div>${defect.scope}$</div>
</div></li>
${:end-for}$
</ul>
</body></html>
'''
)

# This template renders the list of defects as a text report, and includes details
# like events and source code snippets related to the defect.  The template text is a
# bit hard to read since whitespace is significant in plain text output.

render_as_details = Template(
'''${intro}$
    
${for defect in defects:}$
############################################
${defect.cid}$ ${defect.checkerName}$, found ${emit(defect.firstDetected.strftime("%Y-%m-%d %H:%M"))}$
${defect.status}$ / ${defect.owner}$
${defect.url}$
${for inst in defect.defectInstances:}$

In ${
try: emit(inst.function.functionDisplayName)
except AttributeError: emit('<unknown function>') }$ (${inst.function.fileId.filePathname}$)
${src = SourceFile(defect.streamId, inst.function.fileId)
}$${for event in inst.events:}$${if not event.eventNumber:}$

"${event.eventTag}$" event

${for l in src.snippet(event.lineNumber, caption=event.eventDescription):}$${
    if not l.lineNum and event.main:}$${
        checker = CheckerDescription(defect.checkerSubcategoryId)
        }$
==>   CID ${defect.cid}$: ${emit(checker.subcategoryShortDescription
            or 'Unknown defect')}$ (${defect.checkerSubcategoryId.checkerName}$${
        if defect.checkerSubcategoryId.subcategory not in (None, '', 'none'):
        }$.${defect.checkerSubcategoryId.subcategory}$)${:endif
    }$${:endif}$
${if l.lineNum:}$   ${:else:}$${if event.main:}$==> ${:else:}$ -> ${:endif}$${:endif
    }$ ${l.lineNum}$ ${l.text}$${
:end-for}$${:endif}$${:end-for}$${:end-for}$
${if not defect.defectInstances:}$
No source available; originally found in
${defect.scope}$ from ${defect.filePathname}$${:endif}$
${:end-for}$
'''
)

# This template renders the list of defects as an html report, and includes details
# like events and source code snippets related to the defect.  Unfortunately, we can't
# take advantage of much CSS or layout because some popular email readers like Outlook
# 2007 have very limited HTML support.

render_as_details_html = Template(
'''<p>${intro}$<p>

${for defect in defects:}$
  ${checker = CheckerDescription(defect.checkerSubcategoryId)}$
  <div style="background-color:#ccc; padding:5px;"><a href="${defect.url}$">${defect.cid}$ ${defect.checkerName}$</a> found ${emit(defect.firstDetected.strftime("%Y-%m-%d %H:%M"))}$<br>
  ${checker.subcategoryLongDescription}$
  </div>
  <p>${defect.status}$ / ${defect.owner}$</p>
  <ol>
  ${for inst in defect.defectInstances:}$
    <li>In ${
        try: emit(inst.function.functionDisplayName)
        except AttributeError: emit('<unknown function>')
        }$ (${inst.function.fileId.filePathname}$)
        ${src = SourceFile(defect.streamId, inst.function.fileId)}$
        ${for event in inst.events:}$
            ${if not event.eventNumber:}$
                <div>"<b>${event.eventTag}$" event</b></div>
                <table>
                ${for l in src.snippet(event.lineNumber, caption=event.eventDescription):}$
                    <tr>
                    ${if not l.lineNum:}$
                        <td colspan="2"
                            ${if event.main:}$style="background-color:#fcc; color:#f44; padding:3px;"${:endif}$
                        >
                        <b>CID ${defect.cid}$: ${emit(checker.subcategoryShortDescription
                                or 'Unknown defect')}$ (${defect.checkerSubcategoryId.checkerName}$${
                        if defect.checkerSubcategoryId.subcategory not in (None, '', 'none'):}$.${defect.checkerSubcategoryId.subcategory}$${:endif}$)</b><br>
                        ${l.text}$
                        </td>
                    ${:else:}$
                        <td color="#ccc" align="right">${l.lineNum}$</td>
                        <td><pre>${l.text}$</pre></td>
                    ${:endif}$
                    </tr>
                ${:end-for}$
                </table>
            ${:endif}$
        ${:end-for}$
    </li>
  ${:end-for}$
  ${if not defect.defectInstances:}$
    No source available; originally found in
    ${defect.scope}$ from ${defect.filePathname}$
  ${:endif}$
${:end-for}$
'''
)

# This report creates an HTML file which uses Javascript and the d3.js library
# to render a stacked column chart in a browser.

render_as_defects_bar_chart = ChartTemplate(
'''
<h1>${if options.title:}$
${options.title}$
${:elif intro:}$
${intro}$
${:else:}$
Defect counts by component and classification
${:endif}$</h1>
''', 
'''
	${
	classification_colors = {
		'Unclassified': '#ff8888',
		'Bug': '#8888ff',
		'Pending': '#88ff88',
		'False Positive': '#ffcccc',
		'Intentional': '#ffffff'
	}
	status_colors = {
		'New': '#ff8888',
		'Triaged': '#8888ff',
		'Dismissed': '#ffcccc',
		'Fixed': '#ffffff'
	}
	series,categories = defect_counts(defects, options.field, options.stack_field)
	vals = series.values()
	}$
	var def_chk_comp = [${
	for i in range(len(categories)):}$
	  { checker:"${categories[i]}$"${
	       for v in range(len(vals)):}$,"${vals[v].name}$":${vals[v].v[i].data}$${
		   :end-for}$ }${if i!=len(categories)-1:}$,${:endif}$${
	:end-for}$
	];

	${
	if options.stack_field == 'status':
		color_func = lambda x: status_colors[x]
	elif options.stack_field == 'classification':
		color_func = lambda x: classification_colors[x]
	else:
		color_func = False
	}$
    bars_with_proportions(def_chk_comp,
                          "checker",
						  ["${emit('","'.join(series.keys()))}$"]
	${if color_func:}$
						  ,undefined,
						  function(x) {return (["${emit('","'.join(map(color_func, series.keys())))}$"])[x];}
	${:endif}$
						  );
'''
)

# This report creates an HTML file which uses Javascript and the d3.js library
# to render a line chart in a browser.

render_as_metrics_chart = MetricsChartTemplate(
'''
<style>
/* Line colors by classification */
.fixed,.inspected,.dismissed,.triaged { display: none; opacity: 0; stroke: none;}
.outstanding { stroke: #00f;}
.resolved { stroke: #0f0;}
.new { stroke: #800;}
.total {
    stroke: #f84;
    stroke-width: 4px;
    stroke-dasharray: 10,5;
    opacity: .7;
}
</style>
<h1>${if options.title:}$${options.title}$${:elif intro:}$${intro}$${:else:}$Defect metrics${:endif}$</h1>
''',
'''
${
# Preserve the order of this list; we want the most interesting fields first.
states = ("total","new","outstanding","resolved","dismissed","fixed","inspected","triaged")
def fmt_def(x):
  s = ['date:"%s"' % (x.metricsDate,)]
  try:
    s.append('component:"%s"' % (x.componentId.name,))
  except AttributeError:
    s.append('project:"%s"' % (x.projectId.name,))
  for f in (states):
      s.append('"%s":%d' % (f, getattr(x, f+'Count')) )
  return '{' + ','.join(s) + '}'
}$
var metrics = [
${
emit(',\\n'.join(sorted([fmt_def(x) for x in defects])))
}$
];

    line_chart(metrics,
                "date",
				["${ emit('","'.join(states)) }$"]
			   );
'''
)

# This report creates an HTML file which uses Javascript and the d3.js library
# to render a heirarchical circle chart in a browser.

render_as_circles_chart = CircleChartTemplate(
'''
<style type="text/css">

svg {
  width: 1024px;
  height: 1024px;
  font: 8pt sans-serif;
}
circle { stroke-width: 0; fill-opacity: .4; fill: #8bf; }
.leaf circle { fill-opacity: .75; fill: #cc0; }

.leaf.High circle { fill-opacity: 1; fill: #fc0; }
.leaf.Medium circle { fill-opacity: .6; }
.leaf.Low circle { fill-opacity: .2; }

.leaf text { fill: white;}
.leaf.Medium text { font-weight: bold; }
.leaf.High text { font-weight: bold; }
</style>

<h1>${if options.title:}$
${options.title}$
${:elif intro:}$
${intro}$
${:else:}$
Defects by type and component
${:endif}$</h1>
''',
'''
${class Subcat(object):
        def __init__(self, defect = None):
            if defect is None:
                self.checkerName = "FORWARD_NULL"
                self.domain = "CXX"
                self.subcategory = ""
            else:
                self.checkerName = defect.checkerName
                self.domain = defect.domain
                self.subcategory = defect.checkerSubcategory

    }$${
	data,cats = defect_counts(defects, options.field, options.stack_field)
	vals = data.values()
	}$
	var def_chk_comp = [${
	for i in range(len(cats)):}$${
      chk = Subcat([x for x in defects if x.checkerName == cats[i]][0])
      desc = CheckerDescription(chk) }$
	  { checker:"${cats[i]}$",impact:"${desc.impact}$"${
	       for v in range(len(vals)):}$,"${vals[v].name}$":${vals[v].v[i].data}$${
		   :end-for}$ }${if i!=len(cats)-1:}$,${:endif}$${
	:end-for}$
	];
    var cats = ["${emit('","'.join(data.keys()))}$"];

    var series = {name: "All",
                  children: cats.map(
                      function(attr) {
                        return {name: attr,
                                children: def_chk_comp.filter(
                                  function(d) { return d[attr];}
                                ).map(
                                  function(d) {
                                    return {name: d.checker, impact: d.impact, count: d[attr]};
                                  })
                               };
                      }
                  )
                 };

    make_chart(series);
'''
)

# Add new templates here.

#
# Templates end here.  The string "TEMPLATE_END" serves as a
# bookmark for users to find this section quickly.
#
###########################################################################

#===============================================================
# List of known formats, which can be used by command-line option handlers
available_formats = {}
for name,func in [x for x in globals().items() if x[0][:10] == 'render_as_']:
    k = name[10:]
    available_formats[k] = func
