# Organizer tools

Everything here is for running the tournament. Teams don't need any of it.

| File | What it does |
| --- | --- |
| `tournament.py` | Runs the round-robin of duplicate matches and writes the standings. |
| `Containerfile` | The image every bot runs in on the official machine. |
| `best_bluff.py` | Finds the Best Bluff award winner in the final's logs. |
| `view_hands.py` | Shows hands from a log in the terminal, for the reveal. |
| `beat_the_champion.py` | Lets a person play the champion bot live. |
| `human_player/` | The "bot" that asks the person for each move. |
| `gamelog.py` | Shared code that reads `gamelog.txt` files. |

All commands run from the repo root with the virtual environment active.

## Set up the official machine

```
sudo dnf install podman python3.12          # or apt on Ubuntu
git clone https://github.com/kacperm37/devnet-pokerbots.git
cd devnet-pokerbots
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
podman build -t devnet-pokerbots -f organizer/Containerfile .
```

Add any libraries approved in week 1 to the `pip install` line in `Containerfile`, then rebuild.

Before kickoff, run the test suite on the VM, including the sandbox tests. Those start bots that try to break the rules (open the network, read the seed, write files, start lots of threads, use too much memory) and check that each attempt fails. See `tests/README.md`:

```
python3 -m unittest discover -s tests -v
POKERBOTS_TEST_SANDBOX=podman python3 -m unittest discover -s tests -p test_sandbox.py -v
```

Then run a short sandboxed tournament with the house bots:

```
python3 organizer/tournament.py house_bots --sandbox podman --hands 300 --out results/test
```

On SELinux hosts (Fedora, CentOS, RHEL), add `--selinux` to every `--sandbox` command so the mounts get relabeled. This setup was tested with Docker using a stand-in image. Podman takes the same flags, but confirm it on the VM.

## Run the final

1. At the deadline, clone each team's repo into one folder, named after the team. Record each commit hash.

   ```
   git clone https://github.com/TEAM_OWNER/TEAM_REPO.git submissions/Team_Name
   git -C submissions/Team_Name log -1 --format=%H
   ```

2. Run the tournament:

   ```
   python3 organizer/tournament.py submissions --sandbox podman --out results/final
   ```

   It prints each matchup as it finishes, plus any problems (crashes, timeouts, illegal actions). Then it prints the standings and saves:
   - `results/final/standings.txt`
   - `results/final/results.json`, which includes the deck seeds. Keep it private until after the final.
   - a log folder for each game: `results/final/A_vs_B/game1/` and `game2/`

3. To rerun matchups with the same cards, for example after fixing a bug:

   ```
   python3 organizer/tournament.py submissions --sandbox podman --out results/rerun \
       --reuse-seeds results/final/results.json --only A_vs_B
   ```

## The reveal

Find the Best Bluff. This scans every log and takes about a minute:

```
python3 organizer/best_bluff.py results/final
```

It lists the biggest pots won by making the opponent fold while holding the weaker hand (under 50% equity at the fold), names the winner, and prints the command to replay it.

Step through hands on screen. `--step` waits for Enter after every action:

```
python3 organizer/view_hands.py results/final/A_vs_B/game1 --biggest 3 --step
python3 organizer/view_hands.py results/final/A_vs_B/game2 --hand 1469 --step
```

## Beat the Champion

Run it in a real terminal on Linux or macOS. The person's moves are typed at the keyboard.

```
python3 organizer/beat_the_champion.py submissions/Champion_Team --name Kacper --hands 10 --sandbox podman
```

- The person has no clock. The champion runs in its usual container with its normal clock.
- Moves: `f` fold, `k` check, `c` call, `r 40` raise to 40, `h` half pot, `p` pot, `a` all in, `?` help.
- If the champion can't start, the game stops before any hands are dealt instead of letting it fold every hand.
- The log goes to `results/beat_the_champion/`, so you can replay hands with `view_hands.py`.

## After the final

Publish `results/final` (logs, standings, and `results.json` with the seeds) once the 48-hour window closes. Publish a team's code only with that team's permission.
