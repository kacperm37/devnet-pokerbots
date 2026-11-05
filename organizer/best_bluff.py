'''
Best Bluff finder: the biggest pots won by making the opponent fold while
holding the weaker hand.

    python3 organizer/best_bluff.py results [--top 10] [--exclude house_bot]

"Weaker hand" means the winner's equity was under 50% at the moment the
opponent folded: if both hands had been played out from that board, the
winner would have lost more often than not. Equity is exact on the flop, turn,
and river, and estimated from 5,000 random boards preflop.

"Pot" is what changed hands: twice the chips the folding bot had put in.
An uncalled final bet doesn't count, since it goes back to the bettor.
'''
import argparse
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import eval7  # noqa: E402
from gamelog import parse  # noqa: E402

FULL_DECK = [str(c) for c in eval7.Deck().cards]
PREFLOP_SAMPLES = 5000


def equity(mine, theirs, board):
    '''Chance `mine` beats `theirs` from this board, counting ties as half.'''
    known = set(mine) | set(theirs) | set(board)
    rest = [eval7.Card(c) for c in FULL_DECK if c not in known]
    me, them, shared = ([eval7.Card(c) for c in cs] for cs in (mine, theirs, board))
    need = 5 - len(shared)
    if need == 0:
        runouts = [()]
    elif need <= 2:
        runouts = itertools.combinations(rest, need)
    else:  # preflop: sample instead of enumerating 1.7 million boards
        rng = random.Random(' '.join(mine + theirs))
        runouts = (rng.sample(rest, need) for _ in range(PREFLOP_SAMPLES))
    score = total = 0
    for extra in runouts:
        full = shared + list(extra)
        a, b = eval7.evaluate(me + full), eval7.evaluate(them + full)
        score += 2 if a > b else 1 if a == b else 0
        total += 2
    return score / total


def shown(path):
    '''A short path when it's under the current folder, otherwise the full path.'''
    path = os.path.abspath(path)
    here = os.getcwd()
    return os.path.relpath(path, here) if path.startswith(here + os.sep) else path


def find_logs(path):
    if os.path.isfile(path):
        return [path]
    logs = []
    for root, _, files in os.walk(path):
        if 'gamelog.txt' in files:
            logs.append(os.path.join(root, 'gamelog.txt'))
    return sorted(logs)


def main():
    parser = argparse.ArgumentParser(description='Find the Best Bluff in a set of game logs.')
    parser.add_argument('results', help='a results folder from tournament.py, or one gamelog.txt')
    parser.add_argument('--top', type=int, default=10)
    parser.add_argument('--exclude', action='append', default=[], help='skip bluffs by this bot')
    args = parser.parse_args()

    candidates = []
    for log in find_logs(args.results):
        _, hands = parse(log)
        for hand in hands:
            winner, folder = hand.winner, hand.folded
            if not winner or not folder or winner in args.exclude:
                continue
            if winner not in hand.hole or folder not in hand.hole:
                continue
            candidates.append((hand.pot, log, hand))
    if not candidates:
        sys.exit('No hands that ended in a fold were found under ' + args.results)
    candidates.sort(key=lambda c: c[0], reverse=True)

    bluffs = []
    teams = {h.winner for _, _, h in candidates}
    best_by_team = {}
    for pot, log, hand in candidates:
        if len(bluffs) >= args.top and len(best_by_team) == len(teams):
            break
        last = hand.actions[-1]
        eq = equity(hand.hole[hand.winner], hand.hole[hand.folded], last.board)
        if eq >= 0.5:
            continue
        entry = (pot, eq, log, hand, last.street)
        if len(bluffs) < args.top:
            bluffs.append(entry)
        best_by_team.setdefault(hand.winner, entry)

    if not bluffs:
        print('No bluffs found: every fold was made against the stronger hand.')
        return
    print('Biggest pots won with the weaker hand\n')
    print('{:<4}{:<18}{:>6}{:>9}  {:<8}{:>6}  {}'.format('#', 'Bot', 'Pot', 'Equity', 'Street', 'Hand', 'Log'))
    for i, (pot, eq, log, hand, street) in enumerate(bluffs, 1):
        print('{:<4}{:<18}{:>6}{:>8.0%}  {:<8}{:>6}  {}'.format(
            i, hand.winner[:17], pot, eq, street, hand.number, shown(log)))
    pot, eq, log, hand, street = bluffs[0]
    print('\nBest Bluff: {} won a {}-chip pot on the {} of hand {} holding {} ({:.0%} to win) '
          'when {} folded {}.'.format(hand.winner, pot, street.lower(), hand.number,
                                      ' '.join(hand.hole[hand.winner]), eq, hand.folded,
                                      ' '.join(hand.hole[hand.folded])))
    print('Show it with:\n  python3 organizer/view_hands.py {} --hand {} --step'.format(
        shown(os.path.dirname(log)), hand.number))
    print('\nEach bot\'s best bluff:')
    for team in sorted(best_by_team, key=lambda t: best_by_team[t][0], reverse=True):
        pot, eq, log, hand, street = best_by_team[team]
        print('  {:<18} {:>5}-chip pot, {:.0%} equity, hand {} ({})'.format(
            team[:17], pot, eq, hand.number, shown(os.path.dirname(log))))
    missing = sorted(teams - set(best_by_team))
    if missing:
        print('  No bluffs: ' + ', '.join(missing))


if __name__ == '__main__':
    main()
