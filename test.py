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
        self.assertResponse('footballchannel add #test', "ERROR: '#test' is not a valid channel. You must add a channel that we are in.") #, 'I have added SEC into #test')
        self.assertResponse('footballchannel del #test', "ERROR: '#test' is not a valid channel. You must add a channel that we are in.") #, 'I have added SEC into #test')

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
