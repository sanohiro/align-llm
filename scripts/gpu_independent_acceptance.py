#!/usr/bin/env python3
"""Independent G1 acceptance execution and content-bound replay."""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import stat
import subprocess
import time

from gpu_backend_recipe import RecipeError, canonical, retained_path
from gpu_independent_corpus import validate as validate_corpus, MAX_BYTES as CORPUS_LIMIT
from gpu_qualification_records import parse_record, validate_command, exact_keys, validate_profile_records, parse_json_object
from gpu_qualification_backend import stage
from gpu_qualification_native import prepare, success_metadata, failure as native_failure
from gpu_qualification_input import admit
from gpu_qualification_deadline import Deadline, sha256_file
from gpu_qualification_stream import NumericStream
from gpu_qualifier_process import run_owned_command, retained_file_row

ROOT = pathlib.Path(__file__).resolve().parents[1]
TIMEOUT_NS = 1800_000_000_000
RESULT_LIMIT = 16 * 1024**2


def digest(path, deadline=None):
    return sha256_file(path, deadline)


def source_files(root):
    names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).split(b'\0')
    return {name: digest(root / name) for name in sorted({raw.decode() for raw in names if raw})
            if name.startswith(('src/', 'scripts/', 'eval/')) or name in ('.align-revision', 'Makefile')}


