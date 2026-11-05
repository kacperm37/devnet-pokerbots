'''
Reads a gamelog.txt into Hand objects, for the hand viewer and the Best Bluff finder.
'''
import re
from dataclasses import dataclass, field

SMALL_BLIND, BIG_BLIND = 1, 2

ROUND = re.compile(r'^Round #(\d+), (\S+) \((-?\d+)\), (\S+) \((-?\d+)\)$')
DEALT = re.compile(r'^(\S+) dealt \[(.*)\]$')
STREET = re.compile(r'^(Flop|Turn|River) \[(.*)\], (\S+) \((\d+)\), (\S+) \((\d+)\)$')
ACTION = re.compile(r'^(\S+) (folds|checks|calls|bets|raises to)(?: (\d+))?$')
SHOWS = re.compile(r'^(\S+) shows \[(.*)\]$')
AWARDED = re.compile(r'^(\S+) awarded (-?\d+)$')
NOTE = re.compile(r'^(\S+) (attempted illegal .*|response misformatted.*|ran out of time|disconnected)$')


@dataclass
class Action:
    street: str     # 'Preflop', 'Flop', 'Turn', 'River'
    board: list     # board cards when it happened
    player: str
    verb: str       # 'folds', 'checks', 'calls', 'bets', 'raises to'
    amount: int     # for bets and raises: the new street total; otherwise 0
    pot: int        # chips in the pot after this action


@dataclass
class Hand:
    number: int
    button: str                     # small blind; acts first preflop
    big_blind: str
    bankroll_before: dict           # running totals before this hand
    hole: dict = field(default_factory=dict)
    actions: list = field(default_factory=list)
    board: list = field(default_factory=list)  # final board shown (may be under 5 cards)
    showdown: bool = False
    deltas: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)  # illegal actions, timeouts, disconnects

    @property
    def players(self):
        return [self.button, self.big_blind]

    @property
    def pot(self):
        '''Chips that changed hands, counted the poker way: both players' matched chips.'''
        return 2 * max(self.deltas.values()) if self.deltas else 0

    @property
    def winner(self):
        best = max(self.deltas, key=self.deltas.get) if self.deltas else None
        return best if best and self.deltas[best] > 0 else None

    @property
    def folded(self):
        last = self.actions[-1] if self.actions else None
        return last.player if last and last.verb == 'folds' else None


def parse(path):
    '''Returns the list of hands in a gamelog.txt and the title line.'''
    hands, hand = [], None
    street, board = 'Preflop', []
    totals, pips = {}, {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        lines = fh.read().splitlines()
    title = lines[0] if lines else ''
    for line in lines[1:]:
        m = ROUND.match(line)
        if m:
            number, a, ra, b, rb = m.groups()
            hand = Hand(int(number), a, b, {a: int(ra), b: int(rb)})
            hands.append(hand)
            street, board = 'Preflop', []
            totals = {a: 0, b: 0}
            pips = {a: SMALL_BLIND, b: BIG_BLIND}
            continue
        if hand is None or not line:
            continue
        m = DEALT.match(line)
        if m:
            hand.hole[m.group(1)] = m.group(2).split()
            continue
        m = STREET.match(line)
        if m:
            street, board = m.group(1), m.group(2).split()
            hand.board = board
            totals = {m.group(3): int(m.group(4)), m.group(5): int(m.group(6))}
            pips = {name: 0 for name in totals}
            continue
        m = ACTION.match(line)
        if m:
            player, verb, amount = m.group(1), m.group(2), int(m.group(3) or 0)
            if verb == 'calls':
                pips[player] = max(pips.values())
            elif verb in ('bets', 'raises to'):
                pips[player] = amount
            pot = sum(totals.values()) + sum(pips.values())
            hand.actions.append(Action(street, list(board), player, verb, amount, pot))
            continue
        m = SHOWS.match(line)
        if m:
            hand.showdown = True
            hand.hole[m.group(1)] = m.group(2).split()
            continue
        m = AWARDED.match(line)
        if m:
            hand.deltas[m.group(1)] = int(m.group(2))
            continue
        m = NOTE.match(line)
        if m:
            hand.notes.append(line)
    return title, hands
