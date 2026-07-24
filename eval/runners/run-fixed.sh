#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
corpus="${1:-${project_root}/eval/tasks/smoke-v1.json}"
binary="${ALIGN_LLM_BIN:-${project_root}/main}"
corpus_name="$(basename "${corpus}" .json)"
expected="${project_root}/eval/expected/${corpus_name}-summary.json"
output_file="$(mktemp)"
summary_file="$(mktemp)"
task_ids_file="$(mktemp)"
expected_task_ids="${project_root}/eval/expected/${corpus_name}-task-ids.txt"
trap 'rm -f "${output_file}" "${summary_file}" "${task_ids_file}"' EXIT

if [[ ! -x "${binary}" ]]; then
  make -C "${project_root}" build
fi

cd "${project_root}"
"${binary}" --eval "${corpus}" | tee "${output_file}"
tail -n 1 "${output_file}" > "${summary_file}"
sed -n 's/.*"task_id":"\([^"]*\)".*/\1/p' "${output_file}" > "${task_ids_file}"

if grep -Eq '"verdict":"(FAIL|TIMEOUT|ERROR)"' "${output_file}"; then
  printf '%s\n' "fixed evaluation contains a non-passing task" >&2
  exit 1
fi

if ! cmp -s "${expected_task_ids}" "${task_ids_file}"; then
  printf '%s\n' "fixed evaluation task order differs from ${expected_task_ids}" >&2
  diff -u "${expected_task_ids}" "${task_ids_file}" >&2 || true
  exit 1
fi

if ! cmp -s "${expected}" "${summary_file}"; then
  printf '%s\n' "fixed evaluation summary differs from ${expected}" >&2
  diff -u "${expected}" "${summary_file}" >&2 || true
  exit 1
fi
