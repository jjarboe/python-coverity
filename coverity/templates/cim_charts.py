import itertools
import math
import sys
import re
import datetime
import suds

try:
    from collections import OrderedDict as odict
except:
    odict = dict

class DataPoint(object):
    def __init__(self, data, err=None):
        self.data = data
        self.err = err

class NumSeq(object):
    def __init__(self):
        self._l = []
    def next(self, id):
        self._l.append(id)
        return self._l.index(id)
    def remove(self, id):
        self._l.remove(id)

class DataSeries(object):
    _ctrgen = NumSeq()
    
    def __init__(self, name=None, *args):
        if name is None:
            self.name = 'series%d' % self._ctrgen.next(id(self))
        else:
            self.name = name

        self.v = []
        for a in args:
            try:
                self.v.append(DataPoint(*a))
            except TypeError:
                self.v.append(DataPoint(a))

    def length(self):
        return len(self.v)

    def data(self):
        return [x.data for x in self.v]

    def err(self):
        v = filter(None, [x.err for x in self.v])
        if v: return v

def dict_to_series(d):
    series = odict()
    for k,v in d.items():
        try:
            series[k] = DataSeries(k, *v)
        except TypeError:
            series[k] = DataSeries(k, v)
    return series

def defect_counts(defects, group_by, then_by = None):
    ret = {}
    counts = {}
    for d in defects:
        group = getattr(d, group_by)
        if group not in ret:
            ret[group] = {}
            counts[group] = 1
        else:
            counts[group] += 1
        if then_by:
          tgroup = getattr(d, then_by)
        else:
          tgroup = 'Defects'
          
        if tgroup not in ret[group]:
            ret[group][tgroup] = 1
        else:
            ret[group][tgroup] += 1

    cats = [x[0] for x in sorted(counts.items(), key=lambda x:x[1], reverse=True)]

    subs = set()
    for k,v in ret.items():
        for vv in v.keys():
            subs.add(vv)
        
    t = ret.copy()
    ret = {}
    for s in subs:
        ret[s] = []
        for k in cats:
            ret[s].append(t[k].get(s,0))

    return dict_to_series(ret), cats

# Use the "templite" module for string formatting.  Pasted here to reduce the
# number of separate files required.  One change was made to the Templite+
# code: '.' was added to the Template.auto_emit re, so it will include object
# members as well as variable names.

##################################################################
#       Templite+
#       A light-weight, fully functional, general purpose templating engine
#
#       Copyright (c) 2009 joonis new media
#       Author: Thimo Kraemer <thimo.kraemer@joonis.de>
#
#       Based on Templite by Tomer Filiba
#       http://code.activestate.com/recipes/496702/
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#

class Templite(object):
    auto_emit = re.compile('(^[\'\"])|(^[a-zA-Z0-9._\[\]\'\"]+$)')
    
    def __init__(self, template, start='${', end='}$'):
        if len(start) != 2 or len(end) != 2:
            raise ValueError('each delimiter must be two characters long')
        delimiter = re.compile('%s(.*?)%s' % (re.escape(start), re.escape(end)), re.DOTALL)
        offset = 0
        tokens = []
        for i, part in enumerate(delimiter.split(template)):
            part = part.replace('\\'.join(list(start)), start)
            part = part.replace('\\'.join(list(end)), end)
            if i % 2 == 0:
                if not part: continue
                part = part.replace('\\', '\\\\').replace('"', '\\"')
                part = '\t' * offset + 'emit("""%s""")' % part
            else:
                part = part.rstrip()
                if not part: continue
                if part.lstrip().startswith(':'):
                    if not offset:
                        raise SyntaxError('no block statement to terminate: ${%s}$' % part)
                    offset -= 1
                    part = part.lstrip()[1:]
                    if not part.endswith(':'): continue
                elif self.auto_emit.match(part.lstrip()):
                    part = 'emit(%s)' % part.lstrip()
                lines = part.splitlines()
                margin = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
                part = '\n'.join('\t' * offset + l[margin:] for l in lines)
                if part.endswith(':'):
                    offset += 1
            tokens.append(part)
        if offset:
            raise SyntaxError('%i block statement(s) not terminated' % offset)
        self.__code = compile('\n'.join(tokens), '<templite %r>' % template[:20], 'exec')

    def render(self, __namespace=None, **kw):
        '''
        renders the template according to the given namespace. 
        __namespace - a dictionary serving as a namespace for evaluation
        **kw - keyword arguments which are added to the namespace
        '''
        namespace = {}
        if __namespace: namespace.update(__namespace)
        if kw: namespace.update(kw)
        namespace['emit'] = self.write
        
        __stdout = sys.stdout
        sys.stdout = self
        self.__output = []
        eval(self.__code, namespace)
        sys.stdout = __stdout
        return ''.join(self.__output)
    
    def write(self, *args):
        for a in args:
            self.__output.append(str(a))

