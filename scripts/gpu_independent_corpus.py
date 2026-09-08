#!/usr/bin/env python3
"""Strict complete corpus admission for the independent GPU shipping oracle."""
from __future__ import annotations

import hashlib
from gpu_backend_recipe import GGML_COMMIT, RecipeError, canonical
from gpu_qualification_records import (bounded_i64, exact_keys, require_digest,
    require_enum, require_i32_array, self_hash, validate_frozen_cases)

MAX_BYTES = 4 * 1024**2


def coverage(model_id, cases, eog_ids):
    eog = set(eog_ids)
    provider = [row for row in cases if row['input_mode'] == 'provider']
    result = {
        'maximum_one': any(row['maximum_tokens'] == 1 for row in provider),
        'maximum_128': any(row['maximum_tokens'] == 128 and len(row['expected_token_ids']) == 128 for row in provider),
        'successive_decode': any(len(row['expected_token_ids']) >= 8 for row in provider),
        'tail_chunk': any(len(row['prompt_token_ids']) == 129 for row in provider),
        'multiple_chunks': any(len(row['prompt_token_ids']) == 257 for row in provider),
        'request_ceiling': any(len(row['prompt_token_ids']) == 2048 and row['maximum_tokens'] == 128
                               and len(row['expected_token_ids']) == 128 for row in provider),
        'ordinary_eog': any(row['expected_token_ids'][-1] in eog and 1 < len(row['expected_token_ids']) < row['maximum_tokens']
                            for row in provider),
        'immediate_eog': any(row['input_mode'] == 'continuation' and row['maximum_tokens'] == 128
                             and len(row['expected_token_ids']) == 1 and row['expected_token_ids'][0] in eog
                             and row['expected_output_utf8'] == '' for row in cases),
    }
    if model_id == 'olmoe':
        result['seeded'] = any(row['sampler_mode'] == 'seeded' and len(row['expected_token_ids']) >= 8 for row in provider)
    return result


def validate(value, *, bundle_id=None, models=None):
    result = exact_keys(value, ('schema_version', 'artifact_kind', 'corpus_id', 'backend',
                                'bundle_id', 'ggml_commit', 'models'), 'independent corpus')
    bounded_i64(result['schema_version'], 1, 2, 'independent corpus version')
    if result['artifact_kind'] != 'GPU_INDEPENDENT_ACCEPTANCE_CORPUS' or result['ggml_commit'] != GGML_COMMIT:
        raise RecipeError('independent corpus kind or ggml revision is invalid')
    require_enum(result['backend'], {'metal', 'cuda'}, 'independent corpus backend')
    require_digest(result['bundle_id'], 'independent corpus bundle')
    if bundle_id is not None and result['bundle_id'] != bundle_id:
        raise RecipeError('independent corpus bundle differs from admission')
    if len(canonical(result)) > MAX_BYTES:
        raise RecipeError('independent corpus exceeds its byte ceiling')
    entries = result['models']
    if not isinstance(entries, list) or len(entries) != 2:
        raise RecipeError('independent corpus requires exactly two models')
    all_ids = set()
    for ordinal, model_id in enumerate(('qwen2', 'olmoe')):
        fields = ('model', 'eog_token_ids', 'cases') + (('attention_policy',) if result['schema_version'] == 2 else ())
        entry = exact_keys(entries[ordinal], fields, 'independent corpus model')
        if result['schema_version'] == 2:
            require_enum(entry['attention_policy'], {'decomposed', 'flash_f32'}, 'independent attention policy')
        model = exact_keys(entry['model'], ('model_id', 'model_sha256', 'pack_sha256', 'geometry_sha256', 'quantization'),
                           'independent model identity')
        if model['model_id'] != model_id or model['quantization'] != 'Q4_K_M':
            raise RecipeError('independent model order or quantization differs')
        for key in ('model_sha256', 'pack_sha256', 'geometry_sha256'):
            require_digest(model[key], 'independent ' + key)
        if models is not None:
            admitted = next((m for m in models if m['model_id'] == model_id), None)
            if admitted is None or any(model[key] != admitted[key] for key in ('model_sha256', 'pack_sha256', 'geometry_sha256')):
                raise RecipeError('independent model differs from admitted inputs')
        eog = require_i32_array(entry['eog_token_ids'], 'independent EOG IDs', minimum=1, maximum=32)
        if sorted(set(eog)) != eog:
            raise RecipeError('independent EOG IDs are not sorted and unique')
        if not isinstance(entry['cases'], list):
            raise RecipeError('independent cases are not an array')
        frozen, modes = [], []
        for raw in entry['cases']:
            if not isinstance(raw, dict) or 'input_mode' not in raw:
                raise RecipeError('independent case has no input mode')
            modes.append(require_enum(raw['input_mode'], {'provider', 'continuation'}, 'independent input mode'))
            frozen.append({key: value for key, value in raw.items() if key != 'input_mode'})
        validated = validate_frozen_cases(frozen)
        for row, mode in zip(validated, modes):
            row['input_mode'] = mode
            if row['case_id'] in all_ids:
                raise RecipeError('independent case ID is duplicated across models')
            all_ids.add(row['case_id'])
            if not 1 <= len(row['prompt_token_ids']) <= 2048:
                raise RecipeError('independent prompt exceeds its token bound')
            if row['teacher_forced_token_ids'] != row['expected_token_ids']:
                raise RecipeError('independent teacher-forced tail differs from frozen samples')
            if model_id == 'qwen2' and row['sampler_mode'] != 'greedy':
                raise RecipeError('independent Qwen sampler is unsupported')
            terminal = row['expected_token_ids'][-1] in eog
            if any(token in eog for token in row['expected_token_ids'][:-1]) \
                    or (not terminal and len(row['expected_token_ids']) != row['maximum_tokens']):
                raise RecipeError('independent frozen stopping condition is invalid')
            if mode == 'continuation' and (row['maximum_tokens'] != 128 or len(row['expected_token_ids']) != 1
                    or not terminal or row['expected_output_utf8'] or row['sampler_mode'] != 'greedy'):
                raise RecipeError('independent continuation is not an immediate real EOG case')
        entry['cases'] = validated
        missing = [key for key, present in coverage(model_id, validated, eog).items() if not present]
        if missing:
            raise RecipeError('independent corpus lacks ' + model_id + ' coverage: ' + ', '.join(missing))
    self_hash(result, 'corpus_id', 'independent corpus')
    return result


def seal(value):
    result = dict(value, corpus_id='0' * 64)
    result['corpus_id'] = hashlib.sha256(canonical(result)).hexdigest()
    return result
