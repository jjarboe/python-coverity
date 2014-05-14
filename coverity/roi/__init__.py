'''
A helper module to facilitate computation of estimated savings due
to finding defects earlier through the use of the Coverity platform.
'''

class ROICalculator(object):
    '''
    Class used to estimate the savings enabled by the Coverity platform.
    
    The savings are based on the premise that Coverity enables you to find issues in development
    that would normally be found later in the development lifecycle.
    
    For purposes of estimating the effort, issues are classified as "difficult", "average", or "easy".  These classifications reflect that some issues are more difficult to find and fix than others.
    
    The default values for the calculator are based on a broad NIST study performed in the early 2000's and are not specific to the Coverity platform.
    '''
    
    # Hours invested in a defect found during development/unit testing
    _ut_hours = 3.4
    # Hours invested in a defect found during system/integration testing
    _st_hours = 7.0
    # Hours invested in a defect found in the field
    _field_hours = 13.5

    def __init__(self, introduced_pct=0, difficult_pct=15, average_pct=80, easy_pct=5, ut_pct=30, st_pct=30, field_pct=30, fp_pct=10, loaded_dev_cost=(150000.0/2000), effort_difficult=2.0, effort_easy=0.5, triage=1.0/12):
        '''
        introduced_pct: How many new issues are introduced each year, as a percentage of existing issues?
        difficult_pct: Percentage of issues that are difficult to find and fix
        average_pct: Percentage of issues that require average effort to find and fix
        easy_pct: Percentage of issues that are easy to find and fix
        ut_pct: Percentage of issues that would be found in development/unit test without Coverity
        st_pct: Percentage of issues that would be found in system/integration test without Coverity
        field_pct: Percentage of issues that would be found in the field without Coverity
        fp_pct: Percentage of Coverity issues that are false positive/intentional
        loaded_dev_cost: Fully loaded developer cost per hour
        effort_difficult: Effort required to find and fix "difficult" issues (as percentage of average effort)
        effort_easy: Effort required to find and fix "easy" issues (as percentage of average effort)
        triage: hours required to triage and fix issues with Coverity
        '''
        pct = lambda x: x/100.0

        self._difficult = pct(difficult_pct)
        self._average = pct(average_pct)
        self._easy = pct(easy_pct)

        self._ut = pct(ut_pct)
        self._st = pct(st_pct)
        self._field = pct(field_pct)
        self._fp = pct(fp_pct)

        self._loaded = loaded_dev_cost
        self._effort_difficult = effort_difficult
        self._effort_easy = effort_easy
        self._projection = 1.0 + pct(introduced_pct)
        self._triage = triage

        self._cost_factor = ((self._effort_difficult * self._difficult) + (self._average) + (self._effort_easy * self._easy)) * self._projection

    def info(self):
        '''
        Returns a string containing a summary of the parameters used by this calculator.
        '''
        desc = []
        if self._loaded:
            desc.append('Fully loaded developer cost: %g/hour or %s/year' % (
                        self._loaded,
                        numstr(self._loaded * 40 * 50)) )
        if self._fp:
            desc.append('False positive rate: %g%%' % (self._fp*100,))
        if self._triage:
            desc.append('Minutes to triage a Coverity issue: %d' % (
                        self._triage*60))
        if self._projection < 1.0:
            desc.append('Projected to lose %d%% issues annually' % (
                        (self._projection-1)*100) )
        elif self._projection > 1.0:
            desc.append('Projected to add %d%% issues annually' % (
                        (self._projection-1)*100) )

        return 'ROI calculator assumptions:\n  '+'\n  '.join(desc)

    def cost_with_coverity(self, issues):
        '''
        Returns a tuple (hours, dollars) indicating the effort required to address the specified number of issues while using the Coverity platform.
        '''
        hours = issues * (1 + self._triage - self._fp)

        return hours, hours * self._loaded

    def cost_without_coverity(self, issues):
        '''
        Returns a tuple (hours, dollars) indicating the effort required to address the specified number of issues while not using the Coverity platform.
        '''
        val = lambda stage, hours: issues * self._cost_factor * stage * hours

        wo_coding = val(self._ut, self._ut_hours)
        wo_integration = val(self._st, self._st_hours)
        wo_field = val(self._field, self._field_hours)

        hours = wo_coding + wo_integration + wo_field
        return hours, hours * self._loaded

    def value(self, issues):
        '''
        Returns a tuple (hours, dollars) indicating the savings enabled by using the Coverity platform to address the specified number of issues.
        '''
        hours = self.cost_without_coverity(issues)[0] - self.cost_with_coverity(issues)[0]
        return hours, hours * self._loaded

def numstr(x):
    '''
    Returns a string with a human-friendly representations of parameter x.
    
    The number is generally shortened to use the "K" suffix indicating thousands or "M" suffix indicating millions.
    '''
    p = ''
    if x > 1000000:
        x = x / 1000000
        p = 'M'
    elif x > 1000:
        x = x / 1000
        p = 'K'
    return '{:>7} {:s}'.format(round(x,1), p)
