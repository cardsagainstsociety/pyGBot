##
##    ContraHumanity - a plugin for pyGBot
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
##    The game implemented by this plugin is based on Cards Against Humanity,
##    licenced under Creative Commons BY-NC-SA 2.0. The cards used in
##    ContraHumanityCards.txt are directly from Cards Against Humanity.
##    Please see http://cardsagainsthumanity.com for more information
##    about the original game.

import string, random
from pyGBot.BasePlugin import BasePlugin
from time import time

# Enum definition
def enum(**enums):
    return type('Enum', (), enums)

class ContraHumanity(BasePlugin):
    def __init__(self, bot, options):
        # Plugin initialization
        BasePlugin.__init__(self, bot, options)
        self.output = True
        self.auth = self.bot.plugins["system.Auth"]
        
        # Define gamestates
        self.GameState = enum(none=0, starting=1, inprogress=2)
        
        # Define variants
        self.variants = {
            "packingheat": ["Draw an extra card before Pick-2 rounds", True],
            "playercards": ["Each player's name will be added as a white card.", True],
        }

        # Initialize game
        self.loadcards()
        self.resetdata()

    def timer_tick(self):
        # Handle time-based events
        if self.gamestate == self.GameState.inprogress:
            # Don't prompt if in judge delay
            if not self.judgestarttime:
                # Prompt delay
                self.timer = self.timer + 1
                if self.timer == 90:
                    self.timer = 0
                    # TODO: Make this a function, don't call a cmd
                    self.cmd_prompt([], self.channel, self.bot.nickname)
                
            # Judge start delay
            if self.judgestarttime and self.judgestarttime < time():
                self.beginjudging()
                self.judgestarttime = None

    def msg_channel(self, channel, user, message):
        # Determine if a message is a command, and handle it if so.
        a = string.split(message, ":", 1)
        if len(a) > 1 and a[0].lower() == self.bot.nickname.lower():
            self.do_command(channel, user, string.strip(a[1]))
        elif message[0]=='!' and (len(message) > 1) and message[1]!='!':
            self.do_command(channel, user, string.strip(message[1:]))

    def msg_private(self, user, message):
        # Attempt to run private messages as commands
        self.do_command(user, user, message)

    def reply(self, channel, user, text):
        # Send message to user in the same method they came in
        # (publicy or privately)
        if channel != user:
            self.bot.pubout(channel, "%s: %s" % (user, text))
        else:
            self.bot.noteout(user, text)

    def privreply(self, user, text):
        # Send message to user privately
        self.bot.noteout(user, text)
        
    def user_nickchange(self, old, new):
        # Update nick references when users change nicks
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

    def loadcards(self):
        # Empty decks
        self.baseblackdeck = []
        self.basewhitedeck = []
        
        # Load CaH cards
        with open('./pyGBot/Plugins/games/ContraHumanityCards.txt', 'r') as f:
            self.parsecardfile(f)
                        
        with open('./pyGBot/Plugins/games/ContraHumanityCustom.txt', 'r') as f:
            self.parsecardfile(f)
            
    def parsecardfile(self, f):
        for line in f:
            # Ignore comments and empty lines
            if not line.startswith("#") and not line == "\n":
                # Do we have a play definition?
                if line[1] == ":":
                    # This is a black card.
                    self.baseblackdeck.append([line[3:].rstrip("\n"), int(line[0])])
                else:
                    # This is a white card.
                    self.basewhitedeck.append(line.rstrip("\n"))

    def resetdata(self):
        # Initialize all game variables to new game values
        self.players = []
        self.live_players = []
        self.round_players = []
        self.hands = {}
        self.woncards = {}
        self.playedcards = {}
        self.timer = 0
        self.judgeindex = 0
        self.cardstowin = 0
        self.pot = 0
        self.channel = None
        self.blackcard = None
        self.judgestarttime = None
        self.judging = False
        self.gamestate = self.GameState.none
        
        # Load deck instances and shuffle
        self.blackdeck = list(self.baseblackdeck)
        random.shuffle(self.blackdeck)
        self.whitedeck = list(self.basewhitedeck)
        random.shuffle(self.whitedeck)

    def startgame(self):
        # Put the game into InProgress mode
        self.gamestate = self.GameState.inprogress
        self.bot.pubout(self.channel, "A new game is starting! Please wait, dealing cards...")
        
        # Copy players in starting queue to active queue, and shuffle play order
        self.players = list(self.live_players)
        random.shuffle(self.live_players)
        
        # Initialize player keyed data
        for user in self.live_players:
            self.woncards[user] = 0
            self.hands[user] = []
            # Add the user as a white card if playercards variant is on
            if self.variants["playercards"][1]:
                self.whitedeck.append(user)
                random.shuffle(self.whitedeck)
                
        # Deal initial hands to players
        for i in range(1, 11):
            for user in self.live_players:
                self.hands[user].append(self.whitedeck.pop(0))
                
        # Display hands to each player
        for user in self.live_players:
            self.showhand(user)
        # Determine cards to win
        if len(self.live_players) >= 8:
            self.cardstowin = 4
        else:
            self.cardstowin = 12 - len(self.live_players)
        
        # Start first round
        self.newround()

    def endgame(self):
        # Notify users
        self.bot.pubout(self.channel, "The game is over.")
        
        # Show black card counts if a game was in progress
        if self.gamestate == self.GameState.inprogress:
            blackbuild = []
            for user in self.players:
                if self.woncards[user] != 0:
                    blackbuild.append("%s - %i" % (user, self.woncards[user]))
            if blackbuild != []:
                self.bot.pubout(self.channel, "Black cards per players: %s" % ", ".join(blackbuild))
                
        # Reset game data
        self.resetdata()
        
    def newround(self):
        # Initialize round values
        self.judging = False
        self.timer = 0
        self.pot = 0
        # Output current game status
        self.showscores()
        
        # Determine card czar and output
        self.playedcards = []
        if self.judgeindex == len(self.live_players) - 1:
            self.judgeindex = 0
        else:
            self.judgeindex = self.judgeindex + 1
        self.bot.pubout(self.channel, "This round's Card Czar is \x02\x0312%s\x0F." % self.live_players[self.judgeindex])
        
        # Output black card, changing output for "Play" value
        self.blackcard = self.blackdeck.pop(0)
        if self.blackcard[1] == 1:
            self.bot.pubout(self.channel, "The new black card is: \"\x02\x0303%s\x0F\" Please play ONE card from your hand using '!play <number>'." % (self.blackcard[0]))
        elif self.blackcard[1] == 2:
            self.bot.pubout(self.channel, "The new black card is: \"\x02\x0303%s\x0F\" Please play TWO cards from your hand, in desired order, using '!play <number> <number>'." % (self.blackcard[0]))
        elif self.blackcard[1] == 3:
            self.bot.pubout(self.channel, "The new black card is: \"\x02\x0303%s\x0F\" Please play THREE cards from your hand, in desired order, using '!play <number> <number> <number>'." % (self.blackcard[0]))
        
        # Refresh player's hands
        self.deal()
        
    def checkroundover(self):
        # Cancel delay until judging starts
        if self.judgestarttime:
            self.judgestarttime = None
            self.bot.pubout(self.channel, "Judging delay has been reset or cancelled...")
            
        # Generate a list of players that have played their cards
        played = []
        for card in self.playedcards:
            played.append(card[0])
        
        # Find who is in live_players but hasn't played a card
        diff = list(set(self.live_players) - set(played))

        # Begin judging if all live players except judge have played
        if len(diff) == 1 and diff[0] == self.live_players[self.judgeindex]:
            self.bot.pubout(self.channel, "All cards have been played. Judging will begin after a short delay.")
            if not self.judging:
                self.judgestarttime = time() + 10
            
    def beginjudging(self):        
        # Begin the judging process
        # TODO: Possible bug when a judge quits after new player(s) have
        # joined during judging, allowing those player(s) to play that round
        if self.judging == False:
            self.judging = True
            # Restart prompt timer
            self.timer = 0
            
            # Output cards and ask judge to make selection
            self.bot.pubout(self.channel, "Black card is: \"\x02\x0303%s\x0F\"" % self.blackcard[0])
            random.shuffle(self.playedcards)
            if self.blackcard[0].find("____") == -1:
                for i in range (0, len(self.playedcards)):
                    self.bot.pubout(self.channel, "%i. \x0304%s\x0F" % (i+1, " / ".join(self.playedcards[i][1:][0])))
            else:
                for i in range(0, len(self.playedcards)):
                    self.bot.pubout(self.channel, "%i. %s" % (i+1, self.blackcard[0].replace("____", "\x0304%s\x0F") % tuple(self.playedcards[i][1:][0])))
            self.bot.pubout(self.channel, "\x02\x0312%s\x0F: Please make your decision now using the '!pick <number>' command." % self.live_players[self.judgeindex])
        
    def cardwin(self, winningcard):
        # Output the winner, and store the card in their list slot
        winner = self.playedcards[winningcard][0]
        self.bot.pubout(self.channel, "The Card Czar picked \"\x0304%s\x0F\"! \x02\x0312%s\x0F played that, and gets an Awesome Point." % (" / ".join(self.playedcards[winningcard][1:][0]), winner))
        self.woncards[winner] = self.woncards[winner] + 1
        
        # Add the pot
        if self.pot > 0:
            self.woncards[winner] = self.woncards[winner] + self.pot
            self.bot.pubout(self.channel, "%s also won %i Awesome Point(s) from the pot!" % (winner, self.pot))
        
        # Check if the game is over, and start a new round
        if not self.checkgamewin():
            self.newround()
        
    def checkgamewin(self):
        # Does any player have enough cards to win?
        for user in self.players:
            if self.woncards[user] >= self.cardstowin:
                # We have a winner!
                self.bot.pubout(self.channel, "%s now has %i Awesome Points. %s wins!" % (user, self.woncards[user], user))
                # End the game
                self.endgame()
                return True
        
        # Are we out of black cards?
        if len(self.blackdeck) == 0:
            # Uh oh!
            self.bot.pubout(self.channel, "There are no more black cards. The game is over!")
            self.endgame()
            return True
            
        # Nope and nope.
        else:
            return False

    def deal(self):
        # TODO: change this into a one-user function, it's becoming redundant elsewhere
        
        # Determine how many extra cards players get (if any)
        extra = 0
        if self.blackcard[1] == 3:
            extra = 2
        if self.blackcard[1] == 2 and self.variants["packingheat"][1]:
            extra = 1
            
        # Draw up to the hand limit for each player
        for user in self.live_players:
            if user != self.live_players[self.judgeindex]:
                while len(self.hands[user]) < 10 + extra:
                    self.hands[user].append(self.whitedeck.pop(0))
                    self.privreply(user, "You draw: \x0304%s\x0F." % (self.hands[user][len(self.hands[user])-1]))
                    
        # Full hand output to each player
        for user in self.live_players:
            self.showhand(user)
            
    def showhand(self, user):
        if user != self.live_players[self.judgeindex]:
            hand = []
            for i in range (0, len(self.hands[user])):
                hand.append("%i: \x0304%s\x0F" % (i + 1, self.hands[user][i]))
            self.privreply(user, "Your hand: %s" % ", ".join(hand))
                
    def showscores(self):
        if self.gamestate == self.GameState.inprogress:
            blackbuild = []
            for player in self.players:
                if self.woncards[player] != 0:
                    blackbuild.append("%i - %s" % (self.woncards[player], player))
            blackbuild.sort(reverse=True)
            if blackbuild != []:
                self.bot.pubout(self.channel, "Awesome Points per players: %s. Points to win: %i." % (", ".join(blackbuild), self.cardstowin))
            else:
                self.bot.pubout(self.channel, "No scores yet. Cards to win: %i." % self.cardstowin)
            if self.pot > 0:
                self.bot.pubout(self.channel, "There are %i Awesome Point(s) in the pot! Winner takes all." % self.pot)
        else:
            self.reply(channel, user, "No game in progress.")
            
    def removeuser(self, user):
        # If we're here, we're gonna remove them, so let's save repeating this line.
        self.bot.pubout(self.channel, "%s is no longer in the game." % user)
        
        # Game in progress handles differently than one in setup
        if self.gamestate == self.GameState.inprogress:
            # End the game if there are too few users to handle a quit
            if len(self.live_players) < 4:
                self.bot.pubout(self.channel, "There are now too few players to continue the game.")
                self.endgame()
            else:
                # Store the current judge before modifying player lists
                judge = self.live_players[self.judgeindex]
                # Remove the user
                self.live_players.remove(user)
                
                # Overlap the judge index if necessary
                if self.judgeindex == len(self.live_players):
                    self.judgeindex = 0
                
                # Change the judge if necessary
                if user == judge:
                    # Stop judging
                    self.judging = False
                    
                    # Figure out the new judge
                    self.bot.pubout(self.channel, "The Card Czar is now %s." % self.live_players[self.judgeindex])
                    judge = self.live_players[self.judgeindex]
                    
                    # Remove the new judge's played cards
                    for i in range(0, len(self.playedcards)):
                        # IndexError comes up if we delete anything but the last card;
                        # using try/catch for future expansion (with gambling, may require
                        # deletion of multiple cards)
                        try:
                            if self.playedcards[i][0] == judge:
                                self.playedcards.remove(self.playedcards[i])
                        except IndexError:
                            pass
                            
                    # Restart judging
                    self.checkroundover()
                else:
                    # Reassign the current judge to their new index
                    self.judgeindex = self.live_players.index(judge)
                    
                    # Don't interrupt judging in progress
                    if not self.judging:
                        self.checkroundover()

        elif self.gamestate == self.GameState.starting:
            # Remove the user
            self.live_players.remove(user)
            
            # End the game if it's empty
            if len(self.live_players) == 0:
                self.bot.pubout(self.channel, "Game is now empty.")
                self.endgame()
        
    def cmd_play(self, args, channel, user):
        # Ensure game is running
        if self.gamestate == self.GameState.inprogress:
            # Ignore the extra args
            args = args[:self.blackcard[1]]
            # Get player's played card status
            cardplayed = self.checkplayedcard(user)
            
            # Ensure player can play
            if user in self.live_players and user != self.live_players[self.judgeindex] and \
                self.judging == False and not cardplayed and len(args) >= self.blackcard[1] and \
                len(args) == len(set(args)):

                try:
                    # Replace args with int versions
                    for i in range (0, self.blackcard[1]):
                        args[i] = int(args[i]) - 1
                except ValueError:
                    # End function, no output
                    return
                
                # Ensure all cards are within range
                for arg in args:
                    if arg not in range(0, len(self.hands[user])):
                        
                        self.reply(channel, user, "You can't play a card you don't have.")
                        return
                
                # Actually insert the cards
                playcards = []
                for card in args:
                    playcards.append(self.hands[user][card])
                self.playedcards.append([user, playcards])
                
                # Remove the cards from the player's hand
                for card in playcards:
                    self.hands[user].remove(card)
                    
                # Output to user and check if the round is over
                if self.blackcard[1] == 1:
                    self.bot.pubout(self.channel, "%s: You have played your card." % user)
                else:
                    self.bot.pubout(self.channel, "%s: You have played your cards." % user)
                self.checkroundover()
                
            # Send output based on error conditions
            elif user not in self.live_players:
                self.reply(channel, user, "You are not in this game.")
            elif user in self.playedcards:
                self.reply(channel, user, "You have already played a card this round.")
            elif user == self.live_players[self.judgeindex]:
                self.reply(channel, user, "You are Card Czar this round.")
            elif self.judging == True:
                self.reply(channel, user, "Judging has already begun, wait for the next round.")
            elif len(args) < self.blackcard[1]:
                self.reply(channel, user, "Not enough cards! Play %i." % self.blackcard[1])
            elif len(args) != len(set(args)):
                self.reply(channel, user, "You can't play the same card more than once.")
            elif cardplayed:
                self.reply(channel, user, "You have already played your card(s) this round.")
        else:
            self.reply(channel, user, "There is no game in progress.")

    def cmd_gamble(self, args, channel, user):
        # Ensure game is running
        if self.gamestate == self.GameState.inprogress:
            # Ignore the extra args
            args = args[:self.blackcard[1]]
            # Get player's played card status
            cardplayed = self.checkplayedcard(user)
            
            # Ensure player can gamble
            if user in self.live_players and user != self.live_players[self.judgeindex] and \
                self.judging == False and cardplayed and len(args) >= self.blackcard[1] and \
                len(args) == len(set(args)) and self.woncards[user] > 0:

                try:
                    # Replace args with int versions
                    for i in range (0, self.blackcard[1]):
                        args[i] = int(args[i]) - 1
                except ValueError:
                    # End function, no output
                    return
                
                # Ensure all cards are within range
                for arg in args:
                    if arg not in range(0, len(self.hands[user])):
                        self.reply(channel, user, "You can't play a card you don't have!")
                        return
                
                # Actually insert the cards
                playcards = []
                for card in args:
                    playcards.append(self.hands[user][card])
                self.playedcards.append([user, playcards])
                
                # Remove the cards from the player's hand
                for card in playcards:
                    self.hands[user].remove(card)
                    
                # Put a black card into the pot
                self.woncards[user] = self.woncards[user] - 1
                self.pot = self.pot + 1
                    
                # Output to user and check if the round is over
                self.bot.pubout(self.channel, "%s: You have gambled an Awesome Point for an additional play. There are now %i points in the pot!" % (user, self.pot))
                self.checkroundover()
                
            # Send output based on error conditions
            elif user not in self.live_players:
                self.reply(channel, user, "You are not in this game.")
            elif user in self.playedcards:
                self.reply(channel, user, "You have already played a card this round.")
            elif user == self.live_players[self.judgeindex]:
                self.reply(channel, user, "You are Card Czar this round.")
            elif self.judging == True:
                self.reply(channel, user, "Judging has already begun, wait for the next round.")
            elif len(args) < self.blackcard[1]:
                self.reply(channel, user, "Not enough cards! Play %i." % self.blackcard[1])
            elif len(args) != len(set(args)):
                self.reply(channel, user, "You can't play the same card more than once.")
            elif not cardplayed:
                self.reply(channel, user, "You cannot gamble until you have already played.")
            elif self.woncards[user] == 0:
                self.reply(channel, user, "You must have at least one Awesome Point to gamble.")
        else:
            self.reply(channel, user, "There is no game in progress.")
                
    def checkplayedcard(self, user):
        # Returns True if user has played a card, False otherwise
        for cards in self.playedcards:
            if cards[0] == user:
                return True
        return False

    def cmd_pick(self, args, channel, user):
        # Command to pick a card
        # TODO: Maybe restructure this one too.
        if self.gamestate == self.GameState.inprogress:
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
        # Start the game!
        if self.gamestate == self.GameState.none:
            self.gamestate = self.GameState.starting
            self.bot.pubout(channel, "A new game has been started!")
            self.live_players.append(user)
            self.channel = channel
        elif self.gamestate == self.GameState.starting:
            if user in self.live_players and len(self.live_players) >= 3:
                self.startgame()
            elif user not in self.live_players:
                self.reply(channel, user, "There is a game starting already. Please join instead.")
            else:
                self.reply(channel, user, "Not enough players to start a game. Minimum of 3 required. Currently: %i" % len(self.live_players))
        elif self.gamestate == self.GameState.inprogress:
            self.reply(channel, user, "There is a game in progress. Please wait for it to end.")

    def cmd_status(self, args, channel, user):
        # Display status
        if self.gamestate == self.GameState.none:
            self.reply(channel, user, "No game in progress.")
        elif self.gamestate == self.GameState.starting:
            self.reply(channel, user, "A new game is starting. Currently %i players: %s" % (len(self.live_players), ", ".join(self.live_players)))
        elif self.gamestate == self.GameState.inprogress:
            self.bot.pubout(self.channel, "Player order: %s. %s is the current Card Czar. Current black card is: \x0303%s\x0F" % (", ".join(self.live_players), self.live_players[self.judgeindex], self.blackcard[0]))
            self.showscores()
                
    def cmd_stats(self, args, channel, user):
        # Alias to 'stats'
        self.cmd_status(args, channel, user)

    def cmd_scores(self, args, channel, user):
        # Display scores
        self.showscores()

    def cmd_join(self, args, channel, user):
        # Join the game
        # TODO: Maybe restructure this mess too.
        if self.gamestate == self.GameState.none:
            self.reply(channel, user, "No game in progress. Please start one.")
        elif self.gamestate == self.GameState.starting:
            if user not in self.live_players:
                self.live_players.append(user)
                self.bot.pubout(self.channel, "%s is now in the game." % user)
            else:
                self.reply(channel, user, "You are already in the game.")
        elif self.gamestate == self.GameState.inprogress:
            # TODO: Fix bug where players always get 10 cards, even in packingheat + 2 or 3 play
            if user not in self.live_players:
                self.bot.pubout(self.channel, "%s is now in the game." % user)
                if user not in self.players:
                    self.players.append(user)
                    if self.variants["playercards"][1]:
                        self.whitedeck.append(user)
                        random.shuffle(self.whitedeck)                        
                if user not in self.woncards:
                    self.woncards[user] = 0
                self.live_players.insert(self.judgeindex, user)
                self.judgeindex = self.judgeindex + 1
                if user not in self.hands:
                    self.hands[user] = []
                    for i in range(1, 11):
                        self.hands[user].append(self.whitedeck.pop(0))
                else:
                    while len(self.hands[user]) < 9 + self.blackcard[1]:
                        self.hands[user].append(self.whitedeck.pop(0))
                # Show them their hand
                self.showhand(user)
                # Delay judging if necessary
                self.checkroundover()
            else:
                self.reply(channel, user, "You are already in the game.")

    def cmd_hand(self, args, channel, user):
        # Output hand
        if self.gamestate == self.GameState.inprogress:
            if user in self.live_players:
                self.showhand(user)
        else:
            self.reply(channel, user, "There is no game in progress.")

    def cmd_prompt(self, args, channel, user):
        # Prompt players to draw cards
        # Should probably move this logic so the bot doesn't call commands
        if self.gamestate == self.GameState.inprogress:
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
        # Lets a player quit the game
        if self.gamestate == self.GameState.none:
            # Game is not running.
            self.reply(channel, user, "There is no game in progress.")
        else:
             # Game is running; delete them if they're in the game
            if user in self.live_players:
                self.removeuser(user)
            else:
                self.reply(channel, user, "You are not in this game.")
            
    def cmd_del(self, args, channel, user):
        # TODO: Can we make this more readable?
        userlevel = self.auth.get_userlevel(user)
        if userlevel > 50:
            if self.gamestate == self.GameState.inprogress or self.gamestate == self.GameState.starting:
                try:
                    player = args[0]
                    if player in self.live_players:
                        self.removeuser(player)
                    else:
                        self.reply(channel, user, "That player is not in this game.")
                except IndexError:
                    self.reply(channel, user, "Please specify the player to delete.")
            else:
                self.reply(channel, user, "There is no game in progress.")
        elif self.gamestate == self.GameState.starting:
            try:
                player = args[0]
                if player in self.live_players:
                    self.removeuser(player)
                else:
                    self.reply(channel, user, "That player is not in this game.")
            except IndexError:
                self.reply(channel, user, "Please specify the player to delete.")
        else:
            self.reply(channel, user, "You need to be at least a botmod to use that command.")
            
    def cmd_end(self, args, channel, user):
        # End the game
        userlevel = self.auth.get_userlevel(user)
        if userlevel > 50:
            if self.gamestate is not self.GameState.none:
                self.endgame()
            else:
                self.reply(channel, user, "There is no game in progress.")
        elif self.gamestate == self.GameState.starting:
            self.endgame()
        elif self.gamestate == self.GameState.inprogress:
            self.reply(channel, user, "You need to be at least a botmod to use that command during a game.")
        elif self.gamestate == self.GameState.none:
            self.reply(channel, user, "There is no game in progress.")

    def cmd_help(self, args, channel, user):
        # Output all commands
        cmds = [i[4:] for i in dir(self) if i.startswith('cmd_')]
        self.reply(channel, user, "Valid commands: '%s'" % "', '".join(cmds))

    def cmd_rules(self, args, channel, user):
        # Output a simple rules list
        self.reply(channel, user, "Contrahumanity is an implementation of Cards Against Humanity, a free party game for horrible people.")
        self.reply(channel, user, "Unlike most of the party games you've played before, Cards Against Humanity is as despicable and awkward as you and your friends.")
        self.reply(channel, user, "The game is simple. Each round, one player asks a question from a Black Card, and everyone else answers with their funniest White Card.")
        
    def cmd_variant(self, args, channel, user):
        # Manage variants
        # TODO: Take a look at this, see if I can simplify it
        for i in range (0, len(args)):
            args[i] = args[i].lower()
        if len(args) == 0:
            varstring = ""
            for variant in self.variants.keys():
                varstring = varstring + variant.title() + ": " + ("On" if self.variants[variant][1] else "Off") + ", "
            varstring = varstring[:len(varstring) - 2]
            self.reply(channel, user, "Current variants: %s" % varstring)
        if len(args) == 1:
            if args[0] in self.variants.keys():
                self.reply(channel, user, "%s: %s" % (args[0].title(), self.variants[args[0]][0]))
        if len(args) == 2:
            if self.gamestate != self.GameState.inprogress:
                if args[0] == "toggle": 
                    if args[1] in self.variants.keys():
                        if self.variants[args[1]][1]:
                            self.variants[args[1]][1] = False
                            self.reply(channel, user, "%s is now deactivated." % args[1].title())
                        else:
                            self.variants[args[1]][1] = True
                            self.reply(channel, user, "%s is now activated." % args[1].title())
                else:
                    self.reply(channel, user, "Syntax: 'variants toggle <variant>'")
            else:
                self.reply(channel, user, "Cannot modify variants during a game.")

    def cmd_reloadcards(self, args, channel, user):
        # Reload card lists
        userlevel = self.auth.get_userlevel(user)
        # If admin, reload cards. Else, do nothing.
        if userlevel == 200:
            self.loadcards()
            self.reply(channel, user, "Successfully reloaded base decks.")
        else:
            self.reply(channel, user, "You do not have permission to do that.")

    def do_command(self, channel, user, cmd):
        # Handle commands
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
