##
##    Apples To Apples - a plugin for pyGBot
##    Copyright (C) 2008 Morgan Lokhorst-Blight
##
##    This program is free software: you can whiteistribute it and/or modify
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

import sys, string, random, time
from pyGBot import log
from pyGBot.BasePlugin import BasePlugin
from CardsAgainstHumanityCards import WHITECARDS, BLACKCARDS

class CardsAgainstHumanity(BasePlugin):
    def __init__(self, bot, options):
        BasePlugin.__init__(self, bot, options)
        self.output = True
        self.resetdata()
        
    def timer_tick(self):
        if self.gamestate == "InProgress":
            self.timer = self.timer + 1
            if self.timer == 90:
                self.timer = 0
                self.cmd_prompt([], self.channel, self.bot.nickname)

    def msg_channel(self, channel, user, message):
        a = string.split(message, ":", 1)
        if len(a) > 1 and a[0].lower() == self.bot.nickname.lower():
            self.do_command(channel, user, string.strip(a[1]))
        elif message[0]=='!' and (len(message) > 1) and message[1]!='!':
            self.do_command(channel, user, string.strip(message[1:]))
            
    def msg_private(self, user, message):
        self.do_command(user, user, message)

    def reply(self, channel, user, text):
        if channel != user:
            self.bot.pubout(channel, "%s: %s" % (user, text))
        else:
            self.bot.noteout(user, text)

    def privreply(self, user, text):
        self.bot.noteout(user, text)
        
    def user_nickchange(self, old, new):
        for list_ in (self.players, self.live_players, self.round_players):
            if old in list_:
                list_[list_.index(old)] = new
        for value in (self.playedcards):
            if value[0] == old:
                value[0] = new
        for map_ in (self.hands, self.woncards):
            if map_.has_key(old):
                map_[new] = map_[old]
                del map_[old]

    def resetdata(self):
        self.gamestate = "None"
        self.players = []
        self.live_players = []
        self.round_players = []
        self.blackdeck = list(BLACKCARDS)
        random.shuffle(self.blackdeck)
        self.whitedeck = list(WHITECARDS)
        random.shuffle(self.whitedeck)
        self.judgeindex = 0
        self.hands={}
        self.blackcard = None
        self.playedcards = {}
        self.woncards = {}
        self.cardstowin = 0
        self.playamount = 0
        self.drawamount = 0
        self.channel = None
        self.timer = 0
        self.judging = False

    def startgame(self):
        self.gamestate = "InProgress"
        self.bot.pubout(self.channel, "A new game is starting! Please wait, dealing cards...")
        self.players = list(self.live_players)
        random.shuffle(self.live_players)
        for user in self.live_players:
            self.woncards[user] = []
            self.hands[user] = []
        for i in range(1, 11):
            for user in self.live_players:
                self.hands[user].append(self.whitedeck.pop(0))
