# coding: utf-8
##
##      CardsAgainstSociety - a plugin for pyGBot
##      Copyright (C) 2008 Morgan Lokhorst-Blight
##
##      This program is free software: you can distribute it and/or modify
##      it under the terms of the GNU General Public License as published by
##      the Free Software Foundation, either version 3 of the License, or
##      (at your option) any later version.
##
##      This program is distributed in the hope that it will be useful,
##      but WITHOUT ANY WARRANTY; without even the implied warranty of
##      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##      GNU General Public License for more details.
##
##      You should have received a copy of the GNU General Public License
##      along with this program.  If not, see <http://www.gnu.org/licenses/>.
##
##      The game implemented by this plugin is based on Cards Against Humanity,
##      licenced under Creative Commons BY-NC-SA 2.0. Some of the cards used by this plugin
##      are directly from Cards Against Humanity. Some are from Pretend You're XYZZY
##      (https://github.com/ajanata/PretendYoureXyzzy), a CAH clone. Some cards
##      have been edited, and some are new creations. 

##      Please see http://cardsagainsthumanity.com for more information
##      about the original game.

import string
import random
import re
import os
from urllib import urlopen
from time import time
from pyGBot.BasePlugin import BasePlugin
from collections import Set, defaultdict


def enum(**enums):
    return type('Enum', (), enums)


def get_wiki_featured_article_titles(n=7):
    feat_feed_uri = (
        "http://en.wikipedia.org/w/api.php?"
        "action=featuredfeed&feed=featured&feedformat=atom")

    feat_title_re = re.compile(
        ".+title=&quot;(.+?)&quot;"
        "&gt;(&lt;b&gt;)?"
        "Full(&amp;#160;)? ?article.+")

    entry_start_re = re.compile(
        "\s*<entry.+")

    entry_end_re = re.compile(
        "\s*</entry>")

    summary_start_re = re.compile(
        "\s*<summary.+")

    summary_end_re = re.compile(
        "\s*</summary>")

    scanning = True
    in_entry = False
    in_summary = False
    feed = urlopen(feat_feed_uri)
    titles = []
    for line in feed.readlines():
        if not scanning:
            if re.match(entry_end_re, line):
                in_entry = False
                scanning = True
            continue
        if not in_entry:
            if re.match(entry_start_re, line):
                in_entry = True
            continue
        if not in_summary:
            if re.match(summary_start_re, line):
                in_summary = True
            continue
        title_match = re.match(feat_title_re, line)
        if title_match:
            title = title_match.groups()[0]
            if title not in titles:
                titles.append(title)
                scanning = False
        if re.match(summary_end_re, line):
            in_summary = False
        if re.match(entry_end_re, line):
            in_entry = False
        if len(titles) == n:
            break
    feed.close()
    return titles


class Subs(string.Formatter):
    def __init__(self, subfile):
        from random import Random
        self.randomizer = Random()
        with open(subfile, 'r') as f:
            from json import load
            subs = load(f)
            self.subs = subs["vars"]
            self.gendered_vars = subs["gendered_keys"]
        self.gender = 'n'
        self.fallback_gender = 'f'

    def __len__(self):
        return len(self.subs)

    def get_value(self, k, args, kwargs):
        upper = k[0] in string.uppercase
        k = k.lower()
        if k in self.gendered_vars:
            try:
                return self.randomizer.choice(
                    self.subs[k][self.gender])
            except KeyError:
                r = self.randomizer.choice(
                    self.subs[k][self.fallback_gender])
        else:
            r = self.randomizer.choice(self.subs[k])
        if upper:
            return r.capitalize()
        else:
            return r

    def format(self, format_string, *args, **kwargs):
        self.gender = self.randomizer.choice(['n', 'f', 'm'])
        self.fallback_gender = self.randomizer.choice(['m', 'f'])
        return super(Subs, self).format(format_string, *args, **kwargs)


class MetaDeck(Set):
    def __init__(self):
        self.decks = defaultdict(set)
        self.decks_enabled = set()

    def __contains__(self, o):
        for (k, v) in self.decks.iteritems():
            if k in self.decks_enabled:
                if o in v:
                    return True
        return False

    def __iter__(self):
        for (k, v) in self.decks.iteritems():
            if k in self.decks_enabled:
                for w in v:
                    yield w

    def __len__(self):
        return sum(len(v) for (k, v) in self.decks.iteritems()
                   if k in self.decks_enabled)


