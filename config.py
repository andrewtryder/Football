###
# Copyright (c) 2013, spline
# All rights reserved.
#
#
###

import supybot.conf as conf
import supybot.registry as registry
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Football')
except:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x:x

def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Football', True)


Football = conf.registerPlugin('Football')
# This is where your configuration variables (if any) should go.  For example:
conf.registerChannelValue(Football, 'prefix', registry.Boolean(False, """Should we prefix output with the string"""))
conf.registerChannelValue(Football, 'prefixString', registry.String("NFL: ", """Prefix String."""))


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
