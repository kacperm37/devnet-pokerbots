'''
How the Beat the Champion player turns typed input into moves. The full
interactive game needs a real terminal; tests/README.md has a manual check.
'''
import os
import sys
import unittest

from helpers import REPO

sys.path.insert(0, os.path.join(REPO, 'organizer', 'human_player'))
import player as human  # noqa: E402
from skeleton.states import RoundState  # noqa: E402
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction  # noqa: E402


def silent_player():
    p = human.Player.__new__(human.Player)  # skip __init__, which opens the terminal
    p.say = lambda *args: None
    return p


def preflop_small_blind():
    return RoundState(0, 0, [1, 2], [399, 398], [['As', 'Kd'], []], [], None)


def flop_nothing_bet():
    return RoundState(1, 3, [0, 0], [396, 396], [[], ['As', 'Kd']], ['2c', '7d', '9h'], None)


class TestTypedMoves(unittest.TestCase):

    def parse(self, reply, state, active):
        p = silent_player()
        legal = state.legal_actions()
        cost = state.pips[1 - active] - state.pips[active]
        pot = sum(400 - s for s in state.stacks)
        return p.parse(reply, legal, state, active, pot, cost)

    def test_basic_moves_facing_the_big_blind(self):
        state = preflop_small_blind()
        self.assertIsInstance(self.parse('c', state, 0), CallAction)
        self.assertIsInstance(self.parse('f', state, 0), FoldAction)
        self.assertIsNone(self.parse('k', state, 0))  # can't check facing a bet

    def test_raise_amounts(self):
        state = preflop_small_blind()
        self.assertEqual(self.parse('r 10', state, 0), RaiseAction(10))
        self.assertEqual(self.parse('a', state, 0), RaiseAction(400))
        self.assertEqual(self.parse('h', state, 0), RaiseAction(4))   # half pot, at least the minimum
        self.assertEqual(self.parse('p', state, 0), RaiseAction(6))   # call 1, then raise the 4-chip pot
        self.assertEqual(self.parse('r 2', state, 0), 'explained')   # below the minimum: asks again
        self.assertEqual(self.parse('r lots', state, 0), None)

    def test_call_with_nothing_to_call_means_check(self):
        state = flop_nothing_bet()
        self.assertIsInstance(self.parse('c', state, 1), CheckAction)
        self.assertIsInstance(self.parse('k', state, 1), CheckAction)
        self.assertIsNone(self.parse('f', state, 1))  # folding isn't offered when you can check

    def test_nonsense_is_rejected(self):
        state = preflop_small_blind()
        for reply in ('', 'zzz', '?'):
            self.assertIsNone(self.parse(reply, state, 0))


if __name__ == '__main__':
    unittest.main()
