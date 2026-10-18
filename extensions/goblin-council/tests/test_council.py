"""Deterministic transaction/workflow tests; optional real native sandbox probes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / '.agents/skills/goblin/scripts'))
import council as c
import worktree as w


def task(mode='standard', **scores):
    return dict(objective='Repair fixture', scope=['value.txt'], acceptance=['value is repaired'],
                depth=2, blast=1, ambiguity=0, risk=1, mode=mode,
                routing_basis='Bounded fixture contract', validation=[], no_tests_reason='Mock fixture', **{}) | scores


def review(tx, verdict='PASS', restart=False):
    return dict(candidate_id=tx.m['candidate_id'], verdict=verdict, defects=[],
                repair_plan=['Repair value'] if verdict == 'ESCALATE' else [], restart_required=restart)


class RoutingTests(unittest.TestCase):
    def test_matrix(self):
        cases = [((0,0,0,0),'SINGLE'), ((1,1,0,1),'SINGLE'), ((1,1,1,1),'CASCADE'),
                 ((2,1,0,1),'CASCADE'), ((0,0,0,2),'CRITIQUE'), ((3,0,0,0),'CRITIQUE'),
                 ((0,3,0,0),'CRITIQUE'), ((2,2,0,0),'CRITIQUE'), ((0,0,3,0),'BLOCKED')]
        for scores, expected in cases:
            self.assertEqual(c.route(*scores), expected)
        self.assertEqual(c.route(0,0,0,0,'max'), 'CASCADE')
        self.assertEqual(c.route(2,0,0,0,'max'), 'CRITIQUE')
        for bad in [True, -1, 4, '1']:
            with self.assertRaises(w.CouncilError): c.route(bad,0,0,0)

    def test_effort_and_model_routes(self):
        for role in ['goblin-drafter','goblin-judge','goblin-critic-arch','goblin-critic-sec']:
            self.assertEqual(c.selection(role, task('max'))[1], 'high')
        self.assertEqual(c.selection('goblin-drafter', task(), repair=True), ('gpt-5.6-sol','high'))
        self.assertEqual(c.selection('goblin-drafter', task(depth=1)), ('gpt-5.6-luna','medium'))

    def test_bad_catalog_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'catalog.json'; p.write_text('{"models": []}')
            with self.assertRaises(w.CouncilError): c.check_model('unknown','high',p)

    def test_config_and_roles_parse(self):
        config = c.tomllib.loads((PACKAGE/'.codex/config.toml').read_text())
        self.assertEqual(config['agents']['max_concurrent_threads_per_session'],4)
        for path in c.ROLES.glob('*.toml'):
            data = c.tomllib.loads(path.read_text())
            self.assertEqual(data['name'], path.stem)
            self.assertTrue(data['developer_instructions'])
            self.assertNotIn('sandbox_mode',data)
        self.assertFalse(json.loads(c.SCHEMA.read_text())['additionalProperties'])


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='council-test-')
        self.repo = Path(self.temp.name)/'repo'; self.repo.mkdir()
        w.git(self.repo,'init','-q')
        w.git(self.repo,'config','user.name','Test')
        w.git(self.repo,'config','user.email','test@localhost')
        w.git(self.repo,'config','commit.gpgsign','false')
        (self.repo/'value.txt').write_text('base\n')
        (self.repo/'delete.txt').write_text('delete\n')
        (self.repo/'.gitignore').write_text('__pycache__/\nignored.txt\n')
        w.git(self.repo,'add','.')
        w.git(self.repo,'commit','-qm','fixture')
        self.runs = []

    def tearDown(self):
        for tx in self.runs:
            tx.cleanup()
        self.temp.cleanup()

    def tx(self, repo=None):
        root = repo or self.repo
        m = w.init(root); tx = w.Transaction(root,m['id']); self.runs.append(tx)
        return tx

    def dirty(self):
        (self.repo/'value.txt').write_text('staged\n')
        w.git(self.repo,'add','value.txt')
        (self.repo/'value.txt').write_text('unstaged\n')
        (self.repo/'untracked.bin').write_bytes(b'\x00\xffdirty')
        (self.repo/'ignored.txt').write_text('private cache')
        (self.repo/'delete.txt').unlink()

    def approve(self,tx):
        tx.record_review('goblin-judge',review(tx))
        tx.m['validation'] = dict(candidate_id=tx.m['candidate_id'],passed=True)
        tx.save()


class TransactionTests(Fixture):
    def test_snapshot_rehashes_same_size_edits_without_touching_real_index(self):
        # Make the real index deliberately trust a stale stat entry. A snapshot
        # must still hash the current bytes, including staged ignored files.
        w.git(self.repo, 'config', 'core.trustctime', 'false')
        w.git(self.repo, 'config', 'core.checkStat', 'minimal')
        target = self.repo/'value.txt'
        original = target.stat()
        w.git(self.repo, 'update-index', '--refresh')
        target.write_text('next\n')
        os.utime(target, ns=(original.st_atime_ns, original.st_mtime_ns))
        (self.repo/'ignored.txt').write_text('tracked ignored content\n')
        w.git(self.repo, 'add', '-f', 'ignored.txt')
        (self.repo/'intent.txt').write_text('intent to add\n')
        w.git(self.repo, 'add', '-N', 'intent.txt')
        before = w.index_path(self.repo).read_bytes()
        snapshot = w.tree(self.repo, w.paths(self.repo)[1])
        self.assertEqual(w.git(self.repo, 'show', snapshot+':value.txt'), b'next\n')
        self.assertEqual(w.git(self.repo, 'show', snapshot+':ignored.txt'), b'tracked ignored content\n')
        self.assertEqual(w.git(self.repo, 'show', snapshot+':intent.txt'), b'intent to add\n')
        self.assertEqual(w.index_path(self.repo).read_bytes(), before)

    def test_dirty_snapshot_and_abandon_preserve_index_and_contents(self):
        self.dirty()
        before = w.fingerprint(self.repo,w.paths(self.repo)[1])
        tx = self.tx()
        self.assertEqual(w.raw_manifest(tx.candidate), before['raw'])
        self.assertFalse((tx.candidate/'ignored.txt').exists())
        (tx.candidate/'value.txt').write_text('rejected\n')
        tx.abandon()
        self.assertEqual(before,w.fingerprint(self.repo,tx.state))
        self.assertEqual((self.repo/'ignored.txt').read_text(),'private cache')
        self.assertFalse(tx.container.exists())

    def test_promotion_preserves_staging_and_handles_binary_rename_delete(self):
        self.dirty(); tx = self.tx()
        before_index = w.index_path(self.repo).read_bytes()
        (tx.candidate/'value.txt').write_text('repaired\n')
        (tx.candidate/'untracked.bin').rename(tx.candidate/'renamed.bin')
        (tx.candidate/'new.bin').write_bytes(b'\x00\x01\xfe')
        tx.freeze(); self.approve(tx); tx.promote()
        self.assertEqual(tx.m['status'],'PROMOTED')
        self.assertEqual(w.index_path(self.repo).read_bytes(),before_index)
        self.assertEqual(w.git(self.repo,'show',':value.txt'),b'staged\n')
        self.assertEqual((self.repo/'value.txt').read_text(),'repaired\n')
        self.assertEqual((self.repo/'renamed.bin').read_bytes(),b'\x00\xffdirty')
        self.assertFalse((self.repo/'delete.txt').exists())
        self.assertFalse((self.repo/'untracked.bin').exists())
        self.assertFalse(tx.container.exists())

    def test_primary_concurrent_edit_blocks_promotion(self):
        tx = self.tx(); (tx.candidate/'value.txt').write_text('candidate\n')
        tx.freeze(); self.approve(tx)
        (self.repo/'other.txt').write_text('human edit')
        with self.assertRaisesRegex(w.CouncilError,'Primary HEAD'): tx.promote()
        self.assertEqual(tx.m['status'],'PROMOTION_BLOCKED')
        self.assertEqual((self.repo/'value.txt').read_text(),'base\n')
        self.assertEqual((self.repo/'other.txt').read_text(),'human edit')

    def test_stale_and_invalid_review(self):
        tx = self.tx(); tx.freeze()
        bad = review(tx); bad['candidate_id']='stale'
        with self.assertRaises(w.CouncilError): tx.record_review('goblin-judge',bad)
        bad = review(tx); bad['defects']=[dict(severity='blocking',path='value.txt',line=1,evidence='bad',fix='fix')]
        with self.assertRaises(w.CouncilError): tx.record_review('goblin-judge',bad)
        bad['verdict']='ESCALATE'; bad['defects'][0]['line']=-1
        with self.assertRaises(w.CouncilError): tx.record_review('goblin-judge',bad)

    def test_modified_candidate_review_and_patch_block(self):
        for location in ['candidate','review','patch']:
            with self.subTest(location=location):
                tx=self.tx(); tx.freeze(); self.approve(tx)
                if location=='patch': Path(tx.m['patch']).write_bytes(b'tampered')
                else: (Path(tx.m[location])/'value.txt').write_text('tampered\n')
                with self.assertRaises(w.CouncilError): tx.promote()

    def test_missing_validation_blocks(self):
        tx=self.tx(); tx.freeze(); tx.record_review('goblin-judge',review(tx))
        with self.assertRaisesRegex(w.CouncilError,'Validation'): tx.promote()

    def test_linked_worktree_uses_common_state(self):
        linked=Path(self.temp.name)/'linked'
        w.git(self.repo,'worktree','add','--detach',linked,'HEAD')
        try:
            tx=self.tx(linked)
            self.assertEqual(tx.state,w.paths(self.repo)[1])
            self.assertEqual(tx.root,linked.resolve())
            tx.abandon()
            self.runs.remove(tx)
        finally: w.git(self.repo,'worktree','remove','--force',linked)

    def test_reset_uses_original_dirty_baseline(self):
        self.dirty(); tx=self.tx()
        (tx.candidate/'value.txt').write_text('wrong')
        tx.freeze(); tx.reset()
        self.assertEqual(w.raw_manifest(tx.candidate),tx.m['baseline']['raw'])
        self.assertEqual(tx.m['reviews'],[])

    def test_control_edits_rejected(self):
        tx=self.tx(); (tx.candidate/'.codex').mkdir()
        (tx.candidate/'.codex/config.toml').write_text('')
        with self.assertRaisesRegex(w.CouncilError,'protected'): tx.freeze()

    def test_lease_and_cleanup_guards(self):
        tx=self.tx()
        with tx.lease():
            with self.assertRaises(w.CouncilError):
                with tx.lease(): pass
        with self.assertRaises(w.CouncilError): tx.remove_checkout(self.repo)
        tx.m['status']='PROMOTING'
        with self.assertRaises(w.CouncilError): tx.abandon()

    def test_eol_normalization_fails_without_mutating_primary(self):
        (self.repo/'.gitattributes').write_text('*.txt text eol=lf\n')
        (self.repo/'value.txt').write_bytes(b'raw\r\n')
        before=w.index_path(self.repo).read_bytes()
        with self.assertRaisesRegex(w.CouncilError,'raw contents'): w.init(self.repo)
        self.assertEqual((self.repo/'value.txt').read_bytes(),b'raw\r\n')
        self.assertEqual(w.index_path(self.repo).read_bytes(),before)
        for p in w.paths(self.repo)[1].glob('*/state.json'):
            self.runs.append(w.Transaction(self.repo,p.parent.name))

    @unittest.skipUnless(os.environ.get('GOBLIN_NATIVE_TESTS')=='1','opt-in OS sandbox integration')
    def test_native_sandbox_and_mcp_inventory(self):
        tx=self.tx(); tx.freeze(); native=c.Native(timeout=60)
        native.probe(tx,tx.candidate,True)
        native.probe(tx,Path(tx.m['review']),False)
        self.assertIsInstance(native.server_disables(tx.candidate),list)


class FakeNative:
    def __init__(self,reject_first=True,reject_final=False):
        self.calls=[]; self.reject_first=reject_first; self.reject_final=reject_final
        self.barrier=threading.Barrier(2); self.concurrent=False
    def stop(self): pass
    def stage(self,tx,role,task,context,writable=False,repair=False):
        self.calls.append((role,repair,context))
        if writable:
            (tx.candidate/'value.txt').write_text('repaired\n' if repair else 'draft\n')
            return 'CHANGES: fixture'
        if role.startswith('goblin-critic'):
            self.barrier.wait(timeout=5); self.concurrent=True
            return review(tx,'ESCALATE')
        reject=self.reject_final or (self.reject_first and not repair)
        return review(tx,'ESCALATE' if reject else 'PASS')
    def validate(self,tx,task):
        result=dict(candidate_id=tx.m['candidate_id'],passed=True)
        tx.m['validation']=result; tx.save(); return result


class WorkflowTests(Fixture):
    def test_single_cli_creates_no_transaction(self):
        p=Path(self.temp.name)/'task.json'; p.write_text(json.dumps(task(depth=0,blast=0,risk=0)))
        result=subprocess.run([sys.executable,str(Path(c.__file__)),'--repo',str(self.repo),'run','--task',str(p)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['topology'],'SINGLE')
        self.assertFalse((self.repo/'.git/goblin-council').exists())
    def test_cascade_escalation(self):
        tx=self.tx(); native=FakeNative()
        result=c.pipeline(tx,task(),native)
        self.assertEqual(result['status'],'PROMOTED')
        self.assertEqual([(r,repair) for r,repair,_ in native.calls],
                         [('goblin-drafter',False),('goblin-judge',False),('goblin-drafter',True),('goblin-judge',True)])
        self.assertEqual((self.repo/'value.txt').read_text(),'repaired\n')
    def test_max_critique_parallel_and_one_synthesis(self):
        tx=self.tx(); native=FakeNative()
        c.pipeline(tx,task('max',risk=2),native)
        self.assertTrue(native.concurrent)
        self.assertEqual(len(native.calls),5)
        critics=[context for role,_,context in native.calls if role.startswith('goblin-critic')]
        self.assertTrue(all('independent_reviews' not in ctx for ctx in critics))
        self.assertEqual(native.calls[-2][2]['phase'],'synthesize-and-revise')
    def test_repair_budget_exhausted_preserves_primary(self):
        self.dirty(); tx=self.tx(); native=FakeNative(reject_final=True)
        with self.assertRaisesRegex(w.CouncilError,'budget exhausted'): c.pipeline(tx,task(),native)
        self.assertEqual(tx.m['status'],'REJECTED')
        self.assertEqual(w.fingerprint(self.repo,tx.state),tx.m['baseline'])
        self.assertEqual(len(native.calls),4)
    def test_no_single_pipeline_draft(self):
        tx=self.tx(); native=FakeNative()
        with self.assertRaises(w.CouncilError): c.pipeline(tx,task(depth=0,blast=0,risk=0),native)
        self.assertEqual(native.calls,[])

if __name__=='__main__': unittest.main()
