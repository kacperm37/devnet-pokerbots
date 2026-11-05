# Tests

Run everything from the repo root with the virtual environment active. The tests use only the standard library's `unittest`, so there's nothing extra to install.

## Automated tests

```
python3 -m unittest discover -s tests -v
```

That runs about 40 tests in roughly 20 seconds. Each test builds the bots it needs in a temporary folder, so nothing in the repo changes.

| File | What it checks |
| --- | --- |
| `test_rules.py` | Betting rules from the participant guide: blinds, minimum raises (including the "bet 10, raise to 30, re-raise to at least 50" example), all-ins, folds, showdowns, split pots. |
| `test_engine.py` | Duplicate deals, the hidden seed, the fixed run command, Unix sockets, and what happens when a bot crashes, makes illegal moves, runs out of clock, stalls more than the per-decision limit, or prints too much. |
| `test_tools.py` | `check_bot.py`, the tournament runner (including reruns with saved seeds), the standings order, the game log parser, Best Bluff equity math, and the hand viewer. |
| `test_human_player.py` | How Beat the Champion turns typed input into moves. |
| `test_sandbox.py` | Bots that try to escape their containers. Skipped unless you turn it on; see below. |

To run one file or one test:

```
python3 -m unittest discover -s tests -p test_engine.py -v
python3 -m unittest discover -s tests -p test_engine.py -k crash
```

## Sandbox tests (run on the official machine)

These start real containers, so build the image first (see `organizer/README.md`):

```
POKERBOTS_TEST_SANDBOX=podman python3 -m unittest discover -s tests -p test_sandbox.py -v
```

Add `POKERBOTS_TEST_SELINUX=1` on Fedora or CentOS, and `POKERBOTS_TEST_IMAGE=name` if your image isn't called `devnet-pokerbots`. The tests check that a bot:

- can't reach the internet or look up hostnames
- can't see the deck seed or any other engine setting
- can see only its own process and its own socket
- can't write to its folder, while `/tmp` works and is wiped between games
- isn't running as root
- is stopped by the process limit (threads) and the 2 GB memory limit, without affecting its opponent

If any of these fail on the VM, don't run the final until it's fixed.

## Manual checks

These cover what automated tests can't: the interactive tools, the projector, and the setup a team will actually follow. Try them once before kickoff.

**As a team would**
1. On a fresh clone, follow the root README's Quick start exactly. If you can, also try it on a Windows or Mac laptop, using `py -3.12` on Windows.
2. Copy `python_skeleton` to `../my_bot`, set `PLAYER_1_PATH = '../my_bot'`, and run `python3 engine.py`. Open `gamelog.txt` and `A.txt`.
3. Run `python3 check_bot.py ../my_bot`. It should PASS.
4. Break the bot on purpose (add `raise ValueError('test')` in `get_action`) and run the check again. It should FAIL and show the traceback with the hand number.
5. Add `import pandas` to the top of `player.py`. The check should warn that it isn't approved.
6. Set `STARTING_GAME_CLOCK = 30.` in `config.py` and run the check. It should warn that `config.py` differs and still use the official settings. Change it back afterward.
7. Make `../my_bot` a git repo as described under Submitting in the README, then push it to a private GitHub repo with you as a collaborator. That's a dry run of a real submission.

**As the organizer**

8. Clone that test repo into `submissions/Test_Team`, add a copy of `house_bots/rule_book` as `submissions/House`, and run the final command from `organizer/README.md` with `--hands 300`. Read `standings.txt`.
9. Rerun one matchup with `--reuse-seeds` and `--only`. A deterministic bot like `rule_book` should produce exactly the same score.
10. Run `best_bluff.py` on the results, then paste the command it prints to replay the hand with `--step`.
11. On the projector, check that the card colors in `view_hands.py` are readable. If they aren't, use `--no-color`.

**Beat the Champion**

12. Play 5 hands against `house_bots/rule_book`. At each prompt, try `?`, `k`, `c`, `f`, `r` with an amount, `h`, `p`, `a`, an amount that's too big, and some random text. Every bad input should ask again, never crash or make a move.
13. Play to a showdown and check that the opponent's cards and the running total make sense, then replay that hand with `view_hands.py`.
14. On the VM, run it again with `--sandbox podman`. Then point it at a bot that crashes at startup. It should say "Could not start the game" before dealing any cards.
