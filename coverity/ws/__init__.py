"""
A helper module to facilitate use of the Web Services provided
by Coverity Integrity Manager and Coverity Connect.

Typical usage will look something like this:

    # Process command line options so we know how to connect to the server
    # and which defects to report.
    try:
        (self.options, self.args) = WSOpts().get_common_opts().parse_args()
    except WSOpts.ValidationError, e:
        print str(e)+'\n'
        parser.print_help()
        sys.exit(-1)

    # Open the base WS client services
    ws.client.connect(api_version=5, options=parser.options)

Once connected, you can interact with the web services via
ws.client.config, ws.client.defect, and ws.client.admin

note that the admin service is only applicable to 5.0 through 5.4.1.

This module has been most extensively used with CIM v5.5.1 and v6.5.1.
Other versions can likely be made to work, but might require some changes.
That is especially true of the helper classes like the Reporter, Handler,
Processor, and so forth.
"""

import os, urllib, datetime, zlib, sys
from base64 import standard_b64decode
from optparse import OptionParser

# -----------------------------------------------------------------------------
# Base class for all the web service clients
class CoverityWebServiceClient(object):
    '''
    Base class for accessing Web Services in Coverity Integrity Manager.
    '''
    from suds.wsse import Security, UsernameToken
    from suds.client import Client

    def __init__(self,
        webservice_type = None,
        host = None,
        port = None,
        user = None,
        password = None,
        secure = False,
        api_version = 2,
        options = None
        ):
        if options:
            for var in ('host', 'port', 'user', 'password'):
                exec (var + ' = getattr(options, var)')
            if options.secure:
                v = options.secure
                v = v[0].upper() + v[1:]
                secure = eval(v)

        if secure: proto = 'https'
        else: proto = 'http'

        try:
            self.url = proto + '://' + host + ':' + port
        except:
            print proto, host, port
            raise

        if webservice_type not in ('administration','configuration','defect'):
            raise ValueError('Invalid webservice_type: '+webservice_type)

        api_version = int(api_version)
        
        # The v4 API doesn't include the admin service
        if webservice_type in ('administration',) and api_version >= 4:
            raise ValueError('Invalid service type "%s" for API version %d'
                % (webservice_type, api_version))

        self.wsdlFile = (self.url
            + '/ws/v'
            + str(api_version)
            + '/'
            + webservice_type
            + 'service?wsdl'
            )

        try:
            self.client = self.Client(self.wsdlFile)
        except:
            print self.wsdlFile
            raise
        self.security = self.Security()
        self.token = self.UsernameToken(user, password)
        self.security.tokens.append(self.token)
        self.client.set_options(wsse=self.security)

        if webservice_type != 'configuration':
           self.pageSpecDO = self.getDO(
               'pageSpecDataObj',
               pageSize = 1000,
               sortAscending = False,
               startIndex = 0,
               )

    def getwsdl(self):
        print(self.client)

    def create_url(self,
        cid,
        project_id,
        streamId = None,
        defectInstance = None,
        fileInstance = None
        ):
        '''
        Get a URL that will pull up the specified CID in the specified
        project_id.  You can specify a streamId and/or defectInstance if
        desired.
        '''
        if not project_id and cid:
           print "CID must have project_id with it!"
           return ''
        url = self.url + "/sourcebrowser.htm?"
        
        params = [('projectId', str(project_id))]

        if streamId:
          params.append(("streamDefectId", streamId))
        if defectInstance:
          params.append(("defectInstanceId", defectInstance))
        if fileInstance:
          params.append(("fileInstanceId", fileInstance))

        params.append(("mergedDefectId", str(cid)))

        url += urllib.urlencode(params)

        return url

    def __getattr__(self, name):
        '''
        Simplify access to the WS methods
        '''
        if name == 'factory':
            return self.client.factory
        return getattr(self.client.service, name)

    def getDO(self, DO_type, **kw):
        '''
        Get a particular type of data object, and prefill attributes
        if desired.
        '''
        obj = self.factory.create(DO_type)
        for (k,v) in kw.items():
            setattr(obj, k, v)
        return obj
        
