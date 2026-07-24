#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
corpus="${1:-${project_root}/eval/tasks/smoke-v1.json}"
binary="${ALIGN_LLM_BIN:-${project_root}/main}"
corpus_name="$(basename "${corpus}" .json)"
expected="${project_root}/eval/expected/${corpus_name}-summary.json"
output_file="$(mktemp)"
summary_file="$(mktemp)"
trap 'rm -f "${output_file}" "${summary_file}"' EXIT

if [[ ! -x "${binary}" ]]; then
  make -C "${project_root}" build
fi

cd "${project_root}"
"${binary}" --eval "${corpus}" | tee "${output_file}"
tail -n 1 "${output_file}" > "${summary_file}"

if grep -Eq '"verdict":"(FAIL|TIMEOUT|ERROR)"' "${output_file}"; then
  printf '%s\n' "fixed evaluation contains a non-passing task" >&2
  exit 1
fi

if ! cmp -s "${expected}" "${summary_file}"; then
  printf '%s\n' "fixed evaluation summary differs from ${expected}" >&2
  diff -u "${expected}" "${summary_file}" >&2 || true
  exit 1
fi