# End of Templite.py code
#=========================================

class Template(Templite):
    '''
    Simple wrapper for Templite class which renders the template when
    called as a function.
    '''

    # Pull in some Coverity helper classes
    from coverity.ws import SourceFile, CheckerDescription, Component

    def __init__(self, template, factory=None, **kw):
        super(Template, self).__init__(template, **kw)
        # factory can be used to post-process the template text
        self._factory = factory

    def __call__(self, __namespace=None, **kw):
        # Map in our local helpers
        d = {
        'SourceFile': self.SourceFile,
        'CheckerDescription': self.CheckerDescription,
        'Component': self.Component,
        'defect_counts': defect_counts,
        }
        d.update(kw)
        t = self.render(__namespace, **d)
        if self._factory:
            t = self._factory(t)
        return t

class ChartTemplate(Template):
    _template = '''
<!DOCTYPE html>
<html>
  <head>
    <title>Defects</title>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.layout.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.time.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.csv.js?1.29.1"></script>
    <style type="text/css">

svg {
  width: 1024px;
  height: 1000px;
  border: solid 1px #ccc;
  font: 10px sans-serif;
  shape-rendering: crispEdges;
}

    </style>
  </head>
  <body>
    ##@@##BODY@@##@@
    <script type="text/javascript">

var w = 1024,
    h = 1000,
    p = [20, 50, 400, 20],
    x = d3.scale.ordinal().rangeRoundBands([0, w - p[1] - p[3]]),
    x2 = d3.scale.ordinal().rangeRoundBands([0, w - p[1] - p[3]]),
    y = d3.scale.linear().range([0, h - p[0] - p[2]]),
	y2 = d3.scale.linear().range([0, h - p[0] - p[2]]),
	y_l = d3.scale.log().range([0, h - p[0] - p[2]]),
	z = d3.scale.category20(),
	identity = function(x) { return x; };

var svg = d3.select("body").append("svg:svg")
    .attr("width", w)
    .attr("height", h)
  .append("svg:g")
    .attr("transform", "translate(" + p[3] + " " + (h - p[2]) + ")");

var gradient = svg.append("svg:defs")
  .append("svg:linearGradient")
	.attr("id", "gradient")
	.attr("x1", "0%")
	.attr("y1", "0%")
	.attr("x2", "100%")
	.attr("y2", "100%")
	.attr("spreadMethod", "pad");
gradient.append("svg:stop")
	.attr("offset", "0%")
	.attr("stop-color", "#fff")
	.attr("stop-opacity", 0);
gradient.append("svg:stop")
	.attr("offset", "100%")
	.attr("stop-color", "#fff")
	.attr("stop-opacity", 0.7);

function GraphSpec(xaxis, yaxis, ymap, format_x, zaxis) {
	if (yaxis === undefined) yaxis = y;
	this.yaxis = yaxis;
    this.height = function(d) { return yaxis(d.y); };

	if (ymap === undefined) ymap = function(d) { return -yaxis(d.y); };	
	this.ymap = ymap;
	
	if (zaxis == undefined) zaxis = z;
	this.zaxis = z;
	
	if (xaxis === undefined) xaxis = x;
	this.xaxis = xaxis;
	
	if (format_x === undefined) format_x = identity;
	this.format_x = format_x;

	this.tip = undefined;
	
	try {
		zaxis(1);
		this.fill_func = function(d, i) { return zaxis(i); };
	} catch (err) {
		if (err instanceof TypeError) {
			var clr = zaxis;
		    zaxis = function() { return clr; };
		    this.fill_func = zaxis;
			this.zaxis = zaxis;
		} else {
			throw err;
		}
	}
    this.stroke_func = function(d, i) { return d3.rgb(zaxis(i)).darker(); };
	
	this.rect = identity;
}

function Label(parse_f, format_f) {
    if (parse_f === undefined) parse_f = identity;
	this.parse = parse_f;
	
	if (format_f === undefined) format_f = identity;
	this.format = format_f;
}

function do_graph(series, gs) {
  var idx = 0;
  function next_idx() { return idx++; }
  
  // Add a group for each series.
  var serie = svg.selectAll("g.cause")
      .data(series, next_idx)
    .enter().append("svg:g")
      .attr("class", "cause")
      .style("fill", gs.fill_func)
      .style("stroke", gs.stroke_func)
	  ;

  // Add a rect for each date.
  var rect = serie.selectAll("rect")
      .data(Object, next_idx)
    .enter().append("svg:rect")
      .attr("x", function(d) { return gs.xaxis(d.x); })
      .attr("y", gs.ymap)
      .attr("height", gs.height)
      .attr("width", /*gs.width*/ gs.xaxis.rangeBand())
	  ;
  rect = gs.rect(rect);
  
  // Include tooltip with data details
  rect.append("title").text(gs.tip);
}

function do_axes(gs) {
  // Add a label per date.
  var label = svg.selectAll("text")
      .data(gs.xaxis.domain())
    .enter().append("svg:text")
      .attr("text-anchor", "top")
      .attr("dy", ".71em")
	  .attr("transform", function(d) { return "rotate(90 0 0) translate(2 -"+(gs.xaxis(d)+gs.xaxis.rangeBand())+")"; })
      .text(gs.format_x);

  // Add y-axis rules.
  var rule = svg.selectAll("g.rule")
      .data(gs.yaxis.ticks(5))
    .enter().append("svg:g")
      .attr("class", "rule")
      .attr("transform", function(d) { return "translate(0," + -gs.yaxis(d) + ")"; });

  rule.append("svg:line")
      .attr("x2", w - p[1] - p[3])
      .style("stroke", function(d) { return d ? "#ccc" : "#000"; })
      .style("stroke-opacity", function(d) { return d ? .7 : null; });

  rule.append("svg:text")
      .attr("x", w - p[1] - p[3] + 6)
      .attr("dy", ".35em")
      .text(d3.format(",d"));
}

function stacked_bars(data, x_attr, y_attr, x_label, colors) {
  if (x_label === undefined) x_label = new Label();
  
  // Transpose the data into layers
  var series = d3.layout.stack()(y_attr.map(function(attr) {
    return data.map(function(d) {
      return {x: x_label.parse(d[x_attr]), y: d[attr], attr: attr};
    });
  }));
  
  // Compute the x-domain (by date) and y-domain (by top).
  x.domain(series[0].map(function(d) { return d.x; }));
  y.domain([
        0,
        d3.max(series[series.length - 1], function(d) { return d.y0 + d.y; })
  ]);
  gs = new GraphSpec(x, y, function(d) { return -y(d.y+d.y0)}, x_label.format, colors);
  gs.tip = function(d) { return d.x + ': ' + d.y + ' '+d.attr; };

  do_graph(series, gs);
  do_axes(gs);
}

function bars(data, x_attr, y_attr, x_label, log) {
  if (x_label === undefined) x_label = new Label();

  var series = Array( data.map(function(d) {
    var y = 0;
	for (i in y_attr) {
		y = y + d[y_attr[i]];
	}
	return { x: x_label.parse(d[x_attr]), y: y, attr: 'Defects' };
  }) );
  var y_axis = log ? y_l : y;
  
  // Compute the x-domain (by date) and y-domain (by top).
  var d = series[0].map(function(d) { return d.x; });
  x.domain(d);
  y_axis.domain([
        0.5,
        d3.max(series[0], function(d) { return d.y; })
  ]);
  
  gs = new GraphSpec(x, y_axis, undefined, x_label.format);
  gs.tip = function(d) { return d.x + ': ' + d.y + ' '+d.attr; };

  do_graph(series, gs);
  do_axes(gs);
}

function bars_with_proportions(data, x_attr, y_attr, x_label, colors) {
  if (x_label === undefined) x_label = new Label();
  var max_y = 0;
  
  var series = new Array( data.map(function(d) {
    var y = 0.0;
	for (i in y_attr) {
		y = y + d[y_attr[i]];
	}
	if (y > max_y) max_y = y;
	return { x: x_label.parse(d[x_attr]), y: y, attr: 'Defects' };
  }) );

  var y_axis = y_l;
  
  x.domain(series[0].map(function(d) { return d.x; }));
  x2.domain(series[0].map(function(d) { return d.x; }));
  
  // Transpose the data into layers
  var areas = d3.layout.stack()/*.offset("expand")*/(y_attr.map(function(attr) {
    return data.map(function(d) {
      var total = d3.sum(d3.values(d), function(rec) {if (typeof rec == typeof 1) return rec;});
      return {x: x_label.parse(d[x_attr]),
              y: d[attr]/total,
			  attr: attr,
			  total: total,
			  pct: total/max_y };
    });
  }));
  
  // Compute the x-domain and y-domain
  y_axis.domain([0.5, max_y]);
  y2.domain([0,1]);
  
  var gs2 = new GraphSpec(x2,
                         y2,
						 function(d) { return -y2((d.y+d.y0)*(y_axis(d.total)/y_axis(max_y)))-0.5; },
                         x_label.format,
						 colors);

  gs2.height = function(d) { return y2(d.y*y_axis(d.total)/y_axis(max_y));};
  gs2.tip = function(d) { return d.x+': '+d.y*d.total+' '+d.attr+" ("+ parseInt((d.y+0.005)*100) + '%)'; };
  
  var gs = new GraphSpec(x, y_axis, undefined, x_label.format, '#ffffff');
  gs.tip = function(d) { return d.x + ": " + d.y };
  gs.rect = function(r) {
	return r.attr("width", x.rangeBand()*0.3)
		.attr("opacity", 0.5)
		.style("stroke-opacity", 0)
		.style("fill", "url(#gradient)");
  };

  do_axes(gs);
  do_graph(areas, gs2);
  do_graph(series, gs);
}

window.onload = function() {
    ##@@##ONLOAD@@##@@
}
    </script>
  </body>
</html>
    '''

    def __init__(self, body, onload, **kw):
        '''
        The constructor takes markup for the body and the onload function.
        '''
        template = self._template.replace('##@@##BODY@@##@@', body).replace('##@@##ONLOAD@@##@@', onload)
        super(ChartTemplate, self).__init__(template, factory=None, **kw)