class CoverityConfigServiceClient(CoverityWebServiceClient):
    '''
    A client to access the configuration service
    '''
    def __init__(self, *args, **kw):
        a = kw.copy()
        a.update({'webservice_type': 'configuration'})
        CoverityWebServiceClient.__init__(self, *args, **a)

class CoverityAdminServiceClient(CoverityWebServiceClient):
    '''
    A client to access the administration service
    '''
    def __init__(self, *args, **kw):
        a = kw.copy()
        a.update({'webservice_type': 'administration'})
        CoverityWebServiceClient.__init__(self, *args, **a)

class CoverityDefectServiceClient(CoverityWebServiceClient):
    '''
    A client to access the defect service
    '''
    def __init__(self, *args, **kw):
        a = kw.copy()
        a.update({'webservice_type': 'defect'})
        CoverityWebServiceClient.__init__(self, *args, **a)

class CoverityServiceClient(object):
    def connect(self, *args, **kw):
        if 'api_version' not in kw:
            kw['api_version'] = 2
        # The admin service doesn't exist after v3
        if kw['api_version'] < 4:
            self.admin = CoverityAdminServiceClient(*args, **kw)
        self.defect = CoverityDefectServiceClient(*args, **kw)
        self.config = CoverityConfigServiceClient(*args, **kw)
    
client = CoverityServiceClient()

# common options to all the scripts
class WSOpts:
   '''
   Common command-line option support for CIM access
   '''
   class ValidationError(Exception):
       '''
       An exception indicating invalid options were used
       '''
       def __init__(self, errors):
           self.errors = errors
       def __str__(self):
           return 'ValidationError:\n  '+'\n  '.join(self.errors)

   class WSOptionParser(OptionParser):
       '''
       An option parser which handles the common options and validation.  The
       add_validator() method allows you to augment the validation.  Handles
       all common optparse.OptionParser methods as well.
       '''
       _required_opts = ('user', 'password', 'host', 'port')
       _unassigned_choices = ('none', 'include', 'only')
       _snapshot_op_choices = ('new', 'fixed')

       def __init__(self, *a, **kw):
           OptionParser.__init__(self, *a, **kw)
           self._validators = []
           
       def parse_args(self):
           '''
           Parse arguments just like optparse.OptionParser, then validate them
           via validate_args().
           '''
           options, args = OptionParser.parse_args(self)
           self.validate_args(options, args)
           return options, args
           
       def add_validator(self, func):
           '''
           Add a function to validate options/arguments.
           '''
           self._validators.append(func)
               
       def validate_args(self, options, args):
           '''
           Validate the options/arguments.  Raise WSOpts.ValidationError
           on failure.
           '''
           errors = []
           missing = []
           for needed in self._required_opts:
               if not getattr(options, needed):
                   missing.append(needed)
                    
           if missing:
               errors.append('MISSING: '+', '.join(missing))

           for func in self._validators:
               err = func(options, args)
               if err: errors.extend(err)
                
           if errors:
               raise WSOpts.ValidationError(errors)
            
   def __init__(self):
    self.parser = self.WSOptionParser()
    def validate_unassigned(options, args):
          if options.unassigned not in self.parser._unassigned_choices:
            return ['Unknown "--unassigned" value ' + options.unassigned]
    self.parser.add_validator(validate_unassigned)
    def validate_snapshot_op(options, args):
          if options.snapshot_op not in self.parser._snapshot_op_choices:
            return ['Unknown "--snapshot-op" value ' + options.snapshot_op]
    self.parser.add_validator(validate_snapshot_op)
 
   def response_file(self, option, opt_str, value, parser):
    rfile = file(value,'r').read().split()
    parser.rargs.extend(rfile)

   def get_common_opts(self):
    '''
    Returns a WSOptionParser instance which is preconfigured for the common
    options.
    '''
    self.parser.add_option("--response-file","-r", action="callback",
        callback=self.response_file, type="string",
        help="arguments read from this file");

    self.parser.set_defaults(host="localhost")
    self.parser.set_defaults(user="admin")
    self.parser.set_defaults(port="8080")
    self.parser.set_defaults(secure="false")
    self.parser.set_defaults(password=os.getenv("COVERITY_PASSPHRASE"))
    self.parser.set_defaults(unassigned="none")
    self.parser.set_defaults(status="all")
    self.parser.set_defaults(severity="all")
    self.parser.set_defaults(classification="all")
    self.parser.set_defaults(days="0")
    self.parser.set_defaults(snapshot_op="new")
    self.parser.set_defaults(component="all")
    self.parser.set_defaults(excludeComponents=False)

    self.parser.add_option("--host", dest="host", help="host of CIM")
    self.parser.add_option("--port",  dest="port", help="port of CIM")
    self.parser.add_option("--secure",  dest="secure",  action="store_true",
        help="specify for https/SSL server")
    self.parser.add_option("--user",  dest="user", help="CIM user")
    self.parser.add_option("--password",  dest="password",
        help="CIM password")
    self.parser.add_option("--project",  dest="project",  help="project name")
    self.parser.add_option("--stream",  dest="stream",  help="stream name")
    self.parser.add_option("--snapshot",  type=int, dest="snapshot",
        help="snapshot name")
    self.parser.add_option("--snapshot-op",  dest="snapshot_op",
        default='new', help='What to look for in snapshot ("%s")'%
                            '","'.join(self.parser._snapshot_op_choices))

    self.parser.add_option("--unassigned", dest="unassigned",
        help='Include unassigned defects ("%s")'%
                            '","'.join(self.parser._unassigned_choices))
    self.parser.add_option("--status", dest="status", default='all',
        help='Statuses to include (comma-separated, or "all")')
    self.parser.add_option("--severity", dest="severity", default='all',
        help='Severities to include (comma-separated, or "all")')
    self.parser.add_option("--classification", dest="classification", default='all',
        help='Classifications to include (comma-separated, or "all")')
    self.parser.add_option("--days", dest="days", type=int, default=0,
        help="Limit to last <n> days (default 0==no limit)")
    self.parser.add_option("--component", dest="component", default='all',
        help='Components to include (comma-separated, or "all")')
    self.parser.add_option("--excludeComponents", action='store_true', dest="componentExclude",
        default=False, help='Exclude components listed in --component')

    return self.parser

