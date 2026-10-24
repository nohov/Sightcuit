#!/usr/bin/env python3
"""Bounded, resumable Herdr dispatch; no third-party dependencies."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'control' / 'state.json'
ROLES = {'labels': 'campus-labels', 'research': 'campus-data',
         'baseline': 'campus-baseline', 'audit': 'campus-audit'}


def call(*args):
    result = subprocess.run(['herdr', *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    try:
        return json.loads(result.stdout)['result']
    except (ValueError, KeyError):
        return {'output': result.stdout}


def save(state):
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2) + '\n')
    temp.replace(STATE)


def validate(role):
    path = ROOT / role / 'completion.json'
    if not path.exists():
        return False, 'completion.json missing'
    try:
        record = json.loads(path.read_text())
        for key in ('task', 'status', 'artifacts', 'checks', 'limitations', 'sources'):
            if key not in record:
                raise ValueError(f'missing {key}')
        if record['status'] != 'complete':
            raise ValueError(f"status={record['status']}")
        for key in ('artifacts', 'checks', 'limitations', 'sources'):
            if not isinstance(record[key], list):
                raise ValueError(f'{key} must be a list')
        if not record['artifacts']:
            raise ValueError('no artifacts')
        for name in record['artifacts']:
            artifact = (ROOT / name).resolve()
            if not artifact.is_relative_to((ROOT / role).resolve()):
                raise ValueError(f'outside owned directory: {name}')
            if not artifact.is_file():
                raise ValueError(f'missing artifact: {name}')
        return True, 'contract valid; semantic audit still required'
    except (ValueError, TypeError, OSError) as error:
        return False, str(error)


def dispatch(state, role):
    entry = state['roles'].setdefault(role, {})
    if entry.get('submitted'):
        print(f'{role}: already dispatched')
        return
    if not entry.get('pane'):
        tab = call('tab', 'create', '--workspace', state['workspace'],
                   '--cwd', str(ROOT), '--label', role, '--no-focus')
        entry['pane'] = tab['root_pane']['pane_id']
        save(state)
    if not entry.get('started'):
        print(f'{role}: starting Codex in {entry["pane"]} (up to 10 seconds)...', flush=True)
        for attempt in range(15):
            try:
                call('agent', 'start', ROLES[role], '--kind', 'codex', '--pane',
                     entry['pane'], '--timeout', '10000', '--', '--search', '-c',
                     'check_for_update_on_startup=false', '-C', str(ROOT))
                break
            except RuntimeError as error:
                if 'agent_pane_busy' not in str(error) or attempt == 14:
                    output = call('pane', 'read', entry['pane'], '--source',
                                  'detection', '--lines', '20').get('output', '')
                    raise RuntimeError(f'{role}: startup failed.\n{error}\n{output}') from error
                time.sleep(1)
        entry['started'] = True
        save(state)
    # Persist an in-flight marker before submission. Unknown outcomes require
    # inspection instead of automatic re-submission and duplicate work.
    if entry.get('submission_attempted'):
        raise RuntimeError(f'{role}: previous submission outcome unknown; inspect agent')
    entry['submission_attempted'] = True
    save(state)
    prompt = (ROOT / 'prompts' / f'{role}.txt').read_text()
    call('agent', 'prompt', ROLES[role], prompt)
    entry['submitted'] = True
    save(state)
    print(f'{role}: dispatched in {entry["pane"]}')


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    state = json.loads(STATE.read_text()) if STATE.exists() else {'roles': {}}
    if action == 'launch':
        if not state.get('workspace'):
            workspace = call('workspace', 'create', '--cwd', str(ROOT),
                             '--label', 'Campus scanner', '--no-focus')
            state['workspace'] = workspace['workspace']['workspace_id']
            save(state)
        for role in ('labels', 'research', 'baseline'):
            dispatch(state, role)
    elif action == 'audit':
        results = {role: validate(role) for role in ('labels', 'research', 'baseline')}
        if not all(value[0] for value in results.values()):
            raise RuntimeError(json.dumps(results, indent=2))
        if not state.get('workspace'):
            raise RuntimeError('launch first')
        dispatch(state, 'audit')
    elif action == 'status':
        live = call('agent', 'list').get('agents', [])
        for role, name in ROLES.items():
            pane = state['roles'].get(role, {}).get('pane')
            match = next((a for a in live if a.get('pane_id') == pane), {})
            print(json.dumps({'role': role, 'name': name, 'pane': pane,
                              'herdr_status': match.get('agent_status', 'not detected'),
                              'artifact_contract': validate(role)}))
    else:
        raise RuntimeError('use launch, status, or audit')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        sys.exit(str(error))
