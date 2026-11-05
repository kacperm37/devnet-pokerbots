'''
The command-line tools: check_bot.py, the tournament runner, the game log
parser, the Best Bluff finder, and the hand viewer.
'''
import json
import os
import shutil
import subprocess
import sys
import unittest

from helpers import TempDirTest, REPO, SKELETON, HOUSE_BOTS, make_bot

sys.path.insert(0, os.path.join(REPO, 'organizer'))
import gamelog  # noqa: E402
import best_bluff  # noqa: E402

# One hand from a real game: rule_book bets the river with a pair of fives and
# monte_carlo folds a pair of tens. That's a bluff by the Best Bluff rule.
SAMPLE_LOG = '''DevNet.CSU Pokerbots - rule_book vs monte_carlo

Round #34, monte_carlo (-417), rule_book (417)
monte_carlo posts the blind of 1
rule_book posts the blind of 2
monte_carlo dealt [6c Th]
rule_book dealt [5h 2h]
monte_carlo calls
rule_book checks
Flop [Ts Ah 5s], monte_carlo (2), rule_book (2)
rule_book bets 2
monte_carlo raises to 6
rule_book calls
Turn [Ts Ah 5s Ks], monte_carlo (8), rule_book (8)
rule_book bets 8
monte_carlo calls
River [Ts Ah 5s Ks Qs], monte_carlo (16), rule_book (16)
rule_book bets 16
monte_carlo folds
monte_carlo awarded -16
rule_book awarded 16

Round #35, rule_book (433), monte_carlo (-433)
rule_book posts the blind of 1
monte_carlo posts the blind of 2
rule_book dealt [9c 9d]
monte_carlo dealt [4s 4d]
rule_book calls
monte_carlo checks
Flop [2c 7h Jd], rule_book (2), monte_carlo (2)
monte_carlo checks
rule_book checks
Turn [2c 7h Jd 3s], rule_book (2), monte_carlo (2)
monte_carlo checks
rule_book checks
River [2c 7h Jd 3s Kc], rule_book (2), monte_carlo (2)
monte_carlo checks
rule_book checks
rule_book shows [9c 9d]
monte_carlo shows [4s 4d]
rule_book awarded 2
monte_carlo awarded -2

Final, rule_book (435), monte_carlo (-435)'''


def run(*args, cwd=REPO):
    return subprocess.run([sys.executable] + list(args), cwd=cwd, capture_output=True, text=True, timeout=600)


class TestCheckBot(TempDirTest):

    def test_starter_bot_passes(self):
        out = run('check_bot.py', 'python_skeleton')
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn('PASS', out.stdout)

    def test_crashing_bot_fails_with_its_traceback(self):
        bot = make_bot(self.tmp, 'crashy', action='''
            if game_state.round_num == 5:
                raise ValueError('bug on purpose')
        ''')
        out = run('check_bot.py', bot)
        self.assertEqual(out.returncode, 1)
        self.assertIn('crashed or disconnected on hand 5', out.stdout)
        self.assertIn('bug on purpose', out.stdout)

    def test_unapproved_library_is_flagged(self):
        bot = make_bot(self.tmp, 'fancy', top='import definitely_not_an_approved_library\n')
        out = run('check_bot.py', bot)
        self.assertIn("aren't approved: definitely_not_an_approved_library", out.stdout)
        self.assertIn('never connected', out.stdout)

    def test_git_history_does_not_count_toward_the_size_limit(self):
        bot = make_bot(self.tmp, 'repo_bot')
        os.makedirs(os.path.join(bot, '.git'))
        with open(os.path.join(bot, '.git', 'big_pack'), 'wb') as fh:
            fh.truncate(150 * 10 ** 6)  # a sparse file: 150 MB on paper, no real disk use
        out = run('check_bot.py', bot)
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn('Size: 0.0 MB of 100 MB', out.stdout)


class TestTournament(TempDirTest):

    def test_round_robin_end_to_end(self):
        bots = os.path.join(self.tmp, 'bots')
        os.makedirs(bots)
        shutil.copytree(SKELETON, os.path.join(bots, 'twin_a'))
        shutil.copytree(SKELETON, os.path.join(bots, 'twin_b'))
        shutil.copytree(os.path.join(HOUSE_BOTS, 'rule_book'), os.path.join(bots, 'rules'))
        out_dir = os.path.join(self.tmp, 'results')
        out = run(os.path.join('organizer', 'tournament.py'), bots, '--hands', '40', '--out', out_dir)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        with open(os.path.join(out_dir, 'results.json')) as fh:
            results = json.load(fh)
        matchups = {m['id']: m for m in results['matchups']}
        self.assertEqual(set(matchups), {'rules_vs_twin_a', 'rules_vs_twin_b', 'twin_a_vs_twin_b'})
        self.assertEqual(matchups['twin_a_vs_twin_b']['score_a'], 0)  # identical bots tie
        for m in matchups.values():
            self.assertEqual(len(m['seed']), 32)
            for game in ('game1', 'game2'):
                self.assertTrue(os.path.isfile(os.path.join(out_dir, m['id'], game, 'gamelog.txt')))
        self.assertTrue(os.path.isfile(os.path.join(out_dir, 'standings.txt')))

        # rerunning with the saved seed replays the same cards, so deterministic bots repeat exactly
        rerun_dir = os.path.join(self.tmp, 'rerun')
        out = run(os.path.join('organizer', 'tournament.py'), bots, '--hands', '40', '--out', rerun_dir,
                  '--reuse-seeds', os.path.join(out_dir, 'results.json'), '--only', 'rules_vs_twin_a')
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        with open(os.path.join(rerun_dir, 'results.json')) as fh:
            rerun = json.load(fh)['matchups']
        self.assertEqual(len(rerun), 1)
        self.assertEqual(rerun[0]['seed'], matchups['rules_vs_twin_a']['seed'])
        self.assertEqual(rerun[0]['score_a'], matchups['rules_vs_twin_a']['score_a'])