# Start of helper classes that may be more closely tied to the version of
# CIM/CC in use.

class DefectReporter(object):
    '''
    Helper class to build a report of defects. This class is not intended to
    be used directly.  Rather, you should derive a class and flesh out the
    defects() and recipients() methods.
    '''
    intro = 'The following defects were found'

    def __init__(self, client):
        self._client = client

    def defects(self, scope):
        '''
        Get list of defects matching established filters from scope.  If
        there are lots of defects, make sure we properly handle
        multiple pages of results from the server.
        '''
        streamIdDOs = scope.streamIdDOs
        kw = scope.filters

        # Set up our filters
        mergedDefectFilterDO = self._client.defect.getDO(
            'mergedDefectFilterSpecDataObj',
            **kw)
        # Set up a page specifier
        ps = self._client.defect.getDO('pageSpecDataObj',
            pageSize = 2500,
            sortAscending = False,
            startIndex = 0)

        # Walk over the results pages to collect a single list
        mergedDefectsPageDO = self._client.defect.getDO('mergedDefectsPageDataObj',
            totalNumberOfRecords = 0,
            mergedDefects = [])
        while True:
            # Get next page
            ddo = self._client.defect.getMergedDefectsForStreams(
                streamIdDOs,
                mergedDefectFilterDO,
                ps)
            try:
                mergedDefectsPageDO.totalNumberOfRecords += len(ddo.mergedDefects)
                mergedDefectsPageDO.mergedDefects.extend(ddo.mergedDefects)
                ps.startIndex += len(ddo.mergedDefects)
            except AttributeError:
                break
        
        # TODO: Consider calling self._client.defect.getStreamDefects()
        # for the defects, in batches of 100, so we don't need to pull 
        # them up individually.  The DefectHandler class below will
        # fill in those fields on demand, but it would be faster if we
        # grabbed them in batches.
        
        return mergedDefectsPageDO
            
    def recipients(self, md):
        '''
        Returns a list of users relevant to this DefectReporter.  Returns nothing;
        to return a useful list, derive a child class and override this method.
        '''
        pass

