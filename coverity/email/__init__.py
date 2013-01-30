import sys
import re

# Pull in the standard Coverity WS module
from coverity import ws

# The templates to be used for the email
from coverity import templates
from coverity.templates import render_subject, render_intro

###########################################################
# Some helper classes

class ConsoleReporter(ws.DefectReporter):
    '''
    Helper class to build a report for the console
    '''
    intro = 'The following defects were found'
    
    def recipients(self, md):
        '''
        Always return "console" since we're producing just one report.
        '''
        return ['console']

class MetricsReporter(ws.MetricsReporter):
    '''
    Helper class to build a metrics report for the console
    '''
    def recipients(self, md):
        '''
        Always return "console" since we're producing just one report.
        '''
        return ['console']

class ComponentMetricsReporter(ws.ComponentMetricsReporter):
    '''
    Helper class to build a metrics report for the console
    '''
    def recipients(self, md):
        '''
        Always return "console" since we're producing just one report.
        '''
        return ['console']

class SubscriberReporter(ws.DefectReporter):
    '''
    Helper class to build a report for component subscribers
    '''
    intro = 'The following defects were found in your subscribed components'
    
    def __init__(self, client):
        ws.DefectReporter.__init__(self, client)
        self._comp_subs = {}

    def recipients(self, md):
        '''
        Get a list of the users that subscribe to the component which contains
        defect "md".
        '''
        # Try the component cache first
        try:
            componentDO = self._comp_subs[md.componentName]
        except KeyError:
            compFilter = self._client.config.getDO('componentIdDataObj', name = md.componentName)
            self._comp_subs[md.componentName] = self._client.config.getComponent(compFilter)
            componentDO = self._comp_subs[md.componentName]
            
        try:
            return componentDO.subscribers
        except:
            # no subscribers
            pass

class OwnerReporter(ws.DefectReporter):
    '''
    Helper class to build a report to defect owners
    '''
    intro = 'The following defects were assigned to you'

    def defects(self, scope):
        '''
        Get list of defects matching established filters
        '''
        
        # Save any established cutoff date so we don't go too far back in
        # the history when collecting the recipients
        try:
            self._cutoff = scope.filters['firstDetectedStartDate']
        except KeyError:
            self._cutoff = None
  
        # Make a note of whether we want unassigned defects, to be used later
        self.allow_unassigned = scope.options.unassigned in ('include','only')

        if scope.options.unassigned == 'only':
            # If we only want unassigned defects, skip the standard
            # recipients code since it will only delay things.
            self.recipients = lambda m: None

        # Save the scope for when we call recipients() later
        self.scope = scope

        # Get the defects
        return ws.DefectReporter.defects(self, scope)

    def recipients(self, md):
        '''
        Get the most recent owner for defect "md", based on the defect history
        over the relevant time period.
        '''
        changes = self._client.defect.getMergedDefectHistory(md.cid, self.scope.triage_scope())
 
        # Walk through history in reverse order so we find the most
        # recent changes first
        for rec in reversed(changes):
            if self._cutoff is None or rec.dateModified > self._cutoff:
                try:
                    if rec.ownerChange:
                        if self.allow_unassigned or rec.ownerChange.newValue not in (None, 'Unassigned'):
                            if rec.ownerChange.newValue == 'Unassigned':
                                return [None]
                            return([rec.ownerChange.newValue])
                except:
                    pass

class MyOptionParser(object):
    '''
    Class to manage this script's command-line options.  We start with the
    common options from ws.WSOpts, and add a few specifically for
    this script.
    '''
    def __init__(self, reporters):
        self._p = ws.WSOpts().get_common_opts()

        # use --test flag to avoid sending e-mail while debugging this script
        self._p.set_defaults(testing = "false")
        self._p.set_defaults(raw = "false")
        self._p.set_defaults(quiet = "false")
    
        self._p.add_option("--test", action="store_true", dest="testing", help="Testing flag: no mail just echo to stdout")
        self._p.add_option("--dest", dest="reporter", default='subscribers', help="Send to whom? "+','.join(reporters.keys()))
        self._p.add_option("--unassigned-to", dest="unassigned_to", default=None, help="Send report of unassigned defects to this user")
        self._p.add_option("--format", dest="format", default='table', help="Report format (%s)"%(','.join(templates.available_formats.keys()),))
        self._p.add_option("--chart_field", dest="field", default='', help="Primary field for chart")
        self._p.add_option("--chart_stack_field", dest="stack_field", default='', help="Stacking field for chart")
        self._p.add_option("--title", dest="title", default=None, help="Title for chart")
        self._p.add_option("--raw", action='store_true', dest="raw", help="Exclude headers in CSV output")
        self._p.add_option("--quiet", action='store_true', dest="quiet", help="Exclude unnecessary script output.")

        # Make sure we validate options
        def validate_reporter(options, args):
            try:
                reporters[options.reporter]
            except KeyError:
                return ['Unknown "--dest" value ' + options.reporter]
        self._p.add_validator(validate_reporter)
        def validate_format(options, args):
            global render_email
            try:
                render_email = templates.available_formats[options.format]
            except KeyError:
                return ['Unknown "--format" value ' + options.format]
        self._p.add_validator(validate_format)
    
    def print_help(self):
        return self._p.print_help()

    def parse_args(self):
        (self.options, self.args) = self._p.parse_args()
        
    def defect_scope(self, client):
        return ws.OptionsProcessor(self.options, client)