class MetricsChartTemplate(ChartTemplate):
    _template = '''
<!DOCTYPE html>
<html>
  <head>
    <title>Defects</title>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.layout.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.time.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.csv.js?1.29.1"></script>
    <style type="text/css">

svg { border: 0px; width: 900px; height: 400px; font: 8pt sans-serif;}
path { stroke: none; stroke-width: 2; fill: none; opacity: .5;}
line { stroke-width: 1; opacity: .7; }

rect.selected { stroke: none; fill: #ffff00; opacity: .5;}
rect { fill: white; opacity: 0;}
    </style>
  </head>
  <body>
    ##@@##BODY@@##@@
    <script type="text/javascript">

var w = 900,
    h = 400,
    p = [20, 20, 100, 20], // top, left, bottom, right padding
    x = d3.scale.ordinal().rangeBands([p[1], w - p[1] - p[3]]),
    y = d3.scale.linear().range([0, h - p[0] - p[2]]),
	z = d3.scale.category20()
    min_band_width = 4;

var svg = d3.select("body").append("svg:svg")
    .attr("width", w)
    .attr("height", h)
  .append("svg:g")
    .attr("transform", "translate(" + p[3] + " " + (h - p[2]) + ")");

function do_graph(series, x, y) {
  // Add lines for the series and attach to paths
  var line = d3.svg.line()
        .interpolate("basis")
        .x(function(d) {return x(d.x);})
        .y(function(d) {return -y(d.y);});
  
  svg.selectAll(".line")
      .data(series)
    .enter().append("svg:path")
	  .attr("class", function(d) { return d[0].type;} )
	  .attr("d", line)
      ;
}

function do_axes(series, x, y, series_names) {
  // Add x labels
  var dt_fmt = d3.time.format("%Y-%m-%d");
  var series_data = d3.zip.apply(d3, series);
  var xrule;

  // Functions to enable flyover highlighting of dates  
  var hover = function(d,i) {
    svg.select("#xrulerect"+i).attr("class","selected");
    xrule.attr("class", "xrule hl");
  };
  var hovclear = function(d,i) {
    svg.select("#xrulerect"+i).attr("class","");
    xrule.attr("class", "xrule");
  };
  // Capitalize the first letter of a string
  var cap1 = function(x) { return x[0].toUpperCase() + x.slice(1); }

  xrule = svg.selectAll("g.xrule")
      .data(x.domain(), String)
    .enter().append("svg:g")
      .attr("class", "xrule")
      .attr("transform", function(d) { return "translate("+(x(d)-x.rangeBand()/2)+" 0)"; })
      ;

  // Add a rect to use for highlighting, plus a title with details.
  xrule.append("svg:rect")
      .attr("width", x.rangeBand())
      .attr("height", h-p[0])
      .attr("y", -(h - p[0] - p[2]+5) )
      .attr("stroke", "black")
      .attr("opacity", .3)
      .attr("id", function(d,i) { return "xrulerect"+i; } )
      .on("mousemove", hover)
      .on("mouseout", hovclear)
    .append("title").text(function(d,i) {
        var data = series_data[i];
        var s = ["Defect activity", dt_fmt(d)+" ("+data[0].project+"):"];
        for (var v in data) {
            var ts = "";
            for (var j = 6-data[v].y.toString().length; j > 0; j--)
                ts = ts + " ";
            s.push(ts + data[v].y+" "+cap1(data[v].type));
        }
        return s.join("\\n");
    } );
  
  // Don't clutter the axis with excessive labels.  Only print the first
  // of each month, plus the last if it's not too close to the previous one.
  var last_month;
  var final_date = x.domain()[x.domain().length-1];
  var idx = 0;
  var t = xrule.append("svg:text")
      .attr("text-anchor", "begin")
      .attr("dx", "5")
	  .attr("transform", function(d) { return "rotate(90)"; })
      .text(function(d) {
            if (d.getMonth() != last_month) {
                last_month = d.getMonth();
                idx = 0;
                return dt_fmt(d);
            } else if (d == final_date && idx !== undefined && idx >= 3) {
                idx = 0;
                return dt_fmt(d);
            }
            idx++;
            } );

  // add y labels
  var rule = svg.selectAll("g.rule")
      .data(y.ticks(5), String)
    .enter().append("svg:g")
	  .attr("class", "rule")
      .attr("transform", function(d) { return "translate(0," + -y(d) + ")"; });
  rule.append("svg:line")
	  .attr("x1", p[1])
      .attr("x2", w - p[1] - p[3])
      .style("stroke", function(d) { return d ? "#ccc" : "#000"; })
      .style("stroke-opacity", function(d) { return d ? .7 : null; });
  rule.append("svg:text")
      .attr("text-anchor", "end")
	  .attr("x", p[1])
      .text(String)
	  ;
}

function line_chart(data, x_attr, y_attr) {
  var max_y = 0;

  // Translate the data to be more suitable for charting.  While
  // we're at it, keep track of the largest y-axis value.  
  var dt_fmt = d3.time.format("%Y-%m-%d %H:%M:%S");
  var series = (y_attr.map(function(attr) {
    return data.map(function(d) {
      var date = dt_fmt.parse(d[x_attr]);
      if (d[attr] > max_y) max_y = d[attr];
      return {x: date, y: d[attr], type: attr, project: d["project"]};
    });
  }));
  
  // Compute the x-domain (by date) and y-domain (by top).
  x.domain(series[0].map(function(d) { return d.x; }));
  y.domain([0,max_y]);
  
  // Expand our SVG element if the graph will be too congested.
  if (x.rangeBand() < min_band_width) {
     w = min_band_width * x.domain().length+p[1]+p[3]+p[1];
     var node = d3.select("svg");
     node.attr("width", w);
     node.style("width", w);
     x.rangeBands([p[1], w - p[1]-p[3]]);
  }
  do_graph(series, x, y);
  do_axes(series, x, y, y_attr);
}

window.onload = function() {
    ##@@##ONLOAD@@##@@
}
    </script>
  </body>
</html>
    '''