class MetricsReporter(object):
    '''
    Helper class to build a report of defect metrics. This class is not intended to
    be used directly.  Rather, you should derive a class and flesh out the
    defects() and recipients() methods.
    '''
    intro = 'The following defects were found'

    def __init__(self, client):
        self._client = client

    def defects(self, scope):
        '''
        Get list of defect metrics matching established filters from scope.
        '''
        streamIdDOs = scope.streamIdDOs
        kw = scope.filters

        # Set up our filters
        projectIdDO = self._client.defect.getDO(
            'projectIdDataObj',
			name = scope.options.project
            )
        projectTrendRecordFilterSpecDO = self._client.defect.getDO(
            'projectTrendRecordFilterSpecDataObj')
        if 'firstDetectedStartDate' in kw:
            projectTrendRecordFilterSpecDO.startDate = kw['firstDetectedStartDate']
            
        # Get metrics
        metricsDO = self._client.defect.getTrendRecordsForProject(projectIdDO, projectTrendRecordFilterSpecDO)
        
        return metricsDO
            
    def recipients(self, md):
        '''
        Returns a list of users relevant to this MetricReporter.  Returns nothing;
        to return a useful list, derive a child class and override this method.
        '''
        pass

class ComponentMetricsReporter(MetricsReporter):
    def defects(self, scope):
        '''
        Get list of defect metrics matching established filters from scope.
        '''
        streamIdDOs = scope.streamIdDOs
        kw = scope.filters

        # Set up our filters
        projectIdDO = self._client.defect.getDO(
            'projectIdDataObj',
			name = scope.options.project
            )

        # Get metrics
        try:
            metricsDO = self._client.defect.getComponentMetricsForProject(projectIdDO, scope.filters['componentIdList'])
        except KeyError:
            metricsDO = self._client.defect.getComponentMetricsForProject(projectIdDO)
        
        return metricsDO
            

