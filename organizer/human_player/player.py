'''
A "bot" that asks a person for every move, for Beat the Champion.

The engine reads bots' normal output into a log, so this talks to the person
through the terminal directly (/dev/tty). That works on Linux and macOS.
Start it with organizer/beat_the_champion.py, not on its own.
'''
import os

from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

SUITS = {'s': ('♠', '97'), 'h': ('♥', '91'), 'd': ('♦', '94'), 'c': ('♣', '92')}
HELP = '''  f = fold    k = check    c = call
  r 40 = raise (or bet) to 40 chips this street
  h = half-pot bet    p = pot-size bet    a = all in'''


def paint(text, code):
    return '\033[{}m{}\033[0m'.format(code, text)


def card(c):
    rank = '10' if c[0] == 'T' else c[0]
    symbol, color = SUITS[c[1]]
    return paint(rank + symbol, '1;' + color)


def cards(cs):
    return '  '.join(card(c) for c in cs) if cs else paint('(none yet)', '2')


class Player(Bot):

    def __init__(self):
        try:
            self.tty_in = open('/dev/tty', 'r')
            self.tty = open('/dev/tty', 'w')
        except OSError:
            print('Beat the Champion needs a terminal (Linux or macOS).', flush=True)
            raise
        self.hands_in_game = os.environ.get('BEAT_THE_CHAMPION_HANDS', '?')
        self.street_seen = None
        self.my_last = None             # 'raise', 'call', 'check-first', 'check-last'

    def say(self, text=''):
        self.tty.write(text + '\n')
        self.tty.flush()

    def ask(self, prompt):
        self.tty.write(prompt)
        self.tty.flush()
        return self.tty_in.readline().strip().lower()

    def handle_new_round(self, game_state, round_state, active):
        self.street_seen = None
        self.my_last = None
        seat = 'the button (small blind)' if active == 0 else 'the big blind'
        self.say()
        self.say(paint('=' * 54, '2'))
        self.say(paint('Hand {} of {}'.format(game_state.round_num, self.hands_in_game), '1') +
                 paint('   you are {}'.format(seat), '2'))
        self.say('Your cards:  ' + cards(round_state.hands[active]) +
                 paint('      running total {:+d}'.format(game_state.bankroll), '2'))

    def describe_opponent(self, round_state, active):
        street = round_state.street
        my_pip, opp_pip = round_state.pips[active], round_state.pips[1 - active]
        if street != self.street_seen:
            # a new street started since our last move: say how the last one ended
            if self.my_last == 'raise':
                self.say(paint('Opponent calls.', '96'))
            elif self.my_last == 'check-first':
                self.say(paint('Opponent checks.', '96'))
            names = {0: 'PREFLOP', 3: 'FLOP', 4: 'TURN', 5: 'RIVER'}
            self.say()
            self.say(paint(names[street], '1') + '   board: ' + cards(round_state.deck[:street]))
            self.street_seen = street
        if opp_pip > my_pip:
            if street == 0 and opp_pip == BIG_BLIND:
                self.say(paint('{} to call (the big blind).'.format(opp_pip - my_pip), '96'))
            else:
                verb = 'bets' if my_pip == 0 else 'raises to'
                self.say(paint('Opponent {} {}. {} to call.'.format(verb, opp_pip, opp_pip - my_pip), '96'))
        elif street == 0 and active == 1:
            self.say(paint('Opponent calls the big blind.', '96'))
        elif street > 0 and active == 0:
            self.say(paint('Opponent checks.', '96'))

    def get_action(self, game_state, round_state, active):
        legal = round_state.legal_actions()
        my_pip, opp_pip = round_state.pips[active], round_state.pips[1 - active]
        continue_cost = opp_pip - my_pip
        pot = sum(STARTING_STACK - s for s in round_state.stacks)
        self.describe_opponent(round_state, active)
        self.say(paint('Pot {}   your stack {}   opponent stack {}'.format(
            pot, round_state.stacks[active], round_state.stacks[1 - active]), '2'))
        options = []
        if FoldAction in legal:
            options.append('f fold')
        if CheckAction in legal:
            options.append('k check')
        if CallAction in legal:
            options.append('c call {}'.format(continue_cost))
        if RaiseAction in legal:
            low, high = round_state.raise_bounds()
            word = 'bet' if continue_cost == 0 and round_state.street > 0 else 'raise'
            options.append('r N {} to {}-{}'.format(word, low, high))
            options.append('h half pot  p pot  a all in')
        while True:
            reply = self.ask(paint('Your move', '1;93') + paint(' ({}): '.format(', '.join(options)), '2'))
            if reply.startswith('?'):
                self.say(HELP)
                continue
            action = self.parse(reply, legal, round_state, active, pot, continue_cost)
            if action == 'explained':
                continue
            if action is not None:
                if isinstance(action, RaiseAction):
                    self.my_last = 'raise'
                elif isinstance(action, CheckAction):
                    first = round_state.street > 0 and active == 1  # big blind acts first after the flop
                    self.my_last = 'check-first' if first else 'check-last'
                else:
                    self.my_last = 'call'
                return action
            self.say(paint('That move isn\'t allowed right now. Options:', '91'))
            self.say(HELP)

    def parse(self, reply, legal, round_state, active, pot, continue_cost):
        if not reply:
            return None
        key = reply[0]
        if key == 'f' and FoldAction in legal:
            return FoldAction()
        if key in 'kx' and CheckAction in legal:
            return CheckAction()
        if key == 'c' and CallAction in legal:
            return CallAction()
        if key == 'c' and CheckAction in legal:
            return CheckAction()  # "call" with nothing to call means check
        if key in 'rhpa' and RaiseAction in legal:
            low, high = round_state.raise_bounds()
            my_pip = round_state.pips[active]
            if key == 'a':
                return RaiseAction(high)
            if key in 'hp':
                fraction = 0.5 if key == 'h' else 1.0
                target = my_pip + continue_cost + int(fraction * (pot + continue_cost))
                return RaiseAction(max(low, min(high, target)))
            try:
                amount = int(reply[1:].strip())
            except ValueError:
                return None
            if low <= amount <= high:
                return RaiseAction(amount)
            self.say(paint('Pick an amount from {} to {}.'.format(low, high), '91'))
            return 'explained'
        return None

    def handle_round_over(self, game_state, terminal_state, active):
        delta = terminal_state.deltas[active]
        previous = terminal_state.previous_state
        opp_cards = previous.hands[1 - active]
        self.say()
        if opp_cards:
            self.say('Showdown. Opponent had ' + cards(opp_cards) + '   board: ' + cards(previous.deck[:5]))
        elif delta > 0:
            self.say(paint('Opponent folds.', '96'))
        chips = lambda n: '{} chip{}'.format(n, '' if n == 1 else 's')
        if delta > 0:
            self.say(paint('You win {}.'.format(chips(delta)), '1;92'))
        elif delta < 0:
            self.say(paint('You lose {}.'.format(chips(-delta)), '1;91'))
        else:
            self.say(paint('Split pot.', '1'))
        self.say(paint('Running total: {:+d}'.format(game_state.bankroll), '1'))  # already includes this hand


if __name__ == '__main__':
    run_bot(Player(), parse_args())