#        for user in self.live_players:
#            self.hands[user].sort()
#            hand = []
#            for i in range (1, 11):
#                hand.append("%i: \x034%s\x0F" % (i, self.hands[user][i-1]))
#            self.privreply(user, "Your hand: %s" % ", ".join(hand))
        if len(self.live_players) >= 8:
            self.cardstowin = 4
        else:
            self.cardstowin = 12 - len(self.live_players)
        self.judgeindex = len(self.live_players) - 1
        self.newround()

    def endgame(self):
        self.bot.pubout(self.channel, "The game is over.")
        if self.gamestate == "InProgress":
            blackbuild = []
            for user in self.players:
                if len(self.woncards[user]) != 0:
                    blackbuild.append("%s - %i" % (user, len(self.woncards[user])))
            if blackbuild != []:
                self.bot.pubout(self.channel, "Black cards per players: %s" % ", ".join(blackbuild))
        self.resetdata()
        
    def newround(self):
        self.judging = False
        self.timer = 0
        self.cmd_scores([], self.channel, self.bot.nickname)
        
        self.playedcards = []
        if self.judgeindex == len(self.live_players) - 1:
            self.judgeindex = 0
        else:
            self.judgeindex = self.judgeindex + 1
        self.bot.pubout(self.channel, "This round's Card Czar is \x02\x0312%s\x0F." % self.live_players[self.judgeindex])
        
        self.blackcard = self.blackdeck.pop(0)
        if self.blackcard[1] == 1:
            self.bot.pubout(self.channel, "The new black card is: \"\x02\x033%s\x0F\". Please play ONE card from your hand using '!play <number>'." % (self.blackcard[0]))
        elif self.blackcard[1] == 2:
            self.bot.pubout(self.channel, "The new black card is: \"\x02\x033%s\x0F\". Please play TWO cards from your hand, in desired order, using '!play <number> <number>'." % (self.blackcard[0]))
        elif self.blackcard[1] == 3:
            self.bot.pubout(self.channel, "The new black card is: \"\x02\x033%s\x0F\". Please play THREE cards from your hand, in desired order, using '!play <number> <number> <number>'." % (self.blackcard[0]))
        
        self.deal()
            
    def checkroundover(self):
        allplayed = True
        for player in self.live_players:
            if player != self.live_players[self.judgeindex]:
                playerplayed = False
                for card in self.playedcards:
                    if player == card[0]:
                        playerplayed = True
                if playerplayed == False:
                    allplayed = False
        if allplayed:
            self.bot.pubout(self.channel, "All cards have been played.")
            self.judging = True
            self.beginjudging()
            
    def beginjudging(self):
        if self.judging == True:
            self.timer = 0
            self.bot.pubout(self.channel, "Black card is: \"\x02\x033%s\x0F\"" % self.blackcard[0])
            random.shuffle(self.playedcards)
            if self.blackcard[0].find("____") == -1:
                for i in range (0, len(self.playedcards)):
                    self.bot.pubout(self.channel, "%i. \x034%s\x0F" % (i+1, " / ".join(self.playedcards[i][1:][0])))
            else:
                for i in range(0, len(self.playedcards)):
                    self.bot.pubout(self.channel, "%i. %s" % (i+1, self.blackcard[0].replace("____", "\x034%s\x0F") % tuple(self.playedcards[i][1:][0])))
            self.bot.pubout(self.channel, "\x02\x0312%s\x0F: Please make your decision now using the '!pick <number>' command." % self.live_players[self.judgeindex])
        
    def cardwin(self, winningcard):
        winner = self.playedcards[winningcard][0]
        self.bot.pubout(self.channel, "The Card Czar picked \"\x034%s\x0F\"! \x02\x0312%s\x0F played that, and gets to keep the black card." % (" / ".join(self.playedcards[winningcard][1:][0]), winner))
        self.woncards[winner].append(self.blackcard)
        if not self.checkgamewin():
            self.newround()
        
    def checkgamewin(self):
        for user in self.players:
            if len(self.woncards[user]) >= self.cardstowin:
                self.bot.pubout(self.channel, "%s now has %i Awesome Points. %s wins!" % (user, len(self.woncards[user]), user))
                self.endgame()
                return True
        if len(self.blackdeck) == 0:
            self.bot.pubout(self.channel, "There are no more black cards. The game is over!")
            self.endgame()
            return True
        else:
            return False

    def deal(self):
        for user in self.live_players:
            if user != self.live_players[self.judgeindex]:
                while len(self.hands[user]) < 9 + self.blackcard[1]:
                    self.hands[user].append(self.whitedeck.pop(0))
                    self.privreply(user, "You draw: \x034%s\x0F." % (self.hands[user][len(self.hands[user])-1]))
        for user in self.live_players:
            if user != self.live_players[self.judgeindex]:
                self.hands[user].sort()
                hand = []
                for i in range (1, 10 + self.blackcard[1]):
                    hand.append("%i: \x034%s\x0F" % (i, self.hands[user][i-1]))
                self.privreply(user, "Your hand: %s" % ", ".join(hand))
        
    def cmd_play(self, args, channel, user):
        if self.gamestate == "InProgress":
            cardplayed = False
            for cards in self.playedcards:
                if cards[0] == user:
                    cardplayed = True
            if user in self.live_players and user not in self.playedcards and user != self.live_players[self.judgeindex] and self.judging == False and cardplayed == False:
                try:
                    if len(args) == self.blackcard[1]:
                        playcards = []
                        valid = True
                        for cardnum in args:
                            if int(cardnum) > 0 and int(cardnum) <= (9 + self.blackcard[1]):
                                playcards.append(self.hands[user][int(cardnum)-1])
                            else:
                                valid = False
                                self.reply(channel, user, "Please pick valid card numbers.")
                        if valid:
                            self.playedcards.append([user, playcards])
                            for removecards in playcards:
                                self.hands[user].remove(removecards)
                            self.reply(channel, user, "You have played your card(s).")
                            self.checkroundover()
                    else:
                        self.reply(channel, user, "Wrong number of cards! Play %i." % self.blackcard[1])
                except:
                    self.reply(channel, user, "Please use the card's number.")
            elif user not in self.live_players:
                self.reply(channel, user, "You are not in this game.")
            elif user in self.playedcards:
                self.reply(channel, user, "You have already played a card this round.")
            elif user == self.live_players[self.judgeindex]:
                self.reply(channel, user, "You are Card Czar this round.")
            elif self.judging == True:
                self.reply(channel, user, "Judging has already begun, wait for the next round.")
            elif cardplayed:
                self.reply(channel, user, "You have already played your card(s) this round.")
        else:
            self.reply(channel, user, "There is no game in progress.")

    def cmd_pick(self, args, channel, user):
        if self.gamestate == "InProgress":
            if self.judging == True and user == self.live_players[self.judgeindex]:
                try:
                    if int(args[0]) > 0 and int(args[0]) <= len(self.playedcards):
                        self.reply(channel, user, "You have chosen.")
                        self.cardwin(int(args[0]) - 1)
                    else:
                        self.reply(channel, user, "Please pick a valid card number.")
                except ValueError:
                    self.reply(channel, user, "Please use the card's number.")
            elif user != self.live_players[self.judgeindex]:
                self.reply(channel, user, "You are not the Card Czar this round.")
            elif len(self.playedcards) != len(self.live_players) - 1:
                self.reply(channel, user, "Not everyone has played a card yet.")
            elif user not in self.live_players:
                self.reply(channel, user, "You are not in this game.")
        else:
            self.reply(channel, user, "There is no game in progress.")
            
    def cmd_start(self, args, channel, user):
        if self.gamestate == "None":
            self.gamestate = "Starting"
            self.bot.pubout(channel, "A new game has been started!")
            self.live_players.append(user)
            self.channel = channel
        elif self.gamestate == "Starting":
            if user in self.live_players and len(self.live_players) >= 3:
                self.startgame()
            elif user not in self.live_players:
                self.reply(channel, user, "There is a game starting already. Please join instead.")
            else:
                self.reply(channel, user, "Not enough players to start a game. Minimum of 4 required. Currently: %i" % len(self.live_players))
        elif self.gamestate == "InProgress":
            self.reply(channel, user, "There is a game in progress. Please wait for it to end.")

    def cmd_stats(self, args, channel, user):
        if self.gamestate == "None":
            self.reply(channel, user, "No game in progress.")
        elif self.gamestate == "Starting":
            self.reply(channel, user, "A new game is starting. Currently %i players: %s" % (len(self.live_players), ", ".join(self.live_players)))
        elif self.gamestate == "InProgress":
            self.bot.pubout(self.channel, "Player order: %s. %s is the current Card Czar. Current black card is: \x033%s\x0F" % (", ".join(self.live_players), self.live_players[self.judgeindex], self.blackcard[0]))
            self.cmd_scores(self, args, channel, user)
                
    def cmd_status(self, args, channel, user):
        self.cmd_stats(args, channel, user)

    def cmd_scores(self, args, channel, user):
        if self.gamestate == "None" or self.gamestate == "Starting":
            self.reply(channel, user, "No game in progress.")
        elif self.gamestate == "InProgress":
            blackbuild = []
            for player in self.players:
                if len(self.woncards[player]) != 0:
                    blackbuild.append("%i - %s" % (len(self.woncards[player]), player))
            blackbuild.sort(reverse=True)
            if blackbuild != []:
                self.bot.pubout(self.channel, "Awesome Points per players: %s. Points to win: %i." % (", ".join(blackbuild), self.cardstowin))
            else:
                self.bot.pubout(self.channel, "No scores yet. Cards to win: %i." % self.cardstowin)

    def cmd_join(self, args, channel, user):
        if self.gamestate == "None":
            self.reply(channel, user, "No game in progress. Please start one.")
        elif self.gamestate == "Starting":
            if user not in self.live_players:
                self.live_players.append(user)
                self.bot.pubout(self.channel, "%s is now in the game." % user)
            else:
                self.reply(channel, user, "You are already in the game.")
        elif self.gamestate == "InProgress":
            if user not in self.live_players:
                self.bot.pubout(self.channel, "%s is now in the game." % user)
                if user not in self.players:
                    self.players.append(user)
                if user not in self.woncards:
                    self.woncards[user] = []
                self.live_players.insert(self.judgeindex, user)
                self.judgeindex = self.judgeindex + 1
                if user not in self.hands:
                    self.hands[user] = []
                    for i in range(1, 11):
                        self.hands[user].append(self.whitedeck.pop(0))
                    self.hands[user].sort()
                else:
                    while len(self.hands[user]) < 10:
                        self.hands[user].append(self.whitedeck.pop(0))
                        self.privreply(user, "You draw: \x034%s\x0F: %s" % (self.hands[user][len(self.hands[user])-1], WHITECARDS[self.hands[user][len(self.hands[user])-1]]))
                hand = []
                for i in range (1, 8):
                    hand.append("%i: \x034%s\x0F" % (i, self.hands[user][i-1]))
                self.privreply(user, "Your hand: %s" % ", ".join(hand))
            else:
                self.reply(channel, user, "You are already in the game.")

    def cmd_hand(self, args, channel, user):
        if self.gamestate == "InProgress":
            if user in self.live_players:
                hand = []
                for i in range (1, len(self.hands[user]) + 1):
                    hand.append("%i: \x034%s\x0F" % (i, self.hands[user][i-1]))
                self.privreply(user, "Your hand: %s" % ", ".join(hand))
            else:
                self.reply(channel, user, "You are not in this game.")
        else:
            self.reply(channel, user, "There is no game in progress.")