class CSVTemplate(Template):
    '''
    A wrapper for Template that outputs CSV data
    '''
    
    # This is our basic template
    _template = '''${if clean != True:}$
${intro}$

${:endif}$${if options.raw != True:}$${emit('"'+'","'.join(columns)+'"')}$
${:endif}$${for defect in defects:}$${emit(','.join([resolve(defect,field) for field in fields]))}$
${:end-for}$
'''
    _unquoted = False

    def __init__(self, *fields, **kw):
        '''
        The constructor takes a list of fields to include in the output.  Fields are specified as
        strings, which are taken as attributes of the individual defects.  Fields may be specified
        as a simple member, like "cid", or a member/method, like "firstDetected.strftime(...)".
        '''
        self._fields = fields
        if 'columns' in kw:
            self._columns = kw['columns']
            del kw['columns']
        else:
            self._columns = fields
        if 'clean' in kw:
            self._clean = True
            del kw['clean']
        else:
            self._clean = False
        if not fields:
            raise ValueError("You must specify a list of fields for the CSV output!")
        super(CSVTemplate, self).__init__(self._template, factory=None, **kw)

    def __call__(self, __namespace=None, **kw):
        def do_quote(x):
            '''
            Function to handle quoting of individual members.
            '''
            if type(x) in (int, long, float):
                # Numbers are returned without quotes
                return str(x)
            elif type(x) in (type(''),suds.sax.text.Text, datetime.datetime):
                # Things that will typically be treated as strings get double quotes
                return '"'+str(x)+'"'
            else:
                raise TypeError('Type %s not supported by %s' % (type(x), self.__class__.__name__))
        def res(obj, x):
            '''
            Function to handle resolving members and quoting appropriately.
            '''
            prefix = 'raise Exception("BAD EXPRESSION")'
            if x[0] == '!':
                field,rest = x[1:].split(' ',1)
                prefix = ''
            elif '.' in x:
                field,rest = x.split('.',1)
                prefix = 'v.'
            else:
                field = x
                rest = ''
            # Get the member value
            v = getattr(obj, field, '')
            if rest:
                # Apply method if specified
                try:
                    v = eval(prefix+rest, {}, {'v':v})
                except AttributeError, e:
                    raise Exception('ERROR with %s.%s'%(field,rest), obj.component, v, e)
            return self._unquoted and v or do_quote(v)
        return super(CSVTemplate, self).__call__(__namespace, fields=self._fields, columns=self._columns, resolve=res, clean=self._clean, **kw)

