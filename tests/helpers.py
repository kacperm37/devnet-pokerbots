'''
Shared helpers for the tests: build throwaway bots from the starter bot and
play short games with them.
'''
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import engine  # noqa: E402
from launchers import HostLauncher  # noqa: E402

SKELETON = os.path.join(REPO, 'python_skeleton')
HOUSE_BOTS = os.path.join(REPO, 'house_bots')
ACTION_HOOK = '        legal_actions = round_state.legal_actions()  # the actions you are allowed to take\n'


class TempDirTest(unittest.TestCase):
    '''A test case with a fresh temporary folder in self.tmp.'''

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='pokerbots-test-')
        self.addCleanup(shutil.rmtree, self.tmp, True)


def make_bot(parent, name, top='', init='', action=''):
    '''
    Copies python_skeleton to parent/name and injects code:
    top runs at import time, init in __init__, and action at the start of get_action
    (where game_state, round_state, active, and legal_actions are available).
    '''
    path = os.path.join(parent, name)
    shutil.copytree(SKELETON, path, ignore=shutil.ignore_patterns('__pycache__'))
    player = os.path.join(path, 'player.py')
    with open(player) as fh:
        source = fh.read()
    if init:
        source = source.replace('        pass\n', textwrap.indent(textwrap.dedent(init), ' ' * 8), 1)
    if action:
        assert ACTION_HOOK in source
        source = source.replace(ACTION_HOOK, ACTION_HOOK + textwrap.indent(textwrap.dedent(action), ' ' * 8), 1)
    if top:
        source = textwrap.dedent(top) + '\n' + source
    with open(player, 'w') as fh:
        fh.write(source)
    return path


def play(p1, p2, log_dir, hands=50, seed='test-seed', names=('A', 'B'), **options):
    '''Plays one game between two bot folders and returns the engine's summary.'''
    options.setdefault('launcher', HostLauncher())
    return engine.Game((names[0], p1), (names[1], p2), num_rounds=hands, seed=seed, official=True,
                       log_dir=log_dir, quiet=True, **options).run()


def read(path):
    with open(path, errors='replace') as fh:
        return fh.read()


def dealt_cards(log_path):
    '''[(hand number, {player: cards}), ...] from a game log.'''
    hands, current = [], None
    for line in read(log_path).splitlines():
        if line.startswith('Round #'):
            current = {}
            hands.append(current)
        elif ' dealt [' in line and current is not None:
            name, cards = line.split(' dealt ')
            current[name] = cards
    return hands