#        
#    def cmd_blacks(self, args, channel, user):
#        if self.gamestate == "InProgress":
#            if user in self.live_players:
#                if len(self.woncards[user]) != 0:
#                    hand = []
#                    for i in range (1, len(self.woncards[user]) + 1):
#                        hand.append("%i: \x02\x033%s\x0F" % (i, self.woncards[user][i-1]))
#                    self.privreply(user, "Your black cards: %s" % ", ".join(hand))
#                else:
#                    self.privreply(user, "You do not have any black cards.")
#            else:
#                self.reply(channel, user, "You are not in this game.")
#        else:
#            self.reply(channel, user, "There is no game in progress.")

    def cmd_prompt(self, args, channel, user):
        if self.gamestate == "InProgress":
            if self.judging == False:
                finishedplayers = [self.judgeindex]
                for card in self.playedcards:
                    finishedplayers.append(card[0])
                unfinishedplayers = []
                for player in self.live_players:
                    if player not in finishedplayers:
                        unfinishedplayers.append(player)
                unfinishedplayers.remove(self.live_players[self.judgeindex])
                self.bot.pubout(channel, "%s: Please play a card." % ", ".join(unfinishedplayers))
            else:
                self.bot.pubout(channel, "%s: Please pick a card to win." % self.live_players[self.judgeindex])
        else:
            self.reply(channel, user, "There is no game in progress.")

    def cmd_quit(self, args, channel, user):
        if self.gamestate == "InProgress":
            if user in self.live_players:
                judge = self.live_players[self.judgeindex]
                self.bot.pubout(self.channel, "%s has quit the game." % user)
                self.live_players.remove(user)
                if len(self.live_players) < 3:
                    self.bot.pubout(self.channel, "There are now too few players to continue the game.")
                    self.endgame()
                else:
                    if self.judgeindex == len(self.live_players):
                        self.judgeindex = 0
                    if user == judge:
                        self.bot.pubout(self.channel, "The Card Czar is now %s." % self.live_players[self.judgeindex])
                        judge = self.live_players[self.judgeindex]
                        for i in range(0, len(self.playedcards)):
                            if self.playedcards[i-1][0] == judge:
                                self.playedcards.remove(self.playedcards[i-1])
                    else:
                      self.judgeindex = self.live_players.index(judge)  
                self.checkroundover()
            else:
                self.reply(channel, user, "You are not in this game.")
        elif self.gamestate == "Starting":
            if user in self.live_players:
                self.bot.pubout(self.channel, "%s has quit the game." % user)
                self.live_players.remove(user)
                if len(self.live_players) == 0:
                    self.bot.pubout(self.channel, "Game is now empty.")
                    self.endgame()
            else:
                self.reply(channel, user, "You are not in this game.")
        else:
            self.reply(channel, user, "There is no game in progress.")
            
    def cmd_del(self, args, channel, user):
        auth = self.bot.plugins['system.Auth']
        userlevel = auth.get_userlevel(user)
        if userlevel > 50:
            if self.gamestate == "InProgress" or self.gamestate == "Starting":
                try:
                    player = args[0]
                    if player in self.live_players:
                        judge = self.live_players[self.judgeindex]
                        self.bot.pubout(self.channel, "%s has quit the game." % player)
                        self.live_players.remove(player)
                        if len(self.live_players) < 3:
                            self.bot.pubout(self.channel, "There are now too few players to continue the game.")
                            self.endgame()
                        else:
                            if self.judgeindex == len(self.live_players):
                                self.judgeindex = 0
                            if player == judge:
                                self.bot.pubout(self.channel, "The Card Czar is now %s." % self.live_players[self.judgeindex])
                                judge = self.live_players[self.judgeindex]
                                for i in range(0, len(self.playedcards)):
                                    if self.playedcards[i][0] == judge:
                                        self.playedcards.remove(self.playedcards[i])
                                self.beginjudging()
                            else:
                              self.judgeindex = self.live_players.index(judge)  
                        self.checkroundover()
                    else:
                        self.reply(channel, user, "That player is not in this game.")
                except IndexError:
                    self.reply(channel, user, "Please specify the player to delete.")
            else:
                self.reply(channel, user, "There is no game in progress.")
        elif self.gamestate == "Starting":
            try:
                player = args[0]
                if player in self.live_players:
                    self.bot.pubout(self.channel, "%s has been deleted from the game." % player)
                    self.live_players.remove(player)
                    if len(self.live_players) == 0:
                        self.bot.pubout(self.channel, "Game is now empty.")
                        self.endgame()
                else:
                    self.reply(channel, user, "That player is not in this game.")
            except IndexError:
                self.reply(channel, user, "Please specify the player to delete.")
        else:
            self.reply(channel, user, "You need to be at least a botmod to use that command.")
            
    def cmd_end(self, args, channel, user):
        auth = self.bot.plugins['system.Auth']
        userlevel = auth.get_userlevel(user)
        if userlevel > 50:
            if self.gamestate is not "None":
                self.endgame()
            else:
                self.reply(channel, user, "There is no game in progress.")
        elif self.gamestate == "Starting":
            self.endgame()
        elif self.gamestate == "InProgress":
            self.reply(channel, user, "You need to be at least a botmod to use that command during a game.")
        elif self.gamestate == "None":
            self.reply(channel, user, "There is no game in progress.")

    def cmd_help(self, args, channel, user):
        cmds = [i[4:] for i in dir(self) if i.startswith('cmd_')]
        self.reply(channel, user, "Valid commands: '%s'" % "', '".join(cmds))

    def cmd_rules(self, args, channel, user):
        self.reply(channel, user, "Cards Against Humanity is a free party game for horrible people.")
        self.reply(channel, user, "Unlike most of the party games you've played before, Cards Against Humanity is as despicable and awkward as you and your friends.")
        self.reply(channel, user, "The game is simple. Each round, one player asks a question from a Black Card, and everyone else answers with their funniest White Card.")

    def do_command(self, channel, user, cmd):
        if cmd=='': return
        cmds = cmd.strip().split(" ")
        cmds[0]=cmds[0].lower()

        try:
            cmd_handler = getattr(self, "cmd_" + cmds[0])
        except AttributeError:
            cmd_handler = None

        if cmd_handler:
            cmd_handler(cmds[1:], channel, user)
            return