class OptionsProcessor(object):
    '''
    Class to handle common command-line options and prepare appropriate
    filters for getMergedDefectsForStream().
    '''
    class StreamNotFound(Exception): pass

    class TooManyObjects(Exception):
        def __init__(self, type, values):
            self._type = type
            self._values = values
        def __str__(self):
            return '%s: %s %s' % (
                self.__class__.__name__, self._type, self._values)

    def __init__(self, options, client):
        self._triage_scope = None
        self.projectId = None
        self.projectDOs = None
        self.filters = {}
        self.options = options
        self.streamIdDOs = []
        self.client = client

        # Apply status filters if relevant
        if self.options.status.lower() in ('open', 'Outstanding'):
            self.filters['statusNameList'] = ['New', 'Triaged']
        elif self.options.status.lower() in ('*','all'):
            pass
        else:
            self.filters['statusNameList'] = self.options.status.split(',')
        
        # Apply severity filters if relevant
        if self.options.component.lower() not in ('*','all'):
            self.filters['componentIdList'] = [client.defect.getDO('componentIdDataObj', name=x) for x in self.options.component.split(',')]
        self.filters['componentIdExclude'] = self.options.excludeComponents
        
        # Apply severity filters if relevant
        if self.options.severity.lower() not in ('*','all'):
            self.filters['severityNameList'] = self.options.severity.split(',')
        
        # Apply classification filters if relevant
        if self.options.classification.lower() not in ('*','all'):
            self.filters['classificationNameList'] = self.options.classification.split(',')
        
        # get the streams for relevant project or all streams if no project
        # given
        if self.options.stream:
            sid = client.config.getStreams(
                client.config.getDO('streamFilterSpecDataObj',
                    namePattern=self.options.stream)
                )
            if not sid:
                raise self.StreamNotFound(self.options.stream)
            else:
                self.streamIdDOs.extend([x.id for x in sid])
                # Also prepare the projectId and projectDOs, so we can map
                # to URLs
                p = set([x.primaryProjectId for x in sid])
                if len(p) != 1:
                    raise self.TooManyObjects('Projects', p)
                projectName = [x.name for x in p][0]
                self.projectDOs = client.config.getProjects(
                    client.config.getDO('projectFilterSpecDataObj',
                        namePattern=projectName)
                    )
                if len(self.projectDOs) != 1:
                    raise TooManyObjects('Projects', self.projectDOs)
                self.projectId = self.projectDOs[0].projectKey
        else:
            projectFilterSpecDO = client.config.getDO(
                'projectFilterSpecDataObj',
                namePattern = self.options.project)
            self.projectDOs = client.config.getProjects(projectFilterSpecDO)
            if len(self.projectDOs) == 1:
                self.projectId = self.projectDOs[0].projectKey
            else:
                self.projectId = None

            for project in self.projectDOs:
                # If there are no streams, skip the project
                try: project.streams
                except AttributeError: continue

                # Add streams in the project to the stream list
                try:
                    addl = [s.id for s in project.streams
                            if s.id.type != 'SOURCE']
                except AttributeError:
                    # The v4 API doesn't have "SOURCE" streams
                    addl = [s.id for s in project.streams]
                self.streamIdDOs.extend(addl)

        # Refine filters, if appropriate
        if self.options.snapshot:
            # Look for a specific snapshot
            ssid = client.config.getDO('snapshotIdDataObj',
                id=long(self.options.snapshot))
            ss = client.config.getSnapshotInformation([ssid])
            if ss:
                f = client.defect.getDO('streamSnapshotFilterSpecDataObj',
                    snapshotIdIncludeList=[ssid])
                mf = client.defect.getDO('mergedDefectFilterSpecDataObj',
                    streamSnapshotFilterSpecIncludeList=f)
                streams = []
                p = client.defect.getDO('pageSpecDataObj',
                    pageSize = 1, sortAscending = False, startIndex = 0)
                # Walk through the streams to see which include this snapshot
                if self.streamIdDOs: lstr = self.streamIdDOs
                else: lstr = [x.id for x in client.config.getStreams()]
                for s in lstr:
                    # Look for merged defects in this stream that come
                    # from the desired snapshot
                    f.streamId = s
                    d = client.defect.getMergedDefectsForStreams([s], mf, p)
                    if d.totalNumberOfRecords or len(lstr) == 1:
                        streams.append(s)
                if len(streams) != 1:
                    raise self.TooManyObjects('Streams', streams)
                # Find the previous snapshot so we can determine what is new
                prev_ss = client.config.getSnapshotsForStream(streams[0],
                    client.config.getDO('snapshotFilterSpecDataObj',
                        endDate=ss[0].dateCreated
                            + datetime.timedelta(seconds=1))
                    )
                # If we're looking for new defects (snapshot_op=='new'),
                # then include ssid and exclude the previous.
                # If we're looking for fixed defects (=='fixed')
                # then include the previous and exclude ssid
                # If there is no previous, the just include ssid
                if len(prev_ss) > 1:
                  if self.options.snapshot_op == 'new':
                    f.snapshotIdExcludeList = [prev_ss[-2]]
                  else:
                    f.snapshotIdIncludeList = [prev_ss[-2]]
                    f.snapshotIdExcludeList = [ssid]
                    
                # Finally, set our global filter to use the right stream
                f.streamId = streams
                
                self.filters['streamSnapshotFilterSpecIncludeList'] = f
        elif self.options.days:
            # Look for defects detected in the past <x> days
            self.filters['firstDetectedStartDate'] = (
                datetime.datetime.today()
                -datetime.timedelta(self.options.days)
                )

        # Set up the owner/user filters
        users = []
        if not self.options.unassigned == 'only':
            ps = client.config.getDO('pageSpecDataObj',
                pageSize=500,sortAscending=False,startIndex=0)
            while True:
              try:
                userPageDO = client.admin.getAssignableUsers(ps)
              except AttributeError:
                # v4 WS API doesn't have an admin service
                userPageDO = client.config.getUsers(
                    client.config.getDO('userFilterSpecDataObj',
                        assignable=True), ps)

              try:
                users.extend([u.username for u in userPageDO.users])
              except AttributeError:
                break
              ps.startIndex += len(userPageDO.users)

        if self.options.unassigned in ('include', 'only'):
            users = list(set(users + ['Unassigned']))
            
        if users:
            self.filters['ownerNameList'] = users

    def triage_scope(self):
        if not self._triage_scope:
            project = '*'
            if len(self.projectDOs) == 1:
                project = self.projectDOs[0].id.name
            stream = '*'
            if self.streamIdDOs and len(self.streamIdDOs) == 1:
                stream = self.streamIdDOs[0].name

            self._triage_scope = '/'.join([project, stream])
        return self._triage_scope