class TestStandings(unittest.TestCase):

    def setUp(self):
        import tournament
        self.standings = tournament.standings

    def test_matchups_won_first_then_net_chips(self):
        bots = {'A': '', 'B': '', 'C': ''}
        # a rock-paper-scissors loop: everyone wins once, so net chips decides
        matchups = [{'a': 'A', 'b': 'B', 'score_a': 10},
                    {'a': 'B', 'b': 'C', 'score_a': 10},
                    {'a': 'C', 'b': 'A', 'score_a': 50}]
        ranked = self.standings(bots, matchups)
        self.assertEqual([r['team'] for r in ranked], ['C', 'B', 'A'])
        self.assertEqual([r['won'] for r in ranked], [1, 1, 1])
        self.assertEqual(ranked[0]['bankroll'], 10000 + 40)

    def test_more_wins_beats_more_chips(self):
        bots = {'A': '', 'B': '', 'C': ''}
        matchups = [{'a': 'A', 'b': 'B', 'score_a': 1},
                    {'a': 'A', 'b': 'C', 'score_a': 1},
                    {'a': 'B', 'b': 'C', 'score_a': 5000}]
        ranked = self.standings(bots, matchups)
        self.assertEqual(ranked[0]['team'], 'A')  # 2 wins, +2 chips
        self.assertEqual(ranked[1]['team'], 'B')  # 1 win, +4,999 chips


class TestLogTools(TempDirTest):

    def setUp(self):
        super().setUp()
        self.log_dir = os.path.join(self.tmp, 'game1')
        os.makedirs(self.log_dir)
        self.log = os.path.join(self.log_dir, 'gamelog.txt')
        with open(self.log, 'w') as fh:
            fh.write(SAMPLE_LOG)

    def test_parser_tracks_pots_and_results(self):
        title, hands = gamelog.parse(self.log)
        self.assertEqual(len(hands), 2)
        bluff, showdown = hands
        self.assertEqual(bluff.button, 'monte_carlo')
        self.assertEqual(bluff.hole['rule_book'], ['5h', '2h'])
        self.assertEqual([a.pot for a in bluff.actions], [4, 4, 6, 12, 16, 24, 32, 48, 48])
        self.assertEqual((bluff.winner, bluff.folded, bluff.pot), ('rule_book', 'monte_carlo', 32))
        self.assertFalse(bluff.showdown)
        self.assertTrue(showdown.showdown)
        self.assertEqual(showdown.winner, 'rule_book')

    def test_equity_is_exact_after_the_flop(self):
        self.assertEqual(best_bluff.equity(['As', 'Ad'], ['Ks', 'Kd'], '2c 7d 9h Js 3s'.split()), 1.0)
        self.assertEqual(best_bluff.equity(['Ks', 'Kd'], ['As', 'Ad'], '2c 7d 9h Js 3s'.split()), 0.0)
        # Ah Kh vs 2c 2d on Qh Jh 5c 9s: 18 of the 44 rivers win (9 hearts, 3 tens, 3 aces, 3 kings)
        self.assertAlmostEqual(best_bluff.equity(['Ah', 'Kh'], ['2c', '2d'], 'Qh Jh 5c 9s'.split()), 18 / 44)

    def test_equity_preflop_is_close(self):
        self.assertAlmostEqual(best_bluff.equity(['As', 'Ad'], ['Ks', 'Kd'], []), 0.82, delta=0.03)

    def test_best_bluff_finds_the_bluff(self):
        out = run(os.path.join('organizer', 'best_bluff.py'), self.tmp)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('Best Bluff: rule_book won a 32-chip pot on the river of hand 34', out.stdout)

    def test_viewer_shows_a_hand(self):
        out = run(os.path.join('organizer', 'view_hands.py'), self.log_dir, '--hand', '34', '--no-color')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('rule_book wins 16 when monte_carlo folds', out.stdout)
        out = run(os.path.join('organizer', 'view_hands.py'), self.log_dir, '--hand', '35', '--no-color')
        self.assertIn('rule_book wins 2 at showdown', out.stdout)


if __name__ == '__main__':
    unittest.main()