class CardsAgainstSociety(BasePlugin):
    def __init__(self, bot, options):
        # Plugin initialization
        BasePlugin.__init__(self, bot, options)
        self.output = True
        self.auth = self.bot.plugins["system.Auth"]

        # Define gamestates
        self.GameState = enum(none=0, starting=1, inprogress=2)

        # Define variants
        self.variants = {
            "packingheat":
            ["Draw an extra card before Pick-2 rounds", True],
            "playercards":
            ["Each player's name will be added as a white card.", True],
            "rando":
            ["Adds an AI player that randomly picks cards.", True],
            "wikifeature":
            ["The titles of the past week's "
             "featured articles on Wikipedia are white cards.", False]
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

            # # Update idle times and kick idle players
            # for player in self.idle_players.keys():
            #     if player in self.live_players:
            #         self.idle_players[player] = self.idle_players[player] + 1
            #         if self.idle_players[player] > 300:
            #             self.bot.pubout(self.channel, player +
            #                             " has been idle too long.")
            #             self.removeuser(player)
            #     else:
            #         del self.idle_players[player]

    def msg_channel(self, channel, user, message):
        # Update idle time
        if user in self.live_players:
            self.idle_players[user] = 0

        # Determine if a message is a command, and handle it if so.
        a = string.split(message, ":", 1)

        if len(a) > 1 and a[0].lower() == self.bot.nickname.lower():
            self.do_command(channel, user, string.strip(a[1]))
        elif message[0] == '!' and (len(message) > 1) and message[1] != '!':
            self.do_command(channel, user, string.strip(message[1:]))

    def msg_private(self, user, message):
        # Update idle time
        if user in self.live_players:
            self.idle_players[user] = 0

        # Attempt to run private messages as commands
        self.do_command(user, user, message)

    def reply(self, channel, user, text):
        # Send message to user in the same method they came in
        # (publicy or privately)
        if channel != user:
            self.bot.pubout(channel, "{}: {}".format(user, text))
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
            if old in map_:
                map_[new] = map_[old]
                del map_[old]

    def loadcards(self):
        # Empty decks
        self.baseblackdeck = MetaDeck()
        self.basewhitedeck = MetaDeck()

        # Cards in the cardlists not to add to the deck.
        self.blacklist = set()
        try:
            blaf = open('./pyGBot/Plugins/games/CardsAgainstSocietyBlacklist.txt',
                        'r')
            self.blacklist_cards(*blaf.readlines())
            blaf.close()
        except (OSError, IOError) as ex:
            print("Error while loading blacklist")
            print(ex)

        # Variable substitutions.
        self.subs = Subs('./pyGBot/Plugins/games/CardsAgainstSocietyVars.json')

        # Load CaH cards
        olddir = os.path.abspath(os.curdir)
        os.chdir('./pyGBot/Plugins/games/CardsAgainstSocietyCards')
        for fn in os.listdir(os.curdir):
            if fn[-3:] == 'txt':
                with open(fn, 'r') as f:
                    self.parsecardfile(f)
        os.chdir(olddir)

        # Which cards should be actually in play?
        # Don't do this after the initial startup;
        # it'd be dumb to have to keep disabling the base deck
        # whenever you replace it.
        if self.baseblackdeck.decks_enabled:
            return
        with open('./pyGBot/Plugins/games/CardsAgainstSocietyDeckList.txt',
                  'r') as decklist:
            for deck in decklist.readlines():
                self.enable_deck(deck.strip())

    def write_decklist(self):
        with open('./pyGBot/Plugins/games/CardsAgainstSocietyDeckList.txt',
                  'w') as decklist:
            for deck in self.baseblackdeck.decks_enabled:
                decklist.write(deck+'\n')

    def enable_deck(self, deck):
        if (deck not in self.baseblackdeck.decks and
            deck not in self.basewhitedeck.decks):
            raise ValueError("I don't have the '{}' deck. "
                             "If you're sure it exists, do !loadcards"
                             .format(deck))
        self.baseblackdeck.decks_enabled.add(deck)
        self.basewhitedeck.decks_enabled.add(deck)
        self.write_decklist()

    def disable_deck(self, deck):
        self.baseblackdeck.decks_enabled.remove(deck)
        self.basewhitedeck.decks_enabled.remove(deck)
        self.write_decklist()

    def toggle_deck(self, deck):
        try:
            self.disable_deck(deck)
        except KeyError:
            self.enable_deck(deck)

    def parsecardfile(self, f):
        for line in f:
            # Special case: escape percent signs
            line.replace("%", "%%")
            # Ignore comments and empty lines
            if not line.startswith("#") and not line == "\n":
                # Do we have a play definition?
                if line[1] == ":":
                    # This is a black card.
                    self.baseblackdeck.decks[f.name].add(
                        (''.join(char for char in line[3:].rstrip("\n")
                                 if ord(char) < 128), int(line[0])))
                else:
                    # This is a white card.
                    self.basewhitedeck.decks[f.name].add(
                        ''.join(char for char in line.rstrip("\n.")
                                if ord(char) < 128))

    def initvars(self):
        self.players = []
        self.live_players = []
        self.round_players = []
        self.idle_players = {}
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

    def resetdata(self):
        # Initialize all game variables to new game values
        self.initvars()

        # Load deck instances and shuffle
#        cardlog = open('card.log', 'w')
#        cardlog.write('Blacklist:\n')
        self.resetdecks()

    def resetdecks(self):
        self.blackdeck = []
        for card in self.baseblackdeck:
            if card[0] not in self.blacklist:
                self.blackdeck.append(
                    (self.subs.format(card[0]),) + card[1:])
#            else:
#                cardlog.write(card[0] + '\n')
        random.shuffle(self.blackdeck)
        self.whitedeck = []
        for card in self.basewhitedeck:
            if card not in self.blacklist:
                self.whitedeck.append(self.subs.format(card))
#            else:
#                cardlog.write(card + '\n')
        if self.variants["wikifeature"][1]:
            self.whitedeck.extend(get_wiki_featured_article_titles())
        random.shuffle(self.whitedeck)
#        cardlog.write("\n\nBlack cards:\n")
#        for card in self.blackdeck:
#            cardlog.write(card[0] + '\n')
#        cardlog.write("\n\nWhite cards:\n")
#        for card in self.whitedeck:
#            cardlog.write(card + '\n')
#        cardlog.close()

    def startgame(self):
        # Put the game into InProgress mode
        self.resetdecks()
        self.gamestate = self.GameState.inprogress
        self.bot.pubout(
            self.channel,
            "A new game is starting! Please wait, dealing cards...")

        # Copy players in starting queue to active queue, and shuffle
        # play order
        self.players = list(self.live_players)
        random.shuffle(self.live_players)

        # Initialize player keyed data
        for user in self.live_players:
            self.idle_players[user] = 0
            self.woncards[user] = 0
            self.hands[user] = []
            # Add the user as a white card if playercards variant is on
            if self.variants["playercards"][1]:
                self.whitedeck.append(user)
                random.shuffle(self.whitedeck)

        # Initialize Rando
        if self.variants["rando"][1]:
            self.woncards["Rando Cardrissian"] = 0

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
                    blackbuild.append("{} - {}".format(
                        user, self.woncards[user]))
            if blackbuild != []:
                self.bot.pubout(
                    self.channel,
                    "Black cards per players: {}".format(
                        ", ".join(blackbuild)))
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
        self.bot.pubout(
            self.channel,
            "This round's Card Czar is \x02\x0312{}\x0F.".format(
                self.live_players[self.judgeindex]))

        # Output black card, changing output for "Play" value
        self.blackcard = self.blackdeck.pop(0)
        if self.blackcard[1] == 1:
            self.bot.pubout(
                self.channel,
                "\"\x02\x0303{}\x0F\" Please play ONE card from your hand "
                "using '!play <number>'.".format(self.blackcard[0]))
        elif self.blackcard[1] == 2:
            self.bot.pubout(
                self.channel,
                "\"\x02\x0303{}\x0F\" Please play TWO cards from your hand, "
                "in desired order, using '!play <number> <number>'.".format(
                    self.blackcard[0]))
        elif self.blackcard[1] == 3:
            self.bot.pubout(
                self.channel,
                "\"\x02\x0303{}\x0F\" Please play THREE cards from your hand, "
                "in desired order, using "
                "'!play <number> <number> <number>'.".format(
                    self.blackcard[0]))

        # Refresh player's hands
        self.deal()

    def checkroundover(self):
        # Cancel delay until judging starts
        if self.judgestarttime:
            self.judgestarttime = None
            self.bot.pubout(
                self.channel,
                "Judging delay has been reset or cancelled...")

        # Generate a list of players that have played their cards
        played = []
        for card in self.playedcards:
            played.append(card[0])

        # Find who is in live_players but hasn't played a card
        diff = list(set(self.live_players) - set(played))

        # Begin judging if all live players except judge have played
        if len(diff) == 1 and diff[0] == self.live_players[self.judgeindex]:
            self.bot.pubout(
                self.channel,
                "All cards have been played. Judgment is imminent. "
                "!gamble now, or forever hold your peace.")
            if not self.judging:
                self.judgestarttime = time() + 20

    def beginjudging(self):
        # Begin the judging process
        # TODO: Possible bug when a judge quits after new player(s) have
        # joined during judging, allowing those player(s) to play that round
        if not self.judging:
            self.judging = True
            # Restart prompt timer
            self.timer = 0

            # Rando Cardissian! (add a random card)
            if self.variants["rando"][1]:
                playcards = []
                # make sure there are enough cards to add
                if len(self.whitedeck) >= self.blackcard[1]:
                    for i in range(0, self.blackcard[1]):
                        playcards.append(self.whitedeck.pop(0))
                    self.playedcards.append(
                        ["Rando Cardrissian", playcards])

            # Output cards and ask judge to make selection
            self.bot.pubout(
                self.channel,
                "Black card is: \"\x02\x0303{}\x0F\"".format(
                    self.blackcard[0]))
            random.shuffle(self.playedcards)
            blanks = re.findall("_+", self.blackcard[0])
            if len(blanks) == 0:
                for i in range(0, len(self.playedcards)):
                    self.bot.pubout(
                        self.channel,
                        "{}. \x0304{}\x0F".format(
                            i+1,
                            " / ".join(self.playedcards[i][1:][0])))
            else:
                black_card_fmtstr = self.blackcard[0]
                for blank in blanks:
                    black_card_fmtstr = black_card_fmtstr.replace(
                        blank, "\x0304{}\x0F")
                for i in xrange(0, len(self.playedcards)):
                    self.bot.pubout(
                        self.channel,
                        "{}. {}".format(
                            i+1,
                            black_card_fmtstr.format(
                                *self.playedcards[i][1:][0])))
            self.bot.pubout(
                self.channel,
                "\x02\x0312{}\x0F: "
                "Please make your decision now using the "
                "'!pick <number>' command.".format(
                    self.live_players[self.judgeindex]))

    def cardwin(self, winningcard):
        # Output the winner, and store the card in their list slot
        winner = self.playedcards[winningcard][0]
        if winner == "Rando Cardrissian":
            self.bot.pubout(
                self.channel,
                "{} picked \"\x0304{}\x0F\"! "
                "\x02\x0312{}\x0F played that, "
                "and gets an Awesome Point. Shame on you.".format(
                    self.last_picker,
                    self.playedcards[winningcard][1:][0][0],
                    winner))
        else:
            self.bot.pubout(
                self.channel,
                "{} picked \"\x0304{}\x0F\"! "
                "\x02\x0312{}\x0F played that, "
                "and gets an Awesome Point.".format(
                    self.last_picker,
                    self.playedcards[winningcard][1:][0][0],
                    winner))
        self.woncards[winner] = self.woncards[winner] + 1

        # Add the pot
        if self.pot > 0:
            self.woncards[winner] = self.woncards[winner] + self.pot
            self.bot.pubout(
                self.channel,
                "{} also won {} Awesome Point(s) from the pot!".format(
                    winner,
                    self.pot))

        # Check if the game is over, and start a new round
        if not self.checkgamewin():
            self.newround()

    def checkgamewin(self):
        # Does any player have enough cards to win?
        def announce_winner(winner):
                self.bot.pubout(
                    self.channel,
                    "{} now has {} Awesome Points. {} wins!".format(
                        winner,
                        self.woncards[winner],
                        winner))
                # Is it Rando?
                if winner == "Rando Cardrissian":
                    self.bot.pubout(
                        self.channel,
                        "You all go home in everlasting shame.")

        for user in self.players:
            if self.woncards[user] >= self.cardstowin:
                # We have a winner!
                announce_winner(user)
                # End the game
                self.endgame()
                return True
        # Are we out of black cards?
        if len(self.blackdeck) == 0:
            # Uh oh!
            self.bot.pubout(
                self.channel,
                "There are no more black cards.")
            (winner, winner_points) = ("", 0)
            for (user, user_points) in self.woncards.iteritems():
                if user_points > winner_points:
                    (winner, winner_points) = (user, user_points)
            announce_winner(winner)
            self.endgame()
            return True

        # Nope and nope.
        else:
            return False

    def deal(self):
        # TODO: change this into a one-user function, it's becoming
        # redundant elsewhere

        # Determine how many extra cards players get (if any)
        extra = 0
        if self.blackcard[1] == 3:
            extra = 2
        if self.blackcard[1] == 2 and self.variants["packingheat"][1]:
            extra = 1

        # Draw up to the hand limit for each player
        for user in self.live_players:
            if user != self.live_players[self.judgeindex]:
                # get rid of Nones left from playing cards
                while None in self.hands[user]:
                    self.hands[user].remove(None)
                while len(self.hands[user]) < 10 + extra:
                    try:
                        self.hands[user].append(self.whitedeck.pop(0))
                    except KeyError:
                        # Ran out of white cards.
                        # Reshuffle them.
                        self.reshuffle_whitedeck()
                        self.hands[user].append(self.whitedeck.pop(0))
                    # self.privreply(user, "You draw: \x0304{}\x0F.".format(
                    #     self.hands[user][len(self.hands[user])-1]))

        # Full hand output to each player
        for user in self.live_players:
            self.showhand(user)

    def reshuffle_whitedeck(self):
        # Make a set of cards currently in someone's hand, which,
        # therefore, should not go into the deck
        inplay = set()
        for hand in self.hands.itervalues():
            for card in hand:
                inplay.add(card)
        # Add all the other white cards back into the white deck
        for card in self.basewhitedeck:
            if card not in inplay:
                self.whitedeck.append(card)
        # Shuffle proper
        random.shuffle(self.whitedeck)

    def showhand(self, user):
        if user != self.live_players[self.judgeindex]:
            hand = []
            for i in range(0, len(self.hands[user])):
                if self.hands[user][i]:
                    hand.append("{}: \x0304{}\x0F".format(
                        i+1,
                        ''.join(x for x in self.hands[user][i] if ord(x) < 128)
                    ))
            self.privreply(user, "Your hand: {}".format(
                ", ".join(hand)))

    def showscores(self):
        if self.gamestate == self.GameState.inprogress:
            blackbuild = []
            for player in self.players:
                if self.woncards[player] != 0:
                    blackbuild.append(
                        "{} - {}".format(self.woncards[player], player))
            if (
                    self.variants["rando"][1] and
                    self.woncards["Rando Cardrissian"] > 0):
                blackbuild.append("{} - Rando Cardrissian".format(
                    self.woncards["Rando Cardrissian"]))
            blackbuild.sort(reverse=True)
            if blackbuild != []:
                self.bot.pubout(
                    self.channel,
                    "Awesome Points per player: {}. Points to win: {}.".format(
                        ", ".join(blackbuild), self.cardstowin))
            else:
                self.bot.pubout(
                    self.channel,
                    "No scores yet. Cards to win: {}.".format(
                        self.cardstowin))
            if self.pot > 0:
                self.bot.pubout(
                    self.channel,
                    "There are {} Awesome Point(s) in the pot! "
                    "Winner takes all.".format(self.pot))
        else:
            self.bot.pubout(self.channel, "No game in progress.")

    def removeuser(self, user):
        self.bot.pubout(
            self.channel,
            "{} is no longer in the game.".format(
                user))

        # Game in progress handles differently than one in setup
        if self.gamestate == self.GameState.inprogress:
            # End the game if there are too few users to handle a quit
            if self.variants["rando"][1]:  # Rando counts too!
                minplayers = 3
            else:
                minplayers = 4
            if len(self.live_players) < minplayers:
                self.bot.pubout(
                    self.channel,
                    "There are now too few players to continue the game.")
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
                    self.bot.pubout(
                        self.channel,
                        "The Card Czar is now {}.".format(
                            self.live_players[self.judgeindex]))
                    judge = self.live_players[self.judgeindex]

                    # The new judge played these cards
                    judge_cards = [card for card in self.playedcards
                                   if card[0] == judge]
                    # Remove them
                    for card in judge_cards:
                        self.playedcards.remove(card)
                    # If there is more than one, it means the judge
                    # gambled. Give their points back.
                    if len(judge_cards) > 1:
                        self.woncards[judge] += len(judge_cards) - 1

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

            try:
                # Replace args with int versions
                for i in range(0, self.blackcard[1]):
                    args[i] = int(args[i]) - 1
            except ValueError:
                # End function, no output
                return
            except IndexError:
                self.reply(
                    channel,
                    user,
                    "Not enough cards! Play {}.".format(
                        self.blackcard[1]))
                return

            # Get player's played card status
            cardplayed = self.checkplayedcard(user)

            # Ensure player can play
            if (
                    user in self.live_players and
                    user != self.live_players[self.judgeindex] and
                    not self.judging and
                    not cardplayed and
                    len(args) == len(set(args))):

                # Ensure all cards are within range
                for arg in args:
                    if arg not in range(0, len(self.hands[user])):
                        self.reply(
                            channel,
                            user,
                            "You can't play a card you don't have.")
                        return
                    elif self.hands[user][arg] is None:
                        self.reply(
                            channel,
                            user,
                            "You already played card #{}".format(
                                arg+1))
                        return

                # Actually insert the cards
                playcards = []
                for card in args:
                    playcards.append(self.hands[user][card])
                self.playedcards.append([user, playcards])

                # Remove the cards from the player's hand
                for card in playcards:
                    i = self.hands[user].index(card)
                    self.hands[user][i] = None

                # Output to user, redisplay hand, and check if the
                # round is over
                if self.blackcard[1] == 1:
                    self.bot.pubout(
                        self.channel,
                        "{}: You have played your card.".format(user))
                else:
                    self.bot.pubout(
                        self.channel,
                        "{}: You have played your cards.".format(user))
#                self.showhand(user)
                self.checkroundover()

            # Send output based on error conditions
            elif user not in self.live_players:
                self.reply(channel, user, "You are not in this game.")
            elif user in self.playedcards:
                self.reply(
                    channel,
                    user,
                    "You have already played a card this round.")
            elif user == self.live_players[self.judgeindex]:
                self.reply(channel, user, "You are Card Czar this round.")
            elif self.judging:
                self.reply(
                    channel,
                    user,
                    "Judging has already begun, wait for the next round.")
            elif len(args) != len(set(args)):
                self.reply(
                    channel,
                    user,
                    "You can't play the same card more than once.")
            elif cardplayed:
                self.reply(
                    channel,
                    user,
                    "You have already played your card(s) this round.")
        else:
            self.reply(channel, user, "There is no game in progress.")

    def cmd_gamble(self, args, channel, user):
        # Ensure game is running
        if self.gamestate == self.GameState.inprogress:
            # Ignore the extra args
            args = args[:self.blackcard[1]]

            try:
                # Replace args with int versions
                for i in range(0, self.blackcard[1]):
                    args[i] = int(args[i]) - 1
            except ValueError:
                # End function, no output
                return
            except IndexError:
                self.reply(
                    channel,
                    user,
                    "Not enough cards! Play {}.".format(
                        self.blackcard[1]))
                return

            # Get player's played card status
            cardplayed = self.checkplayedcard(user)

            # Ensure player can gamble
            if (
                    user in self.live_players and
                    user != self.live_players[self.judgeindex] and
                    not self.judging and
                    cardplayed and
                    len(args) == len(set(args)) and
                    self.woncards[user] > 0):

                # Ensure all cards are within range
                for arg in args:
                    if arg not in xrange(0, len(self.hands[user])):
                        self.reply(
                            channel,
                            user,
                            "You can't play a card you don't have.")
                        return
                    elif self.hands[user][arg] is None:
                        self.reply(
                            channel,
                            user,
                            "You already played card #{}.".format(arg+1))
                        return

                # Actually insert the cards
                playcards = []
                for card in args:
                    playcards.append(self.hands[user][card])
                self.playedcards.append([user, playcards])

                # Remove the cards from the player's hand
                for card in playcards:
                    i = self.hands[user].index(card)
                    self.hands[user][i] = None

                # Put a black card into the pot
                self.woncards[user] = self.woncards[user] - 1
                self.pot = self.pot + 1

                # Output to user, redisplay hand, and check if the
                # round is over
                self.bot.pubout(
                    self.channel,
                    "{}: You have gambled an Awesome Point "
                    "for an additional play. "
                    "There are now {} points in the pot!".format(
                        user,
                        self.pot))
#                self.showhand(user)
                self.checkroundover()

            # Send output based on error conditions
            elif user not in self.live_players:
                self.reply(
                    channel,
                    user,
                    "You are not in this game. "
                    "To amend this circumstance, use !join")
            elif user in self.playedcards:
                self.reply(
                    channel,
                    user,
                    "You have already played a card this round.")
            elif user == self.live_players[self.judgeindex]:
                self.reply(channel, user, "You are Card Czar this round.")
            elif self.judging:
                self.reply(
                    channel,
                    user,
                    "Judging has already begun, wait for the next round.")
            elif len(args) != len(set(args)):
                self.reply(
                    channel,
                    user,
                    "You can't play the same card more than once.")
            elif not cardplayed:
                self.reply(
                    channel,
                    user,
                    "You cannot gamble until you have played "
                    "at least one card.")
            elif self.woncards[user] == 0:
                self.reply(
                    channel,
                    user,
                    "You must have at least one Awesome Point to gamble.")
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
            if self.judging and user == self.live_players[self.judgeindex]:
                try:
                    if (
                            int(args[0]) > 0 and
                            int(args[0]) <= len(self.playedcards)):
                        self.last_picker = user
#                        self.reply(channel, user, "You have chosen.")
                        self.cardwin(int(args[0]) - 1)
                    else:
                        self.reply(
                            channel,
                            user,
                            "Please pick a valid card number.")
                except (IndexError, ValueError):
                    self.reply(channel, user, "Please use the card's number.")
            elif user != self.live_players[self.judgeindex]:
                self.reply(
                    channel,
                    user,
                    "You are not the Card Czar this round.")
            elif len(self.playedcards) != len(self.live_players) - 1:
                self.reply(
                    channel,
                    user,
                    "Not everyone has played a card yet.")
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
                self.reply(
                    channel,
                    user,
                    "There is a game starting already. Please !join instead.")
            else:
                self.reply(
                    channel,
                    user,
                    "Not enough players to start a game. "
                    "Minimum of 3 required. "
                    "Currently: {}" .format(len(self.live_players)))
        elif self.gamestate == self.GameState.inprogress:
            self.reply(
                channel,
                user,
                "There is a game in progress. Please !join")

    def cmd_status(self, args, channel, user):
        # Display status
        if self.gamestate == self.GameState.none:
            self.reply(channel, user, "No game in progress.")
        elif self.gamestate == self.GameState.starting:
            self.reply(
                channel,
                user,
                "A new game is starting. "
                "Currently {} players: {}".format(
                    len(self.live_players),
                    ", ".join(self.live_players)))
        elif self.gamestate == self.GameState.inprogress:
            self.bot.pubout(
                self.channel,
                "Player order: {}. "
                "{} is the current Card Czar. "
                "Current black card is: \x02\x0303{}\x0F".format(
                    ", ".join(self.live_players),
                    self.live_players[self.judgeindex],
                    self.blackcard[0]))
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
                self.bot.pubout(
                    self.channel,
                    "{}: you're in! "
                    "If you need to leave, use !quit".format(user))
            else:
                self.reply(channel, user, "You are already in the game.")
        elif self.gamestate == self.GameState.inprogress:
            # TODO: Fix bug where players always get 10 cards, even in
            # packingheat + 2 or 3 play
            if user not in self.live_players:
                self.bot.pubout(
                    self.channel, "{} is now in the game.".format(user))
                if user not in self.players:
                    self.players.append(user)
                    if self.variants["playercards"][1]:
                        self.whitedeck.append(user)
                        random.shuffle(self.whitedeck)
                if user not in self.woncards:
                    self.woncards[user] = 0
                if user not in self.idle_players:
                    self.idle_players[user] = 0
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
            if not self.judging:
                finishedplayers = [self.judgeindex]
                for card in self.playedcards:
                    finishedplayers.append(card[0])
                unfinishedplayers = []
                for player in self.live_players:
                    if player not in finishedplayers:
                        unfinishedplayers.append(player)
                unfinishedplayers.remove(self.live_players[self.judgeindex])
                self.bot.pubout(
                    channel,
                    "{}: Please play a card.".format(
                        ", ".join(unfinishedplayers)))
            else:
                self.bot.pubout(
                    channel,
                    "{}: Please pick a card to win.".format(
                        self.live_players[self.judgeindex]))
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
            if (
                    self.gamestate == self.GameState.inprogress or
                    self.gamestate == self.GameState.starting):
                try:
                    player = args[0]
                    if player in self.live_players:
                        self.removeuser(player)
                    else:
                        self.reply(
                            channel,
                            user,
                            "That player is not in this game.")
                except IndexError:
                    self.reply(
                        channel,
                        user,
                        "Please specify the player to delete.")
            else:
                self.reply(channel, user, "There is no game in progress.")
        elif self.gamestate == self.GameState.starting:
            try:
                player = args[0]
                if player in self.live_players:
                    self.removeuser(player)
                else:
                    self.reply(
                        channel,
                        user,
                        "That player is not in this game.")
            except IndexError:
                self.reply(
                    channel,
                    user,
                    "Please specify the player to delete.")
        else:
            self.reply(
                channel,
                user,
                "You need to be at least a botmod to use that command.")

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
            self.reply(
                channel,
                user,
                "You need to be at least a botmod "
                "to use that command during a game.")
        elif self.gamestate == self.GameState.none:
            self.reply(channel, user, "There is no game in progress.")

    def cmd_help(self, args, channel, user):
        # Output all commands
        cmds = [i[4:] for i in dir(self) if i.startswith('cmd_')]
        self.reply(channel, user, "Valid commands: '{}'".format("', '".join(cmds)))

    def cmd_rules(self, args, channel, user):
        # Output a simple rules list
        self.reply(
            channel,
            user,
            "Cards Against Society is "
            "a free party game for humorless feminists, "
            "ripped off from Cards Against Humanity.")
        self.reply(
            channel,
            user,
            "Unlike most of the party games you've played before, "
            "Cards Against Society is as flamingly liberal "
            "as you and your friends.")
        self.reply(
            channel,
            user,
            "The game is simple. "
            "Each round, one player asks a question from a Black Card, "
            "and everyone else answers with their funniest White Card.")

    def cmd_variant(self, args, channel, user):
        # Manage variants
        # TODO: Take a look at this, see if I can simplify it
        for i in range(0, len(args)):
            args[i] = args[i].lower()
        if len(args) == 0:
            variant_strings = [
                "{}: {}".format(
                    variant.title(),
                    ("On" if self.variants[variant][1] else "Off"))
                for variant in self.variants.iterkeys()]
            self.reply(
                channel,
                user,
                "Current variants: {}".format(
                    ", ".join(variant_strings)))
        if len(args) == 1:
            if args[0] in self.variants.keys():
                self.reply(
                    channel,
                    user,
                    "{}: {}".format(
                        args[0].title(),
                        self.variants[args[0]][0]))
        if len(args) == 2:
            if self.gamestate == self.GameState.inprogress:
                self.reply(
                    channel,
                    user,
                    "Cannot modify variants during a game.")
                return
            if args[0] == "toggle":
                if args[1] in self.variants.keys():
                    if self.variants[args[1]][1]:
                        self.variants[args[1]][1] = False
                        self.reply(
                            channel,
                            user,
                            "{} is now deactivated.".format(
                                args[1].title()))
                    else:
                        self.variants[args[1]][1] = True
                        self.reply(
                            channel,
                            user,
                            "{} is now activated.".format(
                                args[1].title()))
            else:
                self.reply(
                    channel,
                    user,
                    "Syntax: 'variant toggle <variant>'")

    def cmd_reloadcards(self, args, channel, user):
        # Reload card lists
        userlevel = self.auth.get_userlevel(user)
        # If admin, reload cards. Else, do nothing.
        if userlevel == 200:
            self.loadcards()
            self.reply(channel, user, "Successfully reloaded base decks.")
        else:
            self.reply(channel, user, "You do not have permission to do that.")

    def cmd_clearblacklist(self, args, channel, user):
        userlevel = self.auth.get_userlevel(user)
        if userlevel < 100:
            self.reply(
                channel,
                user,
                "You must be at least a botmod to alter the blacklist.")
            return
        self.blacklist = set()
        self.reply(
            channel,
            user,
            "Blacklist is now empty.")

    def blacklist_cards(self, *args):
        added = []
        removed = []
        unmatched = []
        for arg in args:
            arg = arg.rstrip('\n')
            if arg == '':
                continue
            if arg in self.blacklist:
                self.blacklist.remove(arg)
                removed.append(arg)
            else:
                self.blacklist.add(arg)
                added.append(arg)
        return (added, removed, unmatched)

    def cmd_deck(self, _args, channel, user):
        userlevel = self.auth.get_userlevel(user)
        if len(_args) == 0:
            self.reply(channel,
                       user,
                       "Current decks enabled:")
            decks = self.baseblackdeck.decks_enabled
            for deck in decks:
                self.reply(channel,
                           user,
                           deck)
            return
        if userlevel < 100:
            self.reply(channel,
                       user,
                       "You must be at least a botmod to change decks.")
            return
        else:
            arg = " ".join(_args)
            try:
                if arg in self.baseblackdeck.decks_enabled:
                    self.disable_deck(arg)
                    self.reply(
                        channel,
                        user,
                        "Deck {} disabled.".format(arg))
                else:
                    self.enable_deck(arg)
                    self.reply(
                        channel,
                        user,
                        "Deck {} enabled.".format(arg))
            except ValueError:
                self.reply(
                    channel,
                    user,
                    "I don't have the deck {}. "
                    "If you're sure it exists, do !loadcards".format(
                        arg))
            
    def cmd_blacklist(self, _args, channel, user):
        userlevel = self.auth.get_userlevel(user)
        if len(_args) == 0:
            self.reply(
                channel,
                user,
                "Current blacklist:")
            for ex in self.blacklist:
                self.reply(
                    channel,
                    user,
                    ex)
            return
        if userlevel < 100:
            self.reply(
                channel,
                user,
                "You must be at least a botmod to alter the blacklist."
                "(your level: {} needed level: 100)".format(userlevel))
            return
        arg = " ".join(_args)
        if arg in self.blacklist:
            self.blacklist.remove(arg)
            self.reply(
                channel,
                user,
                "{} removed from blacklist.".format(arg))
        else:
            self.blacklist.add(arg)
            self.reply(
                channel,
                user,
                "Blacklisted {}.".format(arg))
        with open("./pyGBot/Plugins/games/CardsAgainstSocietyBlacklist.txt",
                  "r") as blaf:
            for blc in self.blacklist:
                blaf.write(blc + "\n")

    def do_command(self, channel, user, cmd):
        # Handle commands
        if cmd == '':
            return
        cmds = cmd.strip().split(" ")
        cmds[0] = cmds[0].lower()

        try:
            cmd_handler = getattr(self, "cmd_" + cmds[0])
        except AttributeError:
            cmd_handler = None

        if cmd_handler:
            cmd_handler(cmds[1:], channel, user)
            return
