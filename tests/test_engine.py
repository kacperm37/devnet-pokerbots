'''
Engine behavior, checked by playing short games with purpose-built bots.
Covers the tournament changes (duplicate deals, hidden seed, fixed run
command, output cap) and what happens when a bot misbehaves.
'''
import os
import shutil
import unittest

from helpers import (TempDirTest, engine, make_bot, play, read, dealt_cards, SKELETON)


class TestDuplicateDeals(TempDirTest):

    def test_same_seed_with_seats_swapped_deals_the_same_cards(self):
        a = make_bot(self.tmp, 'bot_a')
        b = make_bot(self.tmp, 'bot_b')
        play(a, b, os.path.join(self.tmp, 'g1'), hands=60, seed='dup', names=('X', 'Y'))
        play(b, a, os.path.join(self.tmp, 'g2'), hands=60, seed='dup', names=('Y', 'X'))
        game1 = dealt_cards(os.path.join(self.tmp, 'g1', 'gamelog.txt'))
        game2 = dealt_cards(os.path.join(self.tmp, 'g2', 'gamelog.txt'))
        self.assertEqual(len(game1), 60)
        for h1, h2 in zip(game1, game2):
            self.assertEqual(h1['X'], h2['Y'])  # Y gets X's game-1 cards on the same hand
            self.assertEqual(h1['Y'], h2['X'])

    def test_different_seeds_deal_different_cards(self):
        play(SKELETON, SKELETON, os.path.join(self.tmp, 's1'), hands=20, seed='one')
        play(SKELETON, SKELETON, os.path.join(self.tmp, 's2'), hands=20, seed='two')
        self.assertNotEqual(dealt_cards(os.path.join(self.tmp, 's1', 'gamelog.txt')),
                            dealt_cards(os.path.join(self.tmp, 's2', 'gamelog.txt')))

    def test_identical_bots_tie_a_duplicate_match(self):
        r1 = play(SKELETON, SKELETON, os.path.join(self.tmp, 'g1'), hands=100, seed='tie', names=('X', 'Y'))
        r2 = play(SKELETON, SKELETON, os.path.join(self.tmp, 'g2'), hands=100, seed='tie', names=('Y', 'X'))
        self.assertEqual(r1['players'][0]['bankroll'] + r2['players'][1]['bankroll'], 0)

    def test_games_are_zero_sum(self):
        result = play(SKELETON, os.path.join(SKELETON, '..', 'house_bots', 'rule_book'),
                      os.path.join(self.tmp, 'logs'), hands=100)
        self.assertEqual(sum(p['bankroll'] for p in result['players']), 0)


class TestIsolation(TempDirTest):

    def test_seed_is_hidden_from_bots(self):
        os.environ['POKERBOTS_SEED'] = 'leak-me'
        self.addCleanup(os.environ.pop, 'POKERBOTS_SEED', None)
        spy = make_bot(self.tmp, 'spy', init='''
            import os
            print('VISIBLE:', sorted(k for k in os.environ if k.startswith('POKERBOTS')), flush=True)
            print('SEED:', os.environ.get('POKERBOTS_SEED'), flush=True)
        ''')
        logs = os.path.join(self.tmp, 'logs')
        result = play(spy, SKELETON, logs, hands=5, seed=None)
        self.assertEqual(result['seed'], 'leak-me')  # the engine did use it...
        output = read(os.path.join(logs, 'A.txt'))
        self.assertIn('SEED: None', output)        # ...but the bot couldn't see it
        self.assertIn('VISIBLE: []', output)

    def test_official_mode_ignores_commands_json(self):
        if not shutil.which('python3'):
            self.skipTest('needs a python3 command on the PATH')
        bot = make_bot(self.tmp, 'bogus_commands')
        with open(os.path.join(bot, 'commands.json'), 'w') as fh:
            fh.write('{"build": ["false"], "run": ["false"]}')
        result = play(bot, SKELETON, os.path.join(self.tmp, 'logs'), hands=5, launcher=None)
        self.assertTrue(result['players'][0]['events']['connected'])

    def test_unix_socket_connection(self):
        sockets = os.path.join(self.tmp, 'sock')
        os.makedirs(sockets)
        result = play(SKELETON, SKELETON, os.path.join(self.tmp, 'logs'), hands=20, socket_dir=sockets)
        self.assertTrue(all(p['events']['connected'] for p in result['players']))


class TestMisbehavingBots(TempDirTest):

    def test_crash_is_reported_with_the_hand_number(self):
        crashy = make_bot(self.tmp, 'crashy', action='''
            if game_state.round_num == 7:
                raise ValueError('bug on purpose')
        ''')
        logs = os.path.join(self.tmp, 'logs')
        result = play(crashy, SKELETON, logs, hands=30)
        me = result['players'][0]
        self.assertEqual(me['events']['disconnected'], 7)
        self.assertIn('A disconnected', read(os.path.join(logs, 'gamelog.txt')))
        self.assertIn('bug on purpose', read(os.path.join(logs, 'A.txt')))  # traceback is kept
        self.assertEqual(read(os.path.join(logs, 'gamelog.txt')).count('Round #'), 30)  # game finished

    def test_illegal_actions_are_logged_and_replaced(self):
        cheeky = make_bot(self.tmp, 'cheeky', action='''
            if RaiseAction in legal_actions:
                return RaiseAction(1)  # below the minimum raise
        ''')
        logs = os.path.join(self.tmp, 'logs')
        result = play(cheeky, SKELETON, logs, hands=10)
        self.assertGreater(result['players'][0]['events']['illegal'], 0)
        self.assertIn('A attempted illegal RaiseAction', read(os.path.join(logs, 'gamelog.txt')))

    def test_running_out_of_clock(self):
        slow = make_bot(self.tmp, 'slow', action='''
            import time
            time.sleep(0.05)
        ''')
        result = play(slow, SKELETON, os.path.join(self.tmp, 'logs'), hands=40, clocks=(0.5, None))
        self.assertIsNotNone(result['players'][0]['events']['ran_out_of_time'])

    def test_single_decision_time_limit(self):
        # the official limit is 10 seconds per decision; 1 second keeps the test quick
        stall = make_bot(self.tmp, 'stall', action='''
            if game_state.round_num == 2:
                import time
                time.sleep(2)
        ''')
        result = play(stall, SKELETON, os.path.join(self.tmp, 'logs'), hands=5, read_timeouts=(1, 10))
        self.assertEqual(result['players'][0]['events']['ran_out_of_time'], 2)

    def test_output_is_capped(self):
        noisy = make_bot(self.tmp, 'noisy', action="print('x' * 20000, flush=True)\n")
        logs = os.path.join(self.tmp, 'logs')
        play(noisy, SKELETON, logs, hands=60)
        size = os.path.getsize(os.path.join(logs, 'A.txt'))
        self.assertLessEqual(size, engine.PLAYER_LOG_SIZE_LIMIT + 20001)

    def test_game_can_refuse_to_start_without_both_bots(self):
        dead = make_bot(self.tmp, 'dead', top='import sys\nsys.exit(1)\n')
        old = engine.CONNECT_TIMEOUT
        engine.CONNECT_TIMEOUT = 2  # don't wait the full 10 seconds in a test
        self.addCleanup(setattr, engine, 'CONNECT_TIMEOUT', old)
        with self.assertRaises(RuntimeError):
            play(dead, SKELETON, os.path.join(self.tmp, 'logs'), hands=5, require_connection=True)


if __name__ == '__main__':
    unittest.main()
