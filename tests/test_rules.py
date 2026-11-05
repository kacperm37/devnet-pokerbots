'''
Poker rules, checked directly against the engine's game tree (no bots needed).
These match the examples in the participant guide, section 2.
'''
import unittest

import eval7

from helpers import engine

FoldAction, CallAction = engine.FoldAction, engine.CallAction
CheckAction, RaiseAction = engine.CheckAction, engine.RaiseAction


def new_hand(sb_cards='As Ad', bb_cards='Ks Kd', board='2c 7d 9h Js 3s'):
    '''A fresh hand: player 0 is the button (small blind), player 1 the big blind.'''
    hands = [[eval7.Card(c) for c in sb_cards.split()], [eval7.Card(c) for c in bb_cards.split()]]
    deck = eval7.Deck()
    top = [eval7.Card(c) for c in board.split()]
    used = {str(c) for c in top} | set(sb_cards.split()) | set(bb_cards.split())
    deck.cards[:] = top + [c for c in deck.cards if str(c) not in used]
    stacks = [engine.STARTING_STACK - engine.SMALL_BLIND, engine.STARTING_STACK - engine.BIG_BLIND]
    return engine.RoundState(0, 0, [engine.SMALL_BLIND, engine.BIG_BLIND], stacks, hands, deck, None)


def play_out(state, *actions):
    for action in actions:
        state = state.proceed(action)
    return state


class TestBetting(unittest.TestCase):

    def test_small_blind_options_preflop(self):
        state = new_hand()
        self.assertEqual(state.legal_actions(), {FoldAction, CallAction, RaiseAction})
        self.assertEqual(state.raise_bounds(), (4, 400))  # min raise to 4, max is all in

    def test_check_only_when_nobody_has_bet(self):
        state = play_out(new_hand(), CallAction())  # small blind completes
        self.assertEqual(state.legal_actions(), {CheckAction, RaiseAction})

    def test_minimum_reraise_example_from_the_guide(self):
        # flop: one bot bets 10, the other raises to 30, so the next raise must reach 50
        flop = play_out(new_hand(), CallAction(), CheckAction())
        self.assertEqual(flop.street, 3)
        state = play_out(flop, RaiseAction(10), RaiseAction(30))
        self.assertEqual(state.raise_bounds()[0], 50)

    def test_big_blind_acts_first_after_the_flop(self):
        flop = play_out(new_hand(), CallAction(), CheckAction())
        self.assertEqual(flop.button % 2, 1)

    def test_raise_amounts_are_raise_to_not_raise_by(self):
        state = play_out(new_hand(), RaiseAction(30))
        self.assertEqual(state.pips[0], 30)
        self.assertEqual(state.stacks[0], engine.STARTING_STACK - 30)

    def test_all_in_called_means_only_checks(self):
        state = play_out(new_hand(), RaiseAction(400), CallAction())
        self.assertEqual(state.street, 3)
        self.assertEqual(state.legal_actions(), {CheckAction})


class TestPayouts(unittest.TestCase):

    def test_fold_preflop(self):
        result = play_out(new_hand(), FoldAction())
        self.assertEqual(result.deltas, [-1, 1])

    def test_showdown_better_hand_wins(self):
        checks = [CallAction(), CheckAction()] + [CheckAction()] * 6
        result = play_out(new_hand('As Ad', 'Ks Kd'), *checks)
        self.assertIsInstance(result, engine.TerminalState)
        self.assertEqual(result.deltas, [2, -2])

    def test_split_pot(self):
        checks = [CallAction(), CheckAction()] + [CheckAction()] * 6
        result = play_out(new_hand('2c 3d', '4h 5d', 'As Ks Qs Js Ts'), *checks)
        self.assertEqual(result.deltas, [0, 0])

    def test_every_hand_is_zero_sum(self):
        result = play_out(new_hand(), RaiseAction(12), CallAction(), RaiseAction(20), FoldAction())
        self.assertEqual(sum(result.deltas), 0)


if __name__ == '__main__':
    unittest.main()
