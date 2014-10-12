###
# Copyright (c) 2013-2014, spline
# All rights reserved.
#
#
###

from supybot.test import *

class FootballTestCase(PluginTestCase):
    plugins = ('Football',)

    def testFootball(self):
        self.assertError('footballchannel add #test') #, 'I have added SEC into #test')
        self.assertError('footballchannel del #test') # , 'I have successfully removed SEC from #test')

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