_cache ={}

class CachedCoverityObject(object):
    def _cache_key(self, v):
        return v

    def __init__(self, v):
        if self._cache_class not in _cache.keys():
            _cache[self._cache_class] = {}
        key = self._cache_key(v)
        if key not in _cache[self._cache_class]:
            _cache[self._cache_class][key] = self._get_object(v)
        self._props = _cache[self._cache_class][key]

    def __getattr__(self, name):
        return getattr(self._props, name)

class Component(CachedCoverityObject):
    '''
    Helper class for a component
    '''
    _cache_class = 'components'
    
    def _get_object(self,v):
        map,comp = v.split('.')
        m = client.config.getComponentMaps(client.config.getDO('componentMapFilterSpecDataObj', namePattern=map))
        class ComponentInfo(object):
            def __init__(self):
                self.componentPathRules = []
                self.components = []
                self.defectRules = []
        ret = ComponentInfo()
        for i in m:
            ret.componentPathRules.extend([x for x in i.componentPathRules if x.componentId.name==v])
            ret.components.extend([x for x in i.components if x.componentId.name==v])
            ret.defectRules.extend([x for x in i.defectRules if x.componentId.name==v])
        return ret
    
class DefectHandler(object):
    '''
    Helper class to facilitate template formatting of a defect from CIM.
    '''
    # Fields that are available in a streamDefectDataObj but not a
    # mergedDefectDataObj.  If a user tries to access those fields and
    # they don't exist, then we'll try to populate them.
    _streamDefectFields = (
        'defectInstances',
        'history',
        'streamId',
        'checkerSubcategoryId'
        )

    def __init__(self,
                 mergedDefectDO,
                 projectId = None,
                 projectDOs = None,
                 streamDefectDO = None,
                 scope = None
        ):
        '''
        We wrap around a mergedDefectDataObject
        '''
        self.defectDO = mergedDefectDO
        if projectId:
            self._projId = str(projectId)
        if projectDOs:
            self._projectDOs = projectDOs

        # Allow us to populate the streamDefectDataObj fields if
        # necessary
        self._triage_scope = scope
        
        if streamDefectDO:
            # Populate the streamDefectDataObj fields
            self.getStreamDefect(streamDefectDO=streamDefectDO, scope=scope)

    def __getattr__(self, name):
        '''
        Redirect unknown attribute lookups to the underlying
        mergedDefectDataObject
        '''
        # If we're failing to access streamDefectDataObj members, then
        # we need to call self.getStreamDefect()
        if name in self._streamDefectFields:
            self.getStreamDefect()
            return getattr(self, name)
        try:
            return getattr(self.defectDO, name)
        except AttributeError:
            raise

    def __str__(self):
        return '%s @ %s' % (self.cid, self.url)

    def getStreamDefect(self, streamDefectDO=None, scope=None):
        '''
        Get the streamDefectDataObj members for this defect
        '''
        if streamDefectDO is None:
            # Use a reasonable triage scope
            if scope is None:
                scope = self._triage_scope
            # If that's not set, just use the global scope
            if scope is None:
                scope = '*/*'
            f = client.defect.getDO('streamDefectFilterSpecDataObj',
                includeDefectInstances = True,
                includeHistory = True,
                scopePattern = scope)

            if self.status == 'Fixed':
                # Fixed defects will normally have no defectInstances
                # In that case, insert an empty list to avoid an AttributeException
                # when defectInstances is enumerated.
                streamDefectDO = client.defect.getStreamDefects([self.cid], f)[0]
                try: streamDefectDO.defectInstances
                except: streamDefectDO.defectInstances = []
            else:
                streamDefectDO = client.defect.getStreamDefects([self.cid], f)[0]

        # Now merge the streamDefectFields onto self
        for f in self._streamDefectFields:
            setattr(self, f, getattr(streamDefectDO, f))
        
    # Add a "scope" attribute that identifies the function if available
    @property
    def scope(self):
        try:
            return self.defectDO.functionDisplayName
        except AttributeError:
            return ''

    @property
    def component(self):
        return Component(self.componentName)
    
    # Add a "url" attribute that will pull up the defect in CIM
    @property
    def url(self):
        return client.defect.create_url(self.cid, self.projId)

    # Add a "projId" attribute with the containing CIM project id
    @property
    def projId(self):
        try:
            # The _projId attribute stores this defect's project id, if known.
            # We do this to avoid querying the server when possible.
            return self._projId
        except AttributeError:
            # Look through all projects for this CID
            for proj in self._projectDOs:
                # Skip any projects that have no streams
                try:
                    streams = proj.streams
                except AttributeError:
                    continue

                try:
                    # before v4, the stream id had a "type" attribute
                    streamIdDOs = [s.id for s in streams
                                    if s.id.type != 'SOURCE']
                except AttributeError:
                    # v4 and later don't have "type", but we also don't need
                    # to filter on it.  Just grab all the stream ids.
                    streamIdDOs = [s.id for s in streams]
                except:
                    # skip these streams if there are any other exceptions
                    continue
                mergedDefectFilterDO = client.defect.getDO(
                    'mergedDefectFilterSpecDataObj',
                    cidList = [self.defectDO.cid],
                    statusNameList = ['New','Triaged','Fixed','Dismissed'])
                client.defect.pageSpecDO.startIndex = 0
                mDOs = client.defect.getMergedDefectsForStreams(
                    streamIdDOs,
                    mergedDefectFilterDO,
                    client.defect.pageSpecDO)
                if mDOs.totalNumberOfRecords > 0:
                    self._projId = proj.projectKey
                    return self._projId

