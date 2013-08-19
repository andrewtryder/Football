###
# Copyright (c) 2013, spline
# All rights reserved.
#
#
###
import json
try:
    import xml.etree.cElementTree as ElementTree
except ImportError:
    import xml.etree.ElementTree as ElementTree
import cPickle as pickle
from base64 import b64decode  # b64.
import datetime  # utc time.
import pytz  # utc time.
from calendar import timegm  # utc time.
# extra supybot libs.
import supybot.conf as conf
import supybot.ircmsgs as ircmsgs
import supybot.schedule as schedule
# supybot libs.
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Football')
except:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x:x

class Football(callbacks.Plugin):
    """Add the help for "@plugin help Football" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        self.__parent = super(Football, self)
        self.__parent.__init__(irc)
        # initial states for games.
        self.games = None
        self.nextcheck = None
        self.scoredict = {}  # for scoring events.
        # now do our initial run.
        if not self.games:
            self.games = self._fetchgames()
        # now setup the empty channels dict.
        self.channels = {}
        self._loadpickle()  # load saved data into channels.
        # now setup the cron.
        def checkfootballcron():
            self.checkfootball(irc)
        try:
            schedule.addPeriodicEvent(checkfootballcron, 30, now=False, name='checkfootball')
        except AssertionError:
            try:
                schedule.removeEvent('checkfootball')
            except KeyError:
                pass
            schedule.addPeriodicEvent(checkfootballcron, 30, now=False, name='checkfootball')

    def die(self):
        try:
            schedule.removeEvent('checkfootball')
        except KeyError:
            pass
        self.__parent.die()

    #####################
    # INTERNAL COMMANDS #
    #####################

    def _httpget(self, url):
        """General HTTP resource fetcher."""

        try:
            headers = {"User-Agent":"Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:17.0) Gecko/20100101 Firefox/17.0"}
            page = utils.web.getUrl(url, headers=headers)
            return page
        except utils.web.Error as e:
            self.log.error("ERROR opening {0} message: {1}".format(url, e))
            return None

    ##########################
    # CHANNEL SAVE INTERNALS #
    ##########################

    def _loadpickle(self):
        """Load channel data from pickle."""

        try:
            datafile = open(conf.supybot.directories.data.dirize(self.name()+".pickle"), 'rb')
            try:
                dataset = pickle.load(datafile)
            finally:
                datafile.close()
        except IOError:
            return False
        # restore.
        self.channels = dataset["channels"]
        return True

    def _savepickle(self):
        """Save channel data to pickle."""

        data = {"channels": self.channels}
        try:
            datafile = open(conf.supybot.directories.data.dirize(self.name()+".pickle"), 'wb')
            try:
                pickle.dump(data, datafile)
            finally:
                datafile.close()
        except IOError:
            return False
        return True

    ############################
    # TIME AND TIME CONVERSION #
    ############################

    def _convertUTC(self, dtstring):
        """We convert our dtstrings in each game into UTC epoch seconds."""

        naive = datetime.datetime.strptime(str(dtstring), "%Y%m%d %I:%M %p")  # 20130808 7:30 PM
        local = pytz.timezone("US/Eastern")  # all of our "times" are in Eastern.
        local_dt = local.localize(naive, is_dst=None)
        utc_dt = local_dt.astimezone(pytz.UTC) # convert from utc->local(tzstring).
        rtrstr = timegm(utc_dt.utctimetuple())  # return epoch seconds/
        return rtrstr

    def _utcnow(self):
        """Calculate Unix timestamp from GMT."""

        ttuple = datetime.datetime.utcnow().utctimetuple()
        return timegm(ttuple)

    ###########################################
    # INTERNAL CHANNEL POSTING AND DELEGATION #
    ###########################################

    def _post(self, irc, message):
        """Posts message to a specific channel."""

        # first check if we have channels.
        if len(self.channels) == 0:  # bail if none.
            return
        # we do have channels. lets go and check where to put what.
        postchans = [k for (k, v) in self.channels.items() if v == 1]  # only channels with 1 = on.
        # iterate over each and post.
        for postchan in postchans:
            try:
                irc.queueMsg(ircmsgs.privmsg(postchan, message))
            except Exception as e:
                self.log.error("ERROR: Could not send {0} to {1}. {2}".format(message, postchan, e))

    ###################
    # GAMES INTERNALS #
    ###################

    def _fetchgames(self):
        """Returns a list of games."""

        # main url. this is for regular season stuff. for some reason, they split it.
        urls = ['aHR0cDovL3d3dy5uZmwuY29tL2xpdmV1cGRhdGUvc2NvcmVzdHJpcC9zcy54bWw=']
        # if we're in January or February, we have to add an additional url.
        if datetime.datetime.now().month in (1, 2):  # add in the postseason url.
            urls.append('aHR0cDovL3d3dy5uZmwuY29tL2xpdmV1cGRhdGUvc2NvcmVzdHJpcC9wb3N0c2Vhc29uL3NzLnhtbA==')
        # g container for our games on output.
        g = {}
        # now lets grab our urls.
        for url in urls:
            url = b64decode(url)  # decode.
            html = self._httpget(url)  # fetch.
            if not html:
                self.log.error("ERROR: Could not _fetchgame url {0}".format(url))
                continue
            # if we get html, load XML.
            try:
                tree = ElementTree.fromstring(html)
            except Exception, e:
                self.log.error("_fetchgames: ERROR. Could not parse XML :: {0}".format(e))
                return None
            # parse games.
            games = tree.findall('./gms/g')
            # iterate over all games we find.
            for game in games:
                tmp = dict((k, v) for (k, v) in game.items())  # dict comprehension for items.
                # create UTC starttime in dict.
                ttime = "{0} {1} PM".format(tmp['eid'][:-2], tmp['t'])  # chop -2 off eid. t = time in 12hr eastern, so add PM.
                tmp['start'] = self._convertUTC("{0}".format(ttime))  # convert to UTC and inject.
                # add dict (one per game) into dict of games.
                g[tmp['eid']] = tmp
        # return our dict of dicts (games).
        if len(g) == 0:  # failsafe incase none are here.
            self.log.error("_fetchgames: No games found or processed. Check logs.")
            # we should add backoff here.
            return None
        else:  # we did get games. return.
            return g

    def _scoreevent(self, gid):
        """
        Fetch the latest scoring event from a game.
        """

        url = b64decode('aHR0cDovL3d3dy5uZmwuY29tL2xpdmV1cGRhdGUvZ2FtZS1jZW50ZXIv') + '%s/%s_gtd.json' % (gid, gid)
        html = self._httpget(url)  # fetch url.
        if not html:
            self.log.error("ERROR: Could not fetch _scoreevent.")
            return None
        # we do have html. lets go.
        try:
            jsonf = json.loads(html.decode('utf-8'))
            base = jsonf[gid]  # base is our id.
            scrsummary = base['scrsummary']  # scoring events part.
            if (len(scrsummary) != 0):  # make sure we have events.
                sc = sorted(dict((int(k),v) for (k, v) in scrsummary.items()))  # sorted list of scoring event items.
                lastid = str(sc[-1])  # grab the last (-1) event from sorted scoring summary items (in str, base is int)
                lastev = scrsummary[lastid]  # grab last item from sorted list and grab that entry.
                lastev['id'] = lastid  # inject the id into the dict returned (str)
                # now lets check some text before we add or return. type = str, desc = text.
                if lastev['type'] == "TD":  # we wait for the XPA/2PA (pass/fail)
                    if (('(' in lastev['desc']) and (')' in lastev['desc'])):  # check for ( and )
                        return lastev  # now we can return the dict.
                else:  # non TD event so return regardless.
                    return lastev  # returns dict.
            else:  # no scoring events.
                return None
        except Exception, e:
            self.log.error("_scoreevent: ERROR :: {0} :: {1}".format(url ,e))
            return None

    def _finalstats(self, gid):
        """
        Fetch the final stat lines for each team.
        """

        url = b64decode('aHR0cDovL3d3dy5uZmwuY29tL2xpdmV1cGRhdGUvZ2FtZS1jZW50ZXIv') + '%s/%s_gtd.json' % (gid, gid)
        html = self._httpget(url)
        if not html:
            self.log.error("ERROR: Could not fetch _scoreevent.")
            return None
        # we do have html. wrap thing in a try/except block.
        try:
            jsonf = json.loads(html)
            # set our base.
            base = jsonf[gid]
            # create dict for output.
            statlines = {}
            # iterate over home/away.
            for t in ['home', 'away']:
                # new base
                b = base[t]['stats']
                # iterate over each category manually.
                # qb stats.
                sb = sorted(b['passing'].iteritems(), key=lambda x: x[1]['yds'], reverse=True)  # leader by yards.
                ps = "{0} ({1}/{2}) TD: {3} INT: {4}".format(sb[0][1]['name'].encode('utf-8'), sb[0][1]['cmp'], sb[0][1]['att'], sb[0][1]['tds'], sb[0][1]['ints'])
                # rb stats.
                sb = sorted(b['rushing'].iteritems(), key=lambda x: x[1]['yds'], reverse=True)  # leader by yards.
                rs = "{0} YDS: {1} ATT: {2} TD: {3}".format(sb[0][1]['name'].encode('utf-8'), sb[0][1]['yds'], sb[0][1]['att'], sb[0][1]['tds'])
                # passing stats.
                sb = sorted(b['receiving'].iteritems(), key=lambda x: x[1]['yds'], reverse=True)  # leader by yards.
                rs = "{0} YDS: {1} TD: {2}".format(sb[0][1]['name'].encode('utf-8'), sb[0][1]['yds'], sb[0][1]['tds'])
                # team stats.
                ts = "TO: {0} YDS: {1} FD: {2} TOP: {3}".format(b['team']['trnovr'], b['team']['totyds'], b['team']['totfd'], b['team']['top'])
                # now that we're done, append the temp dict into statlines for output.
                statlines[base[t]['abbr']] = "{0}  {1}: {2}  {3}: {4}  {5}: {6}".format(ts, ircutils.bold('Passing'), ps, ircutils.bold('Rushing'), rs, ircutils.bold('Receiving'), rs)
            # return now.
            return statlines
        except Exception, e:  # something went wrong above.
            self.log.error("_finalstats: GID: {0} ERROR: {1}".format(gid, e))
            return None

    def _gctosec(self, s):
        """Convert seconds of clock into an integer of seconds remaining."""

        if ':' in s:
            l = s.split(':')
            return int(int(l[0]) * 60 + int(l[1]))
        else:
            return int(round(float(s)))

    def _boldleader(self, awayteam, awayscore, hometeam, homescore):
        """Conveinence function to bold the leader."""

        if (int(awayscore) > int(homescore)):  # visitor winning.
            return "{0} {1} {2} {3}".format(ircutils.bold(awayteam), ircutils.bold(awayscore), hometeam, homescore)
        elif (int(awayscore) < int(homescore)):  # home winning.
            return "{0} {1} {2} {3}".format(awayteam, awayscore, ircutils.bold(hometeam), ircutils.bold(homescore))
        else:  # tie.
            return "{0} {1} {2} {3}".format(awayteam, awayscore, hometeam, homescore)

    ###################
    # PUBLIC COMMANDS #
    ###################

    def footballchannel(self, irc, msg, args, op, optchannel):
        """<add #channel|del #channel|list>

        Add or delete a channel from FOOTBALL output.
        Use list to list channels we output to.
        Ex: add #channel OR del #channel OR list
        """

        # first, lower operation.
        op = op.lower()
        # next, make sure op is valid.
        validop = ['add', 'list', 'del']
        if op not in validop:  # test for a valid operation.
            irc.reply("ERROR: '{0}' is an self.registryValue('checkInterval')invalid operation. It must be be one of: {1}".format(op, " | ".join([i for i in validop])))
            return
        # if we're not doing list (add or del) make sure we have the arguments.
        if (op != 'list'):
            if not optchannel:
                irc.reply("ERROR: add and del operations require a channel and team. Ex: add #channel or del #channel")
                return
            # we are doing an add/del op.
            optchannel = optchannel.lower()
            # make sure channel is something we're in
            if optchannel not in irc.state.channels:
                irc.reply("ERROR: '{0}' is not a valid channel. You must add a channel that we are in.".format(optchannel))
                return
        # main meat part.
        # now we handle each op individually.
        if op == 'add':  # add output to channel.
            self.channels[optchannel] = 1  # add it and on.
            self._savepickle()  # save.
            irc.reply("I have enabled FOOTBALL status updates on {0}".format(optchannel))
        elif op == 'list':  # list channels
            if len(self.channels) == 0:  # no channels.
                irc.reply("ERROR: I have no active channels defined. Please use the footballchannel add operation to add a channel.")
            else:   # we do have channels.
                for (k, v) in self.channels.items():  # iterate through and output translated keys.
                    if v == 0:  # swap 0/1 into OFF/ON.
                        irc.reply("{0} :: OFF".format(k))
                    elif v == 1:
                        irc.reply("{0} :: ON".format(k))
        elif op == 'del':  # delete an item from channels.
            if optchannel in self.channels:  # id is already in.
                del self.channels[optchannel]  # remove it.
                self._savepickle()  # save.
                irc.reply("I have successfully removed {0}".format(optchannel))
            else:  # id was NOT in there.
                irc.reply("ERROR: I do not have {0} in {1}".format(optarg, optchannel))

    footballchannel = wrap(footballchannel, [('checkCapability', 'admin'), ('somethingWithoutSpaces'), optional('channel')])

    def footballon(self, irc, msg, args, channel):
        """
        Enable FOOTBALL scoring in channel.
        """

        # channel
        channel = channel.lower()
        # check if op.
        if not irc.state.channels[channel].isOp(msg.nick):
            irc.reply("ERROR: You must be an op in this channel for this command to work.")
            return
        # check now.
        if channel in self.channels:
            self.channels[channel] = 1
            irc.reply("I have turned on FOOTBALL livescoring for {0}".format(channel))
        else:
            irc.reply("ERROR: {0} is not in any known channels.".format(channel))

    footballon = wrap(footballon, [('channel')])

    def footballoff(self, irc, msg, args, channel):
        """
        Disable FOOTBALL scoring in channel.
        """

        # channel
        channel = channel.lower()
        # check if op.
        if not irc.state.channels[channel].isOp(msg.nick):
            irc.reply("ERROR: You must be an op in this channel for this command to work.")
            return
        # check now.
        if channel in self.channels:
            self.channels[channel] = 0
            irc.reply("I have turned off FOOTBALL livescoring for {0}".format(channel))
        else:
            irc.reply("ERROR: {0} is not in any known channels.".format(channel))

    footballoff = wrap(footballoff, [('channel')])

    def footballscores(self, irc, msg, args):
        """
        FOOTBALL Scores.
        """

        irc.reply("SCOREDICT: {0}".format(self.scoredict))

        for (k, v) in self.games.items():
            irc.reply("{0} :: {1}".format(k, v))

    footballscores = wrap(footballscores)

    #def checkfootball(self, irc, msg, args):
    def checkfootball(self, irc):
        """
        Main loop.
        """
        # before anything, check if nextcheck is set and is in the future.
        if self.nextcheck:  # set
            if self.nextcheck > self._utcnow():  # in the future so we backoff.
                #self.log.info("checkfootball: nextcheck is in the future. {0} from now.".format(self.nextcheck-self._utcnow()))
                return
            else:  # in the past so lets reset it. this means that we've reached the time where firstgametime should begin.
                #self.log.info("checkfootball: nextcheck has passed. we are resetting and continuing normal operations.")
                self.nextcheck = None
        # we must have initial games. bail if not.
        if not self.games:
            self.games = self._fetchgames()
            return
        # check and see if we have initial games, again, but bail if no.
        if not self.games:
            self.log.error("checkfootball: I did not have any games in self.games")
            return
        else:  # setup the initial games.
            games1 = self.games
        # now we must grab the new status.
        games2 = self._fetchgames()
        if not games2:  # something went wrong so we bail.
            self.log.error("checkfootball: fetching games2 failed.")
            return

        # main handler for event changes.
        # we go through each event, compare, and post according to the changes.
        for (k, v) in games1.items():  # iterate over games.
            if k in games2:  # must mate keys between games1 and games2.
                # FIRST, ACTIVE GAME EVENTS ONLY.
                if ((v['q'] in ("1", "2", "3", "4", "5")) and (games2[k]['q'] in ("1", "2", "3", "4", "5"))):
                    # make sure game is in scoredict like if/when we reload.
                    if k not in self.scoredict:
                        self.scoredict[k] = {}
                    ## SCORING EVENT.
                    scev = self._scoreevent(k)
                    if scev:
                        if scev['id'] not in self.scoredict[k]:  # event is unique.
                            #self.log.info("Should fire scoring event in {0}".format(k))
                            l = self._boldleader(games2[k]['v'], games2[k]['vs'], games2[k]['h'], games2[k]['hs'])  # bold leader
                            ordinal = utils.str.ordinal(str(games2[k]['q']))  # ordinal for time/quarter.
                            mstr = "{0} :: {1} :: {2} :: {3} ({4} {5})".format(l, scev['team'], scev['type'], scev['desc'], ordinal, games2[k]['k'])
                            self.scoredict[k] = scev['id']  # we add the event so we don't repeat.
                            # now post event.
                            self._post(irc, mstr)
                    # TEAM ENTERS REDZONE
                    if ((v['rz'] == "0") and (games2[k]['rz'] == "1")):
                        #self.log.info("Should fire redzone event.")
                        # must have pos team. we do this as a sanity check because w/o the team it's pointless.
                        if 'p' in games2[k]:
                            l = self._boldleader(games2[k]['v'], games2[k]['vs'], games2[k]['h'], games2[k]['hs'])
                            ordinal = utils.str.ordinal(str(games2[k]['q']))  # ordinal for time/quarter.
                            mstr = "{0} :: {1} is in the {2} ({3} {4})".format(l, ircutils.bold(games2[k]['p']), ircutils.mircColor('redzone', 'red'), ordinal, games2[k]['k'])
                            # now post event.
                            self._post(irc, mstr)
                    # 2 MINUTE WARNING.
                    if ((games2[k]['q'] in ("2", "4")) and (self._gctosec(v['k']) > 120) and (self._gctosec(games2[k]['k']) <= 120)):
                        #self.log.info("should fire 2 minute warning: q: {0} v['k'] {1} games2[k] {2}".format(games2[k], v['k'], games2[k]['k']))
                        l = self._boldleader(games2[k]['v'], games2[k]['vs'], games2[k]['h'], games2[k]['hs'])
                        ordinal = utils.str.ordinal(str(games2[k]['q']))
                        mstr = "{0} :: {1} ({2} qtr {3})".format(l, ircutils.bold("2 minute warning."), ordinal, games2[k]['k'])
                        # now post event.
                        self._post(irc, mstr)
                    # START OF 2ND/4TH QUARTER.
                    if (((v['q'] == "1") and (games2[k]['q'] == "2")) or ((v['q'] == "3") and (games2[k]['q'] == "4"))):
                        #self.log.info("Should fire start of 2nd or 4th qtr.")
                        l = self._boldleader(games2[k]['v'], games2[k]['vs'], games2[k]['h'], games2[k]['hs'])
                        q = "Start of {0} quarter".format(utils.str.ordinal(str(games2[k]['q'])))
                        mstr = "{0} :: {1}".format(l, ircutils.mircColor(q, 'green'))
                        # now post event.
                        self._post(irc, mstr)
                    # GAME GOES INTO OVERTIME.
                    if ((v['q'] == "4") and (games2[k]['q'] == "5")):
                        #self.log.info("Should fire overtime.")
                        mstr = "{0} {1} {2} {3} :: {4}".format(games2[k]['v'], games2[k]['vs'], games2[k]['h'], games2[k]['hs'], ircutils.bold("Overtime"))
                        # now post event.
                        self._post(irc, mstr)
                # EVENTS THAT SHOULD ONLY FIRE OUTSIDE ACTIVE GAME EVENTS.
                elif (v['q'] != games2[k]['q']):
                    # GAME START.
                    if ((v['q'] == "P") and (games2[k]['q'] == "1")):
                        #self.log.info("Should fire start of game {0}".format(k))
                        mstr = "{0} v. {1} :: {2}".format(games2[k]['v'], games2[k]['h'], ircutils.mircColor('KICKOFF', 'green'))
                        # now post event.
                        self._post(irc, mstr)
                        # add event into scoredict now that we start.
                        if k not in self.scoredict:
                            self.scoredict[k] = {}
                        else:
                            self.log.error("checkfootball: {0} is already in scoredict".format(k))
                    # GAME GOES FINAL.
                    if ((v['q'] in ("4", "5")) and (games2[k]['q'] in ("F", "FO"))):
                        #self.log.info("Should fire final of game {0}".format(k))
                        l = self._boldleader(games2[k]['v'], games2[k]['vs'], games2[k]['h'], games2[k]['hs'])
                        mstr = "{0} :: {1}".format(l, ircutils.mircColor(games2[k]['q'], 'red'))
                        # now post event.
                        self._post(irc, mstr)
                        # try and grab finalstats for game.
                        fs = self._finalstats(k)
                        if fs:  # we got fs.
                            for (y, z) in fs.items():  # iterate over each team.
                                fss = "{0} :: {1}".format(y, z)  # format string.
                                # now post event.
                                self._post(irc, fss)
                        else:  # we didn't get it.
                            self.log.error("checkfootball: failed to get fs for {0}".format(k))
                        # delete item from scoredict now that we're final.
                        if k in self.scoredict:
                            del self.scoredict[k]
                        else:
                            self.log.info("checkfootball: error {0} was not in scoredict when we went final".format(k))
                    # GAME GOES TO HALFTIME.
                    if ((v['q'] == "2") and (games2[k]['q'] == "H")):
                        l = self._boldleader(games2[k]['v'], games2[k]['vs'], games2[k]['h'], games2[k]['hs'])
                        mstr = "{0} :: {1}".format(l, ircutils.mircColor('HALFTIME', 'yellow'))
                        # now post event.
                        self._post(irc, mstr)
                    # GAME COMES OUT OF HALFTIME.
                    if ((v['q'] == "H") and (games2[k]['q'] == "3")):
                        l = self._boldleader(games2[k]['v'], games2[k]['vs'], games2[k]['h'], games2[k]['hs'])
                        s = ircutils.mircColor('Start of 3rd qtr', 'green')
                        mstr = "{0} :: {1}".format(l, s)
                        # now post event.
                        self._post(irc, mstr)

        # done processing active event things.
        # we now need to figure out when to next process.
        self.games = games2  # reset games.
        # now we have to process gamestatuses to figure out what to do. uniq of gamestatuses.
        gamestatuses = set([z['q'] for (i, z) in games2.items()])
        # possible statuses: F/FO = game over, P = pending, H = halftime. Rest are active games.
        if __builtins__['any'](z in ("1", "2", "3", "4", "5", "H") for z in gamestatuses):
            self.nextcheck = None  # reset nextcheck.
        else:  # we're here if there are NO active games.
            utcnow = self._utcnow()  # grab UTCnow.
            if 'P' in gamestatuses:  # we have pending games left in here.
                self.log.info("checkfootball: only pending games.")
                firstgametime = sorted([f['start'] for (i, f) in games2.items() if f['q'] == "P"])[0]  # sort, first item.
                if utcnow < firstgametime:  # make sure these are not stale. this means firstgametime = future.
                    self.log.info("checkfootball: firstgametime is in the future.")
                    self.nextcheck = firstgametime  # set our nextcheck to this time.
                else:  # we're here if firstgametime is stale (in the past)
                    self.log.info("checkfootball: first gametime is in the past.")
                    fgtdiff = firstgametime-utcnow  # get the diff.
                    if (fgtdiff < 3601):  # it's under an hour old. carry on.
                        self.nextcheck = None
                    else:  # older than an hour. lets holdoff for 5m.
                        self.nextcheck = utcnow+300
            else:  # we're here if there are NO active games and NO future games. I assume all games are final then.
                self.log.info("checkfootball: no active games and no future games. holding off for an hour.")
                self.nextcheck = utcnow+3600  # hold off for one hour.
    #    self.log.info("Done running.")
    #checkfootball = wrap(checkfootball)

Class = Football


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
