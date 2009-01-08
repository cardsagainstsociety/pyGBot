##
##    pyGBot - Versatile IRC Bot
##    Copyright (C) 2008 Morgan Lokhorst-Blight, Alex Soborov
##
##    This program is free software: you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation, either version 3 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License
##    along with this program.  If not, see <http://www.gnu.org/licenses/>.
##

import log
from ..Commands import BaseCommand
from ..Auth import AuthLevels as AL

class StatsRoll(BaseCommand):
    level = AL.User
    def __init__(self, bot, channel, user, args):
        args = " " + args.lstrip(" ")
        args = [tuple(x.split(" ")) for x in args.split(" -")[1:]]

        for arg in args:
            if arg[0] == 'sort':
                if len(arg[0]) > 1 and (arg[0][1] == 'asc' or arg[0][1] == 'desc'):
                    sortdir = args[0][1]
                else:
                    sortdir = 'asc'
            elif arg[0] == 'verbose':
                verbose = True

        rolls,stats = self.rollStats(sortdir)

        if channel is None:
            out = bot.privout
            target = user
        else:
            out = bot.pubout
            target = channel


        if verbose:
            out(target,str(rolls))

        out(target,"Stats are: %s." % ', '.join(map(str, stats)))


    def rollStats(self, sortdir):
        """ Roll up a standard 6x4d6 (drop lowest) D&D Stats roll."""
        rolls = [[random.randint(1,6) for i in range(0,4)] for j in range(0,6)]

        # Drop lowest of each 4d6 set and sum to produce 6 stat values
        stats = [sum(sorted(x)[1:]) for x in rolls]

        if sortdir == 'asc':
            stats.sort()
        elif sortdir == 'desc':
            stats.sort(None,None,True)
 
        return rolls, stats
