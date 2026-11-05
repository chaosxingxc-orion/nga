#!/usr/bin/env python3
"""DAG integration for the retained unified NPU host. CPU consumption is not implemented.

The orchestrator supplies trusted component-review pins at construction. Component
review is not deployment authorization; host lease acceptance remains authoritative.
This module does not grant dispatch permission: the host lease policy remains authoritative.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from tools import experiment_dag as D
from tools import unified_container_host_v1 as H
from tools import unified_resource_lease_v1 as U
from tools import r3_resource_adapter as R


def file_pin(path):
    path = Path(os.path.abspath(path))
    D.require(not any(x.is_symlink() for x in (path, *path.parents)), 'symlink evidence')
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def components():
    return [file_pin(p) for p in (Path(__file__), Path(H.__file__), Path(U.__file__),
            Path(R.__file__), Path(H.__file__).resolve().parents[1] / 'docker/engineering-base/schema.json')]


class HistoricalReleaseQuery:
    """Only for validating recorded releases; never use to decide a fresh claim.

    predecessor() calls conflict() last as a present-availability gate. Historical
    verification deliberately omits that gate while preserving real inspection.
    """
    def __init__(self, docker):
        self._docker = docker

    def inspect(self, name):
        return self._docker.inspect(name)

    def conflict(self, chip):
        return False  # No assertion about current physical availability.


class UnifiedDagAdapter:
    """Only exact, reviewed NPU host configs are admitted; no commands in binding."""
    def __init__(self, docker=None, start=None, trusted_review_pins=()):
        self.implementation_sha256 = file_pin(__file__)['sha256']
        self.docker = docker or H.Docker()
        self._start = start or self._host_start
        self._trusted_review_pins = tuple(dict(pin) for pin in trusted_review_pins)

    @staticmethod
    def _host_start(config):
        result = subprocess.run([sys.executable, str(Path(H.__file__).resolve()), 'start',
                                 '--config', config['path'], '--sha256', config['sha256']],
                                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return json.loads(result.stdout)

    def authorize(self, binding, review, node, graph_hash):
        D.exact(binding, ('schema', 'host_config'), 'binding')
        D.require(binding['schema'] == 'unified-dag-binding-v1' and node['lane'] == 'npu', 'NPU binding required')
        review_pin = node['action']['review']
        D.require(review_pin in self._trusted_review_pins and D.read_pin(review_pin) == review,
                  'component review lacks trusted orchestrator pin')
        D.exact(review, ('schema', 'decision', 'node', 'binding_sha256', 'components'), 'component review')
        D.require(review['schema'] == 'unified-dag-component-review-v1' and review['decision'] == 'accept'
                  and review['node'] == node['id'] and review['binding_sha256'] == D.digest(binding)
                  and review['components'] == components(), 'component review differs')
        c = D.read_pin(binding['host_config']); H.validate(c)
        lease = c['lease']
        D.require(sorted(node['devices']) == sorted(lease['eligible_device_ids']) and
                  lease['device_count'] == len(node['devices']), 'fixed devices differ')
        return True

    def reserve_and_start(self, binding, node, token):
        # Re-read the node's pinned review and all reviewed components immediately before start.
        actual = D.read_pin(node['action']['binding'])
        D.require(actual == binding, 'binding changed')
        self.authorize(binding, D.read_pin(node['action']['review']), node, '')
        result = self._start(binding['host_config'])
        D.require(type(result) is dict and result.get('status') == 'supervisor-started' and
                  type(result.get('pid')) is int and result['pid'] > 0, 'invalid supervisor receipt')
        return {'schema': 'unified-dag-supervisor-receipt-v1', 'token': token,
                'host_config': binding['host_config'], 'supervisor': result}

    def observe(self, node, rec):
        binding = D.read_pin(node['action']['binding'])
        self.authorize(binding, D.read_pin(node['action']['review']), node, '')
        c = D.read_pin(binding['host_config']); meta = H.metadata_dir(c)
        receipt = rec.get('receipt')
        if receipt is not None:
            D.require(receipt.get('schema') == 'unified-dag-supervisor-receipt-v1' and
                      receipt.get('token') == rec['token'] and receipt.get('host_config') == binding['host_config'], 'receipt differs')
        terminal = meta / 'terminal.json'; handoff = meta / 'cpu-handoff.json'
        release = U.paths(c['lease'], 'release')[1]
        if not (terminal.exists() and release.exists() and handoff.exists()):
            # Incomplete publication is not terminal evidence. Authenticate both
            # supervisor owner records, the live ledger binding and the container.
            try:
                owner = H.owner_identity(c)
                owner_paths = (meta / 'OWNER.json', Path(c['lease']['journal']) /
                               c['lease']['lease_id'] / 'host-owner.json')
                D.require(all(R.load(p) == owner for p in owner_paths), 'owner differs')
                claim_path = U.paths(c['lease'], 'claim')[1]
                claim = R.load(claim_path)
                D.require(claim.get('chips') == sorted(node['devices']), 'claim devices differ')
                _, ob = H.observe_binding(c, self.docker, claim, self.docker.image_id(c['image']))
                state = ob.get('State', {})
                D.require(state.get('Status') == 'running' and state.get('Running') is True,
                          'container not running')
                return {'state': 'running', 'facts': [], 'failed_facts': [],
                        'evidence': [file_pin(p) for p in (*owner_paths, claim_path,
                                      U.paths(c['lease'], 'binding')[1])]}
            except Exception:  # Missing, malformed, or unavailable observations are uncertain.
                return {'state': 'uncertain', 'facts': [], 'failed_facts': [], 'evidence': []}
        event = R.load(handoff)
        D.exact(event, ('schema', 'event_id', 'evidence', 'scientific_acceptance'), 'handoff')
        D.require(event['schema'] == 'unified-cpu-handoff-v1' and event['scientific_acceptance'] is False and
                  event['event_id'] == U.digest(event['evidence']), 'handoff identity')
        D.require(event['evidence'] == {'terminal': file_pin(terminal), 'release': file_pin(release)}, 'handoff pins')
        t = D.read_pin(event['evidence']['terminal']); rel = D.read_pin(event['evidence']['release'])
        claim = U.paths(c['lease'], 'claim')[1]; bind = U.paths(c['lease'], 'binding')[1]
        b = R.load(bind); chips = sorted(node['devices'])
        D.require(t.get('schema') == 'unified-container-terminal-v1' and type(t.get('exit_code')) is int and
                  t.get('launch_sha256') == U.digest(H.launch_spec(c)) and
                  t.get('container_id') == b.get('container_id') == rel.get('binding', {}).get('container_id') and
                  t['exit_code'] == rel.get('exit_code') and rel.get('binding') == b and
                  rel.get('config_sha256') == U.config_hash(c['lease']) and rel.get('chips') == chips,
                  'terminal/release mismatch')
        D.require(H.verify(c, self.docker, b['container_id'], chips, self.docker.image_id(c['image'])) is not None, 'container identity')
        refs = {'claim': file_pin(claim), 'release': file_pin(release), 'container': None, 'terminal': None}
        for chip in chips:
            entries = [x for x in rel['after']['free'] if x['chip'] == chip]
            D.require(len(entries) == 1, 'missing released chip')
            U.predecessor(c['lease'], entries[0], HistoricalReleaseQuery(self.docker), refs)
        return {'state': 'released' if t['exit_code'] == 0 else 'failed',
                'facts': ['resource_release'] + (['success'] if t['exit_code'] == 0 else []),
                'failed_facts': [] if t['exit_code'] == 0 else ['success'],
                'evidence': [file_pin(terminal), file_pin(release), file_pin(handoff), file_pin(claim), file_pin(bind)]}