_cache['checkers'] = {}
    
class CheckerDescription(object):
    '''
    Helper class for a checker description
    '''
    def _cache_key(self, checker):
        return '??'.join([checker.checkerName, checker.domain,
                        checker.subcategory])
        
    def __init__(self, checker):
        key = self._cache_key(checker)
        if key not in _cache['checkers']:
            filter = client.config.getDO('checkerPropertyFilterSpecDataObj',
                checkerNameList=[checker.checkerName], 
            subcategoryList=[checker.subcategory],
            domainList=[checker.domain])
            self._props = client.config.getCheckerProperties(filter)
            if len(self._props) > 1:
                raise ValueError('Too many checkers found for %s/%s/%s'
                    % (checker.checkerName,
                        checker.subcategory,
                        checker.domain))
            elif len(self._props) < 1:
                _cache['checkers'][key] = client.config.getDO(
                    'checkerPropertyDataObj')
            else:
                _cache['checkers'][key] = self._props[0]
        self._props = _cache['checkers'][key]

    def __getattr__(self, name):
        return getattr(self._props, name)

_cache['files'] = {}

class SourceFile(object):
    '''
    Helper class for a source code file
    '''
    class SourceLine(object):
        def __init__(self, num, text):
            self.lineNum = num
            self.text = text

    def _cache_key(self, stream, file):
        return '??'.join([file.contentsMD5,file.filePathname])
        
    def __init__(self, stream, file):
        key = self._cache_key(stream, file)
        if key not in _cache['files']:
            src = client.defect.getFileContents(stream, file)
            text = zlib.decompress(standard_b64decode(src.contents))
            l = text.splitlines()
            lines = [self.SourceLine(*x) for x in zip(range(1,len(l)+1), l)]
            _cache['files'][key] = (text,lines)
        (self.contents,self._split_contents) = _cache['files'][key]
        
    def snippet(self, line, caption=None, context=7):
        start = line - (context/2) - 1
        if start < 0:
            context += start
            start = 0
        lines = self._split_contents[start:start+context]
        if caption:
            lines.insert(context/2, self.SourceLine('',caption))
        return lines
