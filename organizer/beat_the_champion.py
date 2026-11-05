'''
Beat the Champion: a person plays heads-up against a bot, live, in the terminal.

    python3 organizer/beat_the_champion.py CHAMPION_BOT [--name Kacper] [--hands 10]

The person has no clock. The champion gets its normal 180 seconds, which is
far more than it needs for a few hands. Run it on Linux or macOS, in a real
terminal (the person's moves are read from /dev/tty).

Options:
    --name Kacper              the player's name in the log
    --hands 10                 hands to play (default 10)
    --out results/btc          where the game log goes
    --sandbox podman           run the champion in its container, like the final;
                               takes the same --image and --selinux options as tournament.py

Afterward, replay any hand with organizer/view_hands.py.
'''
import argparse
import os
import re
import sys
import tempfile
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START_DIR = os.getcwd()
sys.path.insert(0, REPO)
os.chdir(REPO)  # the engine reads config.py from the current folder

import engine  # noqa: E402
from launchers import HostLauncher, ContainerLauncher  # noqa: E402

HUMAN_BOT = os.path.join(REPO, 'organizer', 'human_player')


def clean(name):
    return re.sub(r'[^A-Za-z0-9_-]', '_', name)


def main():
    parser = argparse.ArgumentParser(description='Play heads-up against a bot.')
    parser.add_argument('champion', help='the champion\'s bot folder')
    parser.add_argument('--name', default='challenger')
    parser.add_argument('--hands', type=int, default=10)
    parser.add_argument('--out', default=os.path.join('results', 'beat_the_champion'))
    parser.add_argument('--sandbox', choices=['podman', 'docker'])
    parser.add_argument('--image', default='devnet-pokerbots')
    parser.add_argument('--python', default='python3')
    parser.add_argument('--selinux', action='store_true')
    parser.add_argument('--extra-mount', action='append', default=[], help=argparse.SUPPRESS)
    args = parser.parse_args()

    champion_dir = os.path.abspath(os.path.join(START_DIR, args.champion))
    if not os.path.isfile(os.path.join(champion_dir, 'player.py')):
        sys.exit('No player.py in ' + champion_dir)
    if not os.path.exists('/dev/tty'):
        sys.exit('Beat the Champion needs a terminal on Linux or macOS.')
    human = clean(args.name)
    champion = clean(os.path.basename(champion_dir.rstrip('/'))) or 'champion'
    if champion == human:
        champion += '_bot'
    out = os.path.join(START_DIR, args.out)

    socket_dir = None
    if args.sandbox:
        socket_dir = tempfile.mkdtemp(prefix='pb-')
        os.chmod(socket_dir, 0o755)
        champion_launcher = ContainerLauncher(runtime=args.sandbox, image=args.image, python=args.python,
                                              game_id='btc', extra_mounts=args.extra_mount,
                                              selinux=args.selinux)
    else:
        champion_launcher = HostLauncher()

    os.environ['BEAT_THE_CHAMPION_HANDS'] = str(args.hands)
    print('\nBeat the Champion: {} vs {}, {} hands. Type ? at any prompt for help.'.format(
        human, champion, args.hands))
    try:
        result = engine.Game((human, HUMAN_BOT), (champion, champion_dir), num_rounds=args.hands,
                             official=True, launcher=(HostLauncher(), champion_launcher),
                             socket_dir=socket_dir, log_dir=out, quiet=True,
                             clocks=(10 ** 9, None), read_timeouts=(None, engine.CONNECT_TIMEOUT),
                             require_connection=True).run()
    except RuntimeError as error:
        sys.exit('\nCould not start the game: {}'.format(error))
    finally:
        if socket_dir:
            shutil.rmtree(socket_dir, ignore_errors=True)

    me, bot = result['players']
    print('\n' + '=' * 54)
    if me['bankroll'] > 0:
        verdict = '{} beat the champion by {} chips!'.format(human, me['bankroll'])
    elif me['bankroll'] < 0:
        verdict = 'The champion wins by {} chips.'.format(-me['bankroll'])
    else:
        verdict = 'Dead even.'
    print(verdict)
    for p in (me, bot):
        ev = p['events']
        if not ev['connected'] or ev['disconnected'] or ev['ran_out_of_time']:
            print('Note: {} had a problem during the game: {}'.format(p['name'], ev))
    shown = os.path.relpath(out, START_DIR) if out.startswith(START_DIR + os.sep) else out
    print('Replay a hand with: python3 organizer/view_hands.py {} --hand 1'.format(shown))


if __name__ == '__main__':
    main()