def write(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open('xb') as output:
        output.write(data)
    return path


def json_file(path, limit=RESULT_LIMIT, *, framed=True):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= limit:
        raise RecipeError('acceptance input is not a bounded single-link regular file')
    return (parse_record if framed else parse_json_object)(path.read_bytes(), limit)


def comparator():
    spec = importlib.util.spec_from_file_location('independent_gpu_reference', ROOT / 'eval/gpu/compare-reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_inventory(root, deadline=None):
    rows = []
    for path in sorted(root.rglob('*')):
        if path.is_dir() and not path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == 'result.json':
            continue
        retained_path(relative, 'acceptance artifact')
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 4 * 1024**3:
            raise RecipeError('acceptance artifact is not a bounded single-link file')
        rows.append({'path': relative, 'bytes': info.st_size, 'sha256': digest(path, deadline)})
    return rows


def verify_build(directory, candidate):
    record = json_file(directory / 'build.json')
    fields = ('source_commit', 'source_dirty', 'source_files', 'align_revision', 'compiler_sha256',
              'bundle_id', 'executables', 'libraries', 'commands') if candidate else (
              'ggml_commit', 'driver_sha256', 'executable_sha256', 'libraries', 'compiler_sha256', 'commands')
    record = exact_keys(record, fields, 'independent build manifest')
    from gpu_backend_recipe import lowercase_hex
    lowercase_hex(record['source_commit'] if candidate else record['ggml_commit'], 40, 'independent build source')
    if candidate:
        lowercase_hex(record['align_revision'], 40, 'independent Align pin')
        lowercase_hex(record['bundle_id'], 64, 'independent bundle')
        if not isinstance(record['source_files'], dict) or not 1 <= len(record['source_files']) <= 8192:
            raise RecipeError('candidate source closure is invalid')
        for relative, expected in record['source_files'].items():
            retained_path(relative, 'candidate source')
            lowercase_hex(expected, 64, 'candidate source digest')
        if set(record['executables']) != {'runtime_case', 'runtime_immediate_eog_smoke'}:
            raise RecipeError('candidate build entrypoints are incomplete')
    if not isinstance(record['libraries'], dict) or not 3 <= len(record['libraries']) <= 128:
        raise RecipeError('independent build dependency closure is incomplete')
    if candidate and record['source_dirty'] is not False:
        raise RecipeError('shipping acceptance refuses a dirty candidate build')
    lowercase_hex(record['compiler_sha256'], 64, 'independent compiler')
    if not isinstance(record['commands'], list) or not record['commands']:
        raise RecipeError('independent build commands are absent')
    executables = record['executables'] if candidate else {'reference-acquire': record['executable_sha256']}
    for name, expected in executables.items():
        if name in ('.', '..') or '/' in name or digest(directory / name) != expected:
            raise RecipeError('acceptance executable differs from its build')
    for name, expected in record['libraries'].items():
        if name in ('.', '..') or '/' in name or digest(directory / 'lib' / name) != expected:
            raise RecipeError('acceptance dependency differs from its build')
    return record


def retain_build(source, target, candidate):
    record = verify_build(source, candidate)
    names = tuple(record['executables']) if candidate else ('reference-acquire',)
    for name in (*names, 'build.json'):
        shutil.copyfile(source / name, write_directory(target) / name)
        if name != 'build.json':
            (target / name).chmod(0o700)
    write_directory(target / 'lib')
    for name in record['libraries']:
        shutil.copyfile(source / 'lib' / name, target / 'lib' / name)
    verify_build(target, candidate)
    return record


def write_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def plan_for(profile, model, geometry, case, root, physical_input_root, options_path, output):
    return prepare(model_id=model['model_id'], geometry=geometry, calibration_case=case,
        model_path=pathlib.Path(physical_input_root) / model['model_path'],
        pack_path=pathlib.Path(physical_input_root) / model['pack_path'],
        geometry_path=pathlib.Path(physical_input_root) / model['geometry_path'],
        options_path=pathlib.Path(options_path), cache_budget_bytes=model['runtime_cache_budget_bytes'],
        stream_root=root / output, stream_name='numeric')


def attention_policy(corpus, model_id):
    return next(entry for entry in corpus["models"] if entry["model"]["model_id"] == model_id).get("attention_policy", "decomposed")


def expected_cases(corpus):
    for entry in corpus['models']:
        for case in entry['cases']:
            yield entry['model']['model_id'], case


def process(root, executable, input_path, role, directory, deadline):
    executable_token = '<' + role + '>:sha256:' + digest(executable)
    input_token = '<case-input>:sha256:' + digest(input_path)
    outcome = run_owned_command(kind='case', physical_argv=(str(executable), str(input_path)),
        logical_argv=(executable_token, input_token), mappings={executable_token: executable, input_token: input_path},
        cwd=root, home=root / 'home', temporary=root / 'tmp', timeout_seconds=1800, deadline_ns=deadline.monotonic_ns)
    record = {'command': outcome.command, 'terminal': outcome.terminal, 'exit_code': outcome.exit_code,
              'signal': outcome.signal, 'elapsed_ns': outcome.elapsed_ns,
              'descendants_before': outcome.descendants_before, 'descendants_after': outcome.descendants_after}
    for name in ('stdout', 'stderr'):
        captured = getattr(outcome, name)
        relative = directory + '/' + name
        write(root / relative, captured.retained)
        record[name] = retained_file_row(name, relative, captured)
    return record


def process_ok(record, *, output=None, plan=None):
    validate_command(record['command'], allow_sentinel=False, expected_kind='case')
    if record['terminal'] != 'PASS' or record['exit_code'] != 0 or record['signal'] is not None \
            or record['descendants_after'] != 0 or record['stdout']['truncated'] or record['stderr']['truncated']:
        if output is not None and plan is not None:
            try:
                fault = native_failure(output, plan)
            except RecipeError:
                pass
            else:
                raise RecipeError('native ' + fault['category'] + '/' + fault['stage'] + ' refused acceptance')
        raise RecipeError('independent acceptance process did not complete cleanly')


def validate_native(output, plan, bundle_id, device, caps, deadline):
    native = success_metadata(output, plan, expected_bundle_id=bundle_id, expected_device=device, deadline=deadline)
    observation = native.observation
    if observation['managed_host_peak_bytes'] + observation['application_host_reserved_bytes'] > caps['host_budget_bytes'] \
            or observation['managed_device_peak_bytes'] > caps['device_budget_bytes']:
        raise RecipeError('independent acceptance exceeds admitted managed capacity')
    return native


def match_repeat(path, plan, expected_sha256, deadline=None):
    """Validate a fresh complete stream and reuse semantics only for exactly identical bytes."""
    with NumericStream(path, model=plan.traversal.model,
                       maximum_bytes=plan.traversal.maximum_bytes, deadline=deadline) as stream:
        while (frame := stream.read_frame()) is not None:
            remaining = frame.payload_bytes
            while remaining:
                remaining -= len(stream.read_payload())
        if stream.sha256 != expected_sha256:
            raise RecipeError('fresh-process candidate repetition changed numeric bytes')


def bind_comparison_inventory(result):
    files = {row['path']: row for row in result['files']}
    for row in result['cases']:
        comparison = row['comparison']
        reference = row['directory'].rsplit('/', 1)[0] + '/reference'
        expected = {row['numeric']: comparison['candidate_sha256'],
            reference + '/index.jsonl': comparison['reference_index_sha256'],
            reference + '/production.json': comparison['reference_production_sha256']}
        expected.update({reference + '/' + name: value for name, value in comparison['reference_tensors'].items()})
        if any(path not in files or files[path]['sha256'] != value for path, value in expected.items()):
            raise RecipeError('compared artifact changed before acceptance publication')


def execute(profile_path, corpus_path, candidate_build, reference_build, destination):
    started = time.monotonic_ns()
    deadline = Deadline(started + TIMEOUT_NS)
    admitted = admit(profile_path)
    profile, bundle = admitted.records['profile'], admitted.records['bundle']
    corpus = validate_corpus(json_file(corpus_path, CORPUS_LIMIT), bundle_id=bundle['bundle_id'], models=profile['models'])
    if corpus['backend'] != bundle['backend']:
        raise RecipeError('independent corpus backend differs from the admitted package')
    candidate = verify_build(candidate_build, True)
    reference = verify_build(reference_build, False)
    if candidate['bundle_id'] != bundle['bundle_id'] or reference['ggml_commit'] != bundle['ggml']['commit']:
        raise RecipeError('independent builds do not bind the admitted backend')
    if source_files(ROOT) != candidate['source_files']:
        raise RecipeError('current executable input closure differs from the candidate build')
    if reference['driver_sha256'] != digest(ROOT / 'eval/gpu/reference-acquire.cpp'):
        raise RecipeError('independent reference driver differs from current source')
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink() or ROOT == destination or ROOT in destination.parents:
        raise RecipeError('acceptance output must be new and outside the source tree')
    destination.mkdir(mode=0o700)
    root = destination.resolve(strict=True)
    result = {'schema_version': 1, 'artifact_kind': 'GPU_INDEPENDENT_ACCEPTANCE_RESULT', 'status': 'FAIL',
              'origin_root': str(root), 'input_root': str(admitted.root), 'source_commit': candidate['source_commit'],
              'corpus_sha256': digest(corpus_path), 'profile_sha256': digest(profile_path),
              'references': [], 'cases': [], 'elapsed_ns': 0, 'failure': '', 'cleanup': False, 'files': []}
    try:
        write(root / 'corpus.json', corpus_path.read_bytes())
        write(root / 'profile.json', profile_path.read_bytes())
        write(root / 'bundle.json', admitted.bundle_raw)
        write(root / 'admission/runtime-option.json', admitted.runtime_option_raw)
        write(root / 'admission/align-source.json', admitted.align_source.manifest_raw)
        write(root / 'admission/ggml-source.json', admitted.ggml_source.manifest_raw)
        for index, raw in enumerate(admitted.calibration_raws):
            write(root / 'admission' / f'calibration-{index}.json', raw)
        retain_build(candidate_build, root / 'candidate', True)
        retain_build(reference_build, root / 'reference', False)
        for relative in candidate['source_files']:
            write(root / 'source' / relative, (ROOT / relative).read_bytes())
        options = dict(profile['runtime_options'][0])
        options.pop('option_id')
        bundle_root = stage(admitted, root).root
        options['backend_bundle'] = str(bundle_root)
        write(root / 'runtime-options.json', canonical(options))
        for model in profile['models']:
            write(root / 'geometry' / (model['model_id'] + '.json'), admitted.read_retained(model['geometry_path'], 16 * 1024**2))
        write_directory(root / 'home')
        write_directory(root / 'tmp')
        compare = comparator()
        for ordinal, (model_id, case) in enumerate(expected_cases(corpus)):
            deadline.check()
            model = next(m for m in profile['models'] if m['model_id'] == model_id)
            geometry = json_file(root / 'geometry' / (model_id + '.json'), framed=False)
            base = 'cases/' + str(ordinal)
            reference_relative = base + '/reference'
            write_directory(root / reference_relative)
            plugin = next(a['path'] for a in bundle['artifacts'] if a['role'] == 'backend_plugin')
            request = {'model_path': str(admitted.root / model['model_path']), 'plugin_path': str(bundle_root / plugin),
                       'prompt_token_ids': case['prompt_token_ids'], 'maximum_tokens': case['maximum_tokens'],
                       'seed': case['seed'] if case['sampler_mode'] == 'seeded' else None,
                       'output_root': str(root / reference_relative)}
            if corpus['schema_version'] == 2:
                request['attention_policy'] = attention_policy(corpus, model_id)
            input_path = write(root / base / 'reference-input.json', canonical(request))
            command = process(root, root / 'reference/reference-acquire', input_path, 'independent-reference', base + '/reference-process', deadline)
            result['references'].append({'model_id': model_id, 'case_id': case['case_id'], 'directory': reference_relative,
                                         'input': base + '/reference-input.json', 'process': command})
            process_ok(command)
            for repeat in (0, 1):
                relative = base + '/repeat-' + str(repeat)
                write_directory(root / relative)
                plan = plan_for(profile, model, geometry, case, root, admitted.root, root / 'runtime-options.json', relative)
                plan = dataclasses.replace(plan, attention_policy=attention_policy(corpus, model_id))
                input_path = write(root / relative / 'input.json', plan.input_bytes())
                name = 'runtime_immediate_eog_smoke' if case['input_mode'] == 'continuation' else 'runtime_case'
                command = process(root, root / 'candidate' / name, input_path, 'candidate', relative, deadline)
                row = {'model_id': model_id, 'case_id': case['case_id'], 'repeat': repeat, 'directory': relative,
                       'input': relative + '/input.json', 'numeric': relative + '/numeric', 'executable': name, 'process': command}
                result['cases'].append(row)
                process_ok(command, output=(root / relative / 'stdout').read_bytes(), plan=plan)
                native = validate_native((root / relative / 'stdout').read_bytes(), plan, bundle['bundle_id'], options['device'], options, deadline)
                if repeat == 0:
                    comparison = compare.compare(root / reference_relative, plan.stream_path, geometry, case, deadline=deadline)
                    if not comparison['bitwise_equal']:
                        raise RecipeError('independent all-tensor comparison failed')
                    row['comparison'] = comparison
                else:
                    previous = result['cases'][-2]
                    match_repeat(plan.stream_path, plan, previous['comparison']['candidate_sha256'], deadline)
                    row['comparison'] = dict(previous['comparison'])
                    plan.stream_path.unlink()
                    row['numeric'] = previous['numeric']
                deadline.check()
                print(model_id, case['case_id'], 'repeat', repeat, 'PASS', flush=True)
        admitted.recheck()
        verify_build(candidate_build, True)
        verify_build(reference_build, False)
        if source_files(ROOT) != candidate['source_files']:
            raise RecipeError('candidate executable input closure changed during acceptance')
        result['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as error:
        result['failure'] = str(error) or 'independent acceptance interrupted'
    finally:
        result['cleanup'] = True
        for name in ('home', 'tmp'):
            try:
                if (root / name).exists():
                    shutil.rmtree(root / name)
            except OSError as error:
                result['cleanup'] = False
                result['status'] = 'FAIL'
                result['failure'] = result['failure'] or 'acceptance cleanup failed: ' + str(error)
        try:
            result['files'] = file_inventory(root, deadline if result['status'] == 'PASS' else None)
            if result['status'] == 'PASS':
                bind_comparison_inventory(result)
        except RecipeError as error:
            result['status'] = 'FAIL'
            result['failure'] = result['failure'] or str(error)
            result['files'] = file_inventory(root)
        result['elapsed_ns'] = time.monotonic_ns() - started
        if result['elapsed_ns'] > TIMEOUT_NS:
            result['status'] = 'FAIL'
            result['failure'] = result['failure'] or 'independent acceptance deadline expired'
        write(root / 'result.json', canonical(result))
    return result['status']


def replay_process(root, record, directory, executable_sha256, role, input_relative):
    record = exact_keys(record, ('command', 'terminal', 'exit_code', 'signal', 'elapsed_ns',
        'descendants_before', 'descendants_after', 'stdout', 'stderr'), 'acceptance process')
    process_ok(record)
    if type(record['elapsed_ns']) is not int or not 0 <= record['elapsed_ns'] <= TIMEOUT_NS \
            or type(record['descendants_before']) is not int or record['descendants_before'] < 0 \
            or type(record['descendants_after']) is not int:
        raise RecipeError('acceptance process measurements are invalid')
    expected = ['<' + role + '>:sha256:' + executable_sha256,
                '<case-input>:sha256:' + digest(root / input_relative)]
    if record['command']['argv'] != expected:
        raise RecipeError('acceptance process executable or input binding differs')
    for name in ('stdout', 'stderr'):
        row = exact_keys(record[name], ('role', 'path', 'bytes', 'sha256', 'original_bytes',
                                      'original_sha256', 'truncated'), 'acceptance log')
        path = directory + '/' + name
        raw = (root / path).read_bytes()
        expected = {'role': name, 'path': path, 'bytes': len(raw),
                    'sha256': hashlib.sha256(raw).hexdigest(), 'original_bytes': len(raw),
                    'original_sha256': hashlib.sha256(raw).hexdigest(), 'truncated': False}
        if canonical(row) != canonical(expected):
            raise RecipeError('acceptance process log binding differs')


def replay(root):
    """Recompute a complete PASS using only retained artifacts, never recorded physical paths."""
    root = root.resolve(strict=True)
    result = exact_keys(json_file(root / 'result.json'), ('schema_version', 'artifact_kind', 'status',
        'origin_root', 'input_root', 'source_commit', 'corpus_sha256', 'profile_sha256',
        'references', 'cases', 'elapsed_ns', 'failure', 'cleanup', 'files'), 'acceptance result')
    if type(result['schema_version']) is not int or result['schema_version'] != 1 \
            or result['artifact_kind'] != 'GPU_INDEPENDENT_ACCEPTANCE_RESULT' \
            or result['status'] != 'PASS' or result['failure'] != '' or result['cleanup'] is not True \
            or type(result['elapsed_ns']) is not int or not 0 < result['elapsed_ns'] <= TIMEOUT_NS:
        raise RecipeError('acceptance result is not a completed bounded PASS')
    inventory = file_inventory(root)
    if canonical(result['files']) != canonical(inventory):
        raise RecipeError('acceptance retained inventory differs')
    bind_comparison_inventory(result)
    for name in ('origin_root', 'input_root'):
        value = result[name]
        if not isinstance(value, str) or not pathlib.Path(value).is_absolute() or str(pathlib.Path(value)) != value:
            raise RecipeError('acceptance provenance root is invalid')
    if digest(root / 'corpus.json') != result['corpus_sha256'] \
            or digest(root / 'profile.json') != result['profile_sha256']:
        raise RecipeError('acceptance frozen input identity differs')
    records = validate_profile_records(runtime_option_raw=(root / 'admission/runtime-option.json').read_bytes(),
        align_source_raw=(root / 'admission/align-source.json').read_bytes(),
        ggml_source_raw=(root / 'admission/ggml-source.json').read_bytes(),
        bundle_raw=(root / 'bundle.json').read_bytes(),
        calibration_raws=[(root / 'admission' / f'calibration-{i}.json').read_bytes() for i in range(2)],
        profile_raw=(root / 'profile.json').read_bytes())
    profile, bundle = records['profile'], records['bundle']
    corpus = validate_corpus(json_file(root / 'corpus.json', CORPUS_LIMIT),
                             bundle_id=bundle['bundle_id'], models=profile['models'])
    candidate = verify_build(root / 'candidate', True)
    reference = verify_build(root / 'reference', False)
    if corpus['backend'] != bundle['backend'] or candidate['bundle_id'] != bundle['bundle_id'] \
            or reference['ggml_commit'] != bundle['ggml']['commit'] \
            or candidate['source_commit'] != result['source_commit']:
        raise RecipeError('acceptance source/backend identities differ')
    for relative, expected in candidate['source_files'].items():
        retained_path(relative, 'candidate source')
        if digest(root / 'source' / relative) != expected:
            raise RecipeError('acceptance candidate source closure differs')
    if digest(root / 'source/eval/gpu/reference-acquire.cpp') != reference['driver_sha256'] \
            or (root / 'source/.align-revision').read_text().strip() != candidate['align_revision']:
        raise RecipeError('acceptance compiler/reference source binding differs')
    origin = pathlib.Path(result['origin_root'])
    options = dict(profile['runtime_options'][0])
    options.pop('option_id')
    options['backend_bundle'] = str(origin / 'backend')
    if (root / 'runtime-options.json').read_bytes() != canonical(options):
        raise RecipeError('acceptance runtime options differ from admission')
    for artifact in bundle['artifacts']:
        if digest(root / 'backend' / artifact['path']) != artifact['sha256']:
            raise RecipeError('acceptance staged backend differs')
    ordered = list(expected_cases(corpus))
    if not isinstance(result['references'], list) or len(result['references']) != len(ordered) \
            or not isinstance(result['cases'], list) or len(result['cases']) != len(ordered) * 2:
        raise RecipeError('acceptance case coverage is incomplete')
    allowed = {'corpus.json', 'profile.json', 'bundle.json', 'runtime-options.json', 'backend/manifest.json',
        'admission/runtime-option.json', 'admission/align-source.json', 'admission/ggml-source.json',
        'admission/calibration-0.json', 'admission/calibration-1.json', 'candidate/build.json', 'reference/build.json',
        'reference/reference-acquire'}
    allowed.update('source/' + name for name in candidate['source_files'])
    allowed.update('candidate/' + name for name in candidate['executables'])
    allowed.update('candidate/lib/' + name for name in candidate['libraries'])
    allowed.update('reference/lib/' + name for name in reference['libraries'])
    allowed.update('backend/' + artifact['path'] for artifact in bundle['artifacts'])
    allowed.update('geometry/' + model['model_id'] + '.json' for model in profile['models'])
    if (root / 'backend/manifest.json').read_bytes() != (root / 'bundle.json').read_bytes():
        raise RecipeError('acceptance staged backend manifest differs')
    compare = comparator()
    for ordinal, (model_id, case) in enumerate(ordered):
        model = next(m for m in profile['models'] if m['model_id'] == model_id)
        geometry_path = root / 'geometry' / (model_id + '.json')
        if digest(geometry_path) != model['geometry_sha256']:
            raise RecipeError('acceptance geometry differs from admitted model')
        geometry = json_file(geometry_path, framed=False)
        base = 'cases/' + str(ordinal)
        ref = exact_keys(result['references'][ordinal], ('model_id', 'case_id', 'directory', 'input', 'process'),
                         'acceptance reference row')
        expected_ref = {'model_id': model_id, 'case_id': case['case_id'], 'directory': base + '/reference',
                        'input': base + '/reference-input.json', 'process': ref['process']}
        if ref != expected_ref:
            raise RecipeError('acceptance reference order or paths differ')
        plugin = next(a['path'] for a in bundle['artifacts'] if a['role'] == 'backend_plugin')
        request = {'model_path': str(pathlib.Path(result['input_root']) / model['model_path']),
                   'plugin_path': str(origin / 'backend' / plugin), 'prompt_token_ids': case['prompt_token_ids'],
                   'maximum_tokens': case['maximum_tokens'],
                   'seed': case['seed'] if case['sampler_mode'] == 'seeded' else None,
                   'output_root': str(origin / ref['directory'])}
        if corpus['schema_version'] == 2:
            request['attention_policy'] = attention_policy(corpus, model_id)
        if (root / ref['input']).read_bytes() != canonical(request):
            raise RecipeError('acceptance reference input differs from frozen case')
        replay_process(root, ref['process'], base + '/reference-process', reference['executable_sha256'],
                       'independent-reference', ref['input'])
        for repeat in (0, 1):
            row = exact_keys(result['cases'][ordinal * 2 + repeat], ('model_id', 'case_id', 'repeat',
                'directory', 'input', 'numeric', 'executable', 'process', 'comparison'), 'acceptance candidate row')
            relative = base + '/repeat-' + str(repeat)
            name = 'runtime_immediate_eog_smoke' if case['input_mode'] == 'continuation' else 'runtime_case'
            expected = {'model_id': model_id, 'case_id': case['case_id'], 'repeat': repeat,
                'directory': relative, 'input': relative + '/input.json', 'numeric': base + '/repeat-0/numeric',
                'executable': name, 'process': row['process'], 'comparison': row['comparison']}
            if canonical(row) != canonical(expected):
                raise RecipeError('acceptance candidate order or paths differ')
            plan = plan_for(profile, model, geometry, case, origin, result['input_root'],
                            origin / 'runtime-options.json', relative)
            plan = dataclasses.replace(plan, attention_policy=attention_policy(corpus, model_id))
            if (root / row['input']).read_bytes() != plan.input_bytes():
                raise RecipeError('acceptance candidate input differs from frozen case')
            replay_process(root, row['process'], relative, candidate['executables'][name], 'candidate', row['input'])
            numeric = root / row['numeric']
            relocated = dataclasses.replace(plan, document=dict(plan.document,
                stream_root=str(numeric.parent), stream_name=numeric.name))
            native = validate_native((root / relative / 'stdout').read_bytes(), relocated,
                                     bundle['bundle_id'], options['device'], options, None)
            if repeat == 0:
                comparison = compare.compare(root / ref['directory'], numeric, geometry, case)
            allowed.update((row['input'], row['numeric'], relative + '/stdout', relative + '/stderr'))
            allowed.update((ref['input'], base + '/reference-process/stdout', base + '/reference-process/stderr',
                            ref['directory'] + '/index.jsonl', ref['directory'] + '/production.json'))
            allowed.update(ref['directory'] + '/' + name for name in comparison['reference_tensors'])
            if not comparison['bitwise_equal'] or canonical(comparison) != canonical(row['comparison']):
                raise RecipeError('acceptance replay numerical comparison differs')
        print(model_id, case['case_id'], 'replay PASS', flush=True)
    if {row['path'] for row in inventory} != allowed:
        raise RecipeError('acceptance inventory contains artifacts outside its complete closure')
    allowed_directories = {parent.as_posix() for name in allowed for parent in pathlib.PurePosixPath(name).parents
                           if parent.as_posix() != '.'}
    if {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_dir()} != allowed_directories:
        raise RecipeError('acceptance directory cleanup or closure differs')
    if canonical(file_inventory(root)) != canonical(inventory):
        raise RecipeError('acceptance artifacts changed during replay')
    return 'PASS'
