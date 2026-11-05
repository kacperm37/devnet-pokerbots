'''
Sandbox tests: bots that try to break out of their containers. Run these on
the official machine after building the image (see tests/README.md):

    POKERBOTS_TEST_SANDBOX=podman python3 -m unittest discover -s tests -p test_sandbox.py -v

Optional settings:
    POKERBOTS_TEST_IMAGE=devnet-pokerbots   image to use
    POKERBOTS_TEST_SELINUX=1                relabel mounts (Fedora, CentOS)
'''
import json
import os
import shutil
import tempfile
import unittest

from helpers import TempDirTest, engine, make_bot, read, SKELETON
from launchers import ContainerLauncher

RUNTIME = os.environ.get('POKERBOTS_TEST_SANDBOX')
IMAGE = os.environ.get('POKERBOTS_TEST_IMAGE', 'devnet-pokerbots')
PYTHON = os.environ.get('POKERBOTS_TEST_PYTHON', 'python3')
SELINUX = os.environ.get('POKERBOTS_TEST_SELINUX') == '1'
EXTRA_MOUNTS = [m for m in os.environ.get('POKERBOTS_TEST_EXTRA_MOUNTS', '').split(';') if m]

PROBE = '''
import json, os, socket, threading, time
results = {}
def probe(name, fn):
    try:
        results[name] = ['ok', repr(fn())[:200]]
    except Exception as e:
        results[name] = ['blocked', type(e).__name__]
probe('internet', lambda: socket.create_connection(('1.1.1.1', 53), timeout=3))
probe('dns', lambda: socket.getaddrinfo('github.com', 443))
probe('seed_env', lambda: [k for k in os.environ if k.startswith('POKERBOTS')])
probe('processes', lambda: sorted(p for p in os.listdir('/proc') if p.isdigit()))
probe('sockets', lambda: os.listdir('/sock'))
probe('write_bot_folder', lambda: open('/bot/notes.txt', 'w').write('x'))
probe('write_tmp', lambda: open('/tmp/scratch', 'w').write('x'))
probe('uid', lambda: os.getuid())
count = 0
try:
    for _ in range(300):
        threading.Thread(target=time.sleep, args=(20,), daemon=True).start()
        count += 1
except Exception:
    pass
results['threads_started'] = count
print('PROBE ' + json.dumps(results), flush=True)
'''


@unittest.skipUnless(RUNTIME in ('podman', 'docker'), 'set POKERBOTS_TEST_SANDBOX=podman (or docker) to run')
class TestSandbox(TempDirTest):

    def play(self, bot_a, bot_b, hands=20):
        sockets = tempfile.mkdtemp(prefix='pb-')
        os.chmod(sockets, 0o755)
        self.addCleanup(shutil.rmtree, sockets, True)
        launcher = ContainerLauncher(runtime=RUNTIME, image=IMAGE, python=PYTHON, game_id='test',
                                     selinux=SELINUX, extra_mounts=EXTRA_MOUNTS)
        logs = os.path.join(self.tmp, 'logs')
        result = engine.Game(('A', bot_a), ('B', bot_b), num_rounds=hands, official=True,
                             launcher=launcher, socket_dir=sockets, log_dir=logs, quiet=True).run()
        return result, logs

    def test_plain_bots_play_normally(self):
        result, _ = self.play(SKELETON, SKELETON)
        for p in result['players']:
            self.assertTrue(p['events']['connected'], 'the container could not connect; check the image name')
            self.assertIsNone(p['events']['disconnected'])

    def test_escape_attempts_fail(self):
        prober = make_bot(self.tmp, 'prober', init=PROBE)
        os.environ['POKERBOTS_SEED'] = 'secret-seed'
        self.addCleanup(os.environ.pop, 'POKERBOTS_SEED', None)
        result, logs = self.play(prober, SKELETON)
        self.assertTrue(result['players'][0]['events']['connected'])
        line = [l for l in read(os.path.join(logs, 'A.txt')).splitlines() if l.startswith('PROBE ')][0]
        probes = json.loads(line[len('PROBE '):])
        self.assertEqual(probes['internet'][0], 'blocked', 'the bot reached the internet')
        self.assertEqual(probes['dns'][0], 'blocked', 'the bot could look up hostnames')
        self.assertEqual(probes['seed_env'], ['ok', '[]'], 'the bot could see engine settings')
        self.assertEqual(probes['sockets'], ['ok', "['engine.sock']"], 'the bot could see other sockets')
        self.assertEqual(probes['write_bot_folder'][0], 'blocked', 'the bot folder is writable')
        self.assertEqual(probes['write_tmp'][0], 'ok', '/tmp should be writable (and temporary)')
        self.assertNotEqual(probes['uid'], ['ok', '0'], 'the bot runs as root')
        processes = json.loads(probes['processes'][1].replace("'", '"'))
        self.assertLessEqual(len(processes), 2, 'the bot can see other processes: {}'.format(processes))
        self.assertLess(probes['threads_started'], 100, 'the process limit is not enforced')

    def test_memory_limit_stops_only_the_greedy_bot(self):
        greedy = make_bot(self.tmp, 'greedy', action='''
            if game_state.round_num == 3:
                hog = bytearray(3 * 1024 ** 3)  # 3 GB, over the 2 GB limit
                hog[::4096] = b'x' * len(hog[::4096])
        ''')
        result, _ = self.play(greedy, SKELETON, hands=10)
        me, other = result['players']
        self.assertEqual(me['events']['disconnected'], 3, 'the 3 GB allocation was not stopped')
        self.assertIsNone(other['events']['disconnected'])

    def test_nothing_survives_between_games(self):
        writer = make_bot(self.tmp, 'writer', init='''
            import os
            print('FOUND' if os.path.exists('/tmp/marker') else 'CLEAN', flush=True)
            open('/tmp/marker', 'w').write('x')
        ''')
        _, logs = self.play(writer, SKELETON, hands=3)
        _, logs = self.play(writer, SKELETON, hands=3)
        self.assertIn('CLEAN', read(os.path.join(logs, 'A.txt')))


if __name__ == '__main__':
    unittest.main()