###########################################################
#
# MAIN

def main():
    # Supported report types
    # Note that we don't instantiate the class yet--we need to have a
    # connection to CIM first.  We need to define this dict early, though,
    # so our OptionParser can validate the reporter option.
    reporters = {
        # Notify component subscribers
        'subscribers': SubscriberReporter,
        # Notify defect owners
        'owners': OwnerReporter,
        # Report everything to console
        'console': ConsoleReporter,
		# Metrics reports to console
		'metrics': MetricsReporter,
		# ComponentMetrics reports to console
		'compmetrics': ComponentMetricsReporter
    }

    # Process command line options so we know how to connect to CIM
    # and which defects to report.
    try:
        parser = MyOptionParser(reporters)
        parser.parse_args()
    except ws.WSOpts.ValidationError, e:
        sys.stderr.write(str(e)+'\n\n')
        parser.print_help()
        sys.exit(-1)

    # Open the base WS client services
    ws.client.connect(api_version=4, options=parser.options)

    # Process the defect filters
    scope = parser.defect_scope(ws.client)

    # Instantiate the reporters with the proper client
    for k,v in reporters.items():
        reporters[k] = v(ws.client)

    # Get the list of filtered defects
    reporter = reporters[parser.options.reporter]
    mergedDefectsPageDO = reporter.defects(scope)
	
    # If there is no "totalNumberOfRecords" attribute, then defects() didn't return a page
    # descriptor.  That means that it isn't a list of defects, but a list of metrics.
    try:
        recs = mergedDefectsPageDO.totalNumberOfRecords
        rec_l = mergedDefectsPageDO.mergedDefects
        def get_defect(mergedDefectDO, scope):
            try:
                return ws.DefectHandler(mergedDefectDO, projectId=scope.projectId, projectDOs=scope.projectDOs, scope = scope.triage_scope())
            except UnboundLocalError:
                return ws.DefectHandler(mergedDefectDO, scope = scope.triage_scope())
    except AttributeError:
        recs = len(mergedDefectsPageDO)
        rec_l = mergedDefectsPageDO
        def get_defect(mergedDefectDO, scope):
            return mergedDefectDO

    if not parser.options.quiet: sys.stderr.write("%d defects found.\n" % (recs,))
		
    # Group defects by recipient
    email_cid = {}
    if recs:
      for mergedDefectDO in rec_l:
        # Check whether there are recipients for this defect
        recipients = reporter.recipients(mergedDefectDO)
        if recipients is None and parser.options.unassigned_to:
            recipients = [None]
        if recipients:
            defect = get_defect(mergedDefectDO, scope)
            for user in recipients:
                try:
                    email_cid[user].add(defect)
                except:
                    email_cid[user] = set([defect])

    # Print useful info in script output
    if len(email_cid) == 0:
        if not parser.options.quiet: print "No relevant defects"
        sys.exit(0)

    # Finally, send the notifications
    try:
        console_reporter = reporter.recipients(1) == ['console']
    except:
        console_reporter = False

    if console_reporter:
        print render_email(options=parser.options, defects=email_cid['console'], intro=reporter.intro)
    else:
      for email in email_cid:
       if not parser.options.quiet:
        if email is None or email.lower() in ('none', 'unassigned'):
            sys.stderr.write("Unassigned defects ")
            sys.stderr.write(', '.join([str(x.cid) for x in email_cid[email]])+' ')
            if parser.options.unassigned_to:
                sys.stderr.write('will be sent to '+parser.options.unassigned_to+'\n')
            else:
                sys.stderr.write('will be ignored\n')
        else:
         sys.stderr.write(email+" will be notified about "+', '.join([str(x.cid) for x in email_cid[email]])+'\n')

      for user,defects in email_cid.items():
        # This controls whether the message talks about un"assign"ed or
        # un"subscrib"ed defects
        if parser.options.reporter == 'owners':
            relationship = 'assign'
        else:
            relationship = 'subscrib'
        subject = render_subject(user=user, options=parser.options, defects=defects, intro=reporter.intro, relationship=relationship)
        intro = render_intro(user=user, options=parser.options, defects=defects, intro=subject)
        if user in (None, 'Unassigned'):
            user = parser.options.unassigned_to

        body = render_email(options=parser.options, defects=defects, intro=intro)
        
        if parser.options.testing == True:
            print "***\n*** just testing\n***\n"
            print 'To:', user
            print 'Subject:', subject
            print '\n',body
        else:
          # We send the email using CIM's "notify" capability.  One downside to
          # that approach, is that CIM (as of 5.5.1) has a fixed format for
          # the message and we can't change the MIME headers.  We could theoretically
          # use Python's email support to have complete control over the message
          # format, but then we couldn't leverage CIM's user and mail settings.

          # Strip off any LDAP suffix that might be present, since the notify
          # method won't work with that.  The suffix is prefixed with '@'
          # or '['
          user = re.split('\s*[@\[]\s*',user)[0]

          # Send the email.  If AttributeError is raised, it likely
          # means that the admin client doesn't exist.  That only happens
          # for WS v4 (ie CIM 5.5.0+), where the notify method is part
          # of the config service.
          try:
            ws.client.admin.notify(user, subject, body)
          except AttributeError:
            ws.client.config.notify(user, subject, body)
            
    if not parser.options.quiet: sys.stderr.write("%d defects processed.\n" % (recs,))

# -----------------------------------------------------------------------------
if __name__ == '__main__':
    main()