class XMLTemplate(CSVTemplate):
    '''
    A wrapper for Template that outputs XML data
    '''
    
    _unquoted = True

    # This is our basic template
    _template = '''${if options.raw != True:}$<?xml version="1.0" encoding="UTF-8"?>
${:endif}$${for defect in defects:
}$<cov:defect>${
for i in range(len(fields)):}$<${
columns[i]}$>${emit(resolve(defect,fields[i]))}$</${columns[i]}$>${
:end-for
}$</defect>
${:end-for}$'''

class CircleChartTemplate(ChartTemplate):
    _template = '''
<!DOCTYPE html>
<html>
  <head>
    <title>Defects</title>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.layout.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.time.js?1.29.1"></script>
    <script type="text/javascript" src="http://mbostock.github.com/d3/d3.csv.js?1.29.1"></script>
    
<style type="text/css">
svg {
  width: 1024px;
  height: 1024px;
  font: 8pt sans-serif;
}
circle { stroke-width: 0; fill-opacity: .4; fill: #880; }
.leaf circle { fill-opacity: .75; fill: blue; }
</style>
  </head>
  
  <body>
    ##@@##BODY@@##@@

<div id="chart"></div>
    <script type="text/javascript">

var r = 768,
    format = d3.format(",d");

var pack = d3.layout.pack()
    .size([r-4, r-4])
    .sort(d3.descending)
    .value(function(d) { return d.count; });

var vis = d3.select("#chart").append("svg:svg")
    .attr("width", r)
    .attr("height", r)
    .attr("class", "pack")
  .append("g")
    .attr("transform", "translate(2,2)");

function make_chart(data) {
  var node = vis.data([data]).selectAll("g.node")
      .data(pack.nodes)
    .enter().append("g")
      .attr("class", function(d) { 
        var c = [ "node" ];
        if (!d.children) c.push("leaf");
        if (d.impact) c.push(d.impact);
        return c.join(" "); 
      })
      .attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; })
      ;

  node.append("title")
      .text(function(d) {
        if (d.children) {
            return d.name + " (" + d.children.length + " types)";
        }
        return d.parent.name + " // " + d.name + ": " + format(d.count);
      })
      ;

  node.append("circle")
      .attr("r", function(d) { return d.r; })
      ;

  node.filter(function(d) { return !d.children; }).append("text")
      .attr("text-anchor", "middle")
      .attr("dy", ".3em")
      .text(function(d) { return d.name.substring(0, d.r / 3); })
      ;
}

window.onload = function() {
    ##@@##ONLOAD@@##@@
}
    </script>
	
  </body>
</html> 
    '''

