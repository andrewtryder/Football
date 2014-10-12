###
# Copyright (c) 2013-2014, spline
# All rights reserved.
#
#
###

from supybot.test import *
from supybot.commands import *

class FootballTestCase(ChannelPluginTestCase):
    plugins = ('Football',)

    def testFootball(self):
        self.assertResponse('footballchannel add #test', "I have enabled FOOTBALL status updates on #test") #, 'I have added SEC into #test')
        self.assertResponse('footballchannel del #test', "I have successfully removed #test") #, 'I have added SEC into #test')

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
