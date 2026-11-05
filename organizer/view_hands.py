'''
Hand viewer: shows hands from a game log in the terminal, for the results reveal.

    python3 organizer/view_hands.py LOG [options]

LOG is a gamelog.txt, or a folder that contains one (like results/A_vs_B/game1).

Options:
    --hand 37            show this hand (repeatable)
    --biggest 5          show the 5 biggest pots (the default if you pick nothing)
    --step               pause for Enter after every action, for a live reveal
    --no-color           plain text, e.g. for copying into slides
'''
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import eval7  # noqa: E402
from gamelog import parse  # noqa: E402

SUITS = {'s': ('♠', '97'), 'h': ('♥', '91'), 'd': ('♦', '94'), 'c': ('♣', '92')}
COLOR = sys.stdout.isatty()


def paint(text, code):
    return '\033[{}m{}\033[0m'.format(code, text) if COLOR else text


def bold(text):
    return paint(text, '1')


def dim(text):
    return paint(text, '2')


def card(c):
    rank = '10' if c[0] == 'T' else c[0]
    symbol, color = SUITS[c[1]]
    return paint(rank + symbol, '1;' + color)


def cards(cs):
    return ' '.join(card(c) for c in cs) if cs else dim('(none)')


def hand_name(hole, board):
    if len(board) < 5 or not hole:
        return None
    return eval7.handtype(eval7.evaluate([eval7.Card(c) for c in hole + board]))


def find_log(path):
    if os.path.isdir(path):
        path = os.path.join(path, 'gamelog.txt')
    if not os.path.isfile(path):
        sys.exit('No game log at ' + path)
    return path


def pause(step):
    if step:
        try:
            input(dim('  ...'))
        except EOFError:
            pass


def show(hand, step):
    width = max(len(p) for p in hand.players) + 2
    print(bold('Hand #{}'.format(hand.number)) + dim('  ·  {} is the button'.format(hand.button)))
    for p in hand.players:
        print('  {:<{w}} {}   {}'.format(p, cards(hand.hole.get(p, [])),
                                       dim('net so far {:+,}'.format(hand.bankroll_before[p])), w=width))
    print()
    pause(step)
    street = None
    for a in hand.actions:
        if a.street != street:
            street = a.street
            header = bold(street.upper())
            if a.board:
                header += '  ' + cards(a.board)
            print(header)
            pause(step and street != 'Preflop')
        verb = a.verb + (' {}'.format(a.amount) if a.verb in ('bets', 'raises to') else '')
        line = '  {:<{w}} {}'.format(a.player, verb, w=width)
        print('{:<{pad}}{}'.format(line, dim('pot {}'.format(a.pot)), pad=width + 22))
        pause(step)
    for note in hand.notes:
        print(paint('  ! ' + note, '33'))
    print()
    winner = hand.winner
    if winner is None:
        print(bold('Split pot'))
    elif hand.showdown:
        loser = [p for p in hand.players if p != winner][0]
        win_name, lose_name = hand_name(hand.hole[winner], hand.board), hand_name(hand.hole[loser], hand.board)
        print(bold('{} wins {} at showdown'.format(winner, hand.deltas[winner])) +
              dim('  ({} beats {})'.format(win_name, lose_name)))
    else:
        print(bold('{} wins {} when {} folds'.format(winner, hand.deltas[winner], hand.folded)))
    print(dim('-' * 60))
    print()


def main():
    global COLOR
    parser = argparse.ArgumentParser(description='Show hands from a game log.')
    parser.add_argument('log')
    parser.add_argument('--hand', type=int, action='append', default=[])
    parser.add_argument('--biggest', type=int)
    parser.add_argument('--step', action='store_true')
    parser.add_argument('--no-color', action='store_true')
    args = parser.parse_args()
    if args.no_color:
        COLOR = False
    title, hands = parse(find_log(args.log))
    by_number = {h.number: h for h in hands}
    chosen = [by_number[n] for n in args.hand if n in by_number]
    missing = [n for n in args.hand if n not in by_number]
    if missing:
        print('No hand numbered ' + ', '.join(map(str, missing)))
    if args.biggest or not args.hand:
        k = args.biggest or 5
        chosen += sorted(hands, key=lambda h: h.pot, reverse=True)[:k]
    print(dim(title.replace('DevNet.CSU Pokerbots - ', '')) + '\n')
    for hand in chosen:
        show(hand, args.step)


if __name__ == '__main__':
    main()
