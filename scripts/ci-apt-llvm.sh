#!/usr/bin/env bash
# Install the hosted LLVM 22 toolchain and native libraries from a cached .deb set.
#
# `key` identifies the runner image and normalized request. `install` replays a
# checksum-verified restored set with dpkg, or performs the same signed apt
# install used on a miss. `verify` rechecks the retained candidate immediately
# before publication. `install --uncached` retains the full path without
# leaving archives for a cache consumer.
#
# Only ALIGN_APT_PACKAGES and their dependency closure are installed. The
# authoritative apt transaction uses --no-remove: a transaction that removes a
# runner package cannot be replayed later by `dpkg --install` and must never be
# saved. The package list includes lld-22 because Align can select it for ELF
# links; lldb and clangd have no align-llm hosted-check consumer and are omitted.
#
# The key identifies the request, not apt.llvm.org's moving resolved bytes. One
# trusted main miss pins a signed snapshot for the current runner ImageVersion;
# the workflow logs llvm-22-dev's exact version. Bump CACHE_GENERATION to escape
# a bad entry.
#
# SHA256SUMS detects truncation and corruption, not a hostile cache writer.
# Trust in restored archives rests on GitHub Actions cache scope isolation:
# pull requests may read the default-branch entry but never publish it. Revisit
# this boundary before adding pull_request_target or an untrusted reusable
# workflow caller.
set -euo pipefail

readonly LLVM_VERSION=22
readonly APT_CONF=/etc/apt/apt.conf.d/99-align-archives
readonly LLVM_KEYRING=/etc/apt/keyrings/apt-llvm-org.asc
readonly LLVM_SOURCES=/etc/apt/sources.list.d/align-apt-llvm-org.list
readonly LLVM_KEY_URL=https://apt.llvm.org/llvm-snapshot.gpg.key
# "Sylvestre Ledru - Debian LLVM packages", the apt.llvm.org archive signing
# key. Pinned because this script adds the repository itself: fetching a key
# over TLS and trusting whatever arrives is the weakest link in the chain.
readonly LLVM_KEY_FINGERPRINT=6084F3CF814B57C1CF12EFD515CF4D18AF4F7421
# Manual escape hatch: bump to invalidate every entry (see the header).
# g2 adopts the replayable no-removal archive contract from sibling Align.
readonly CACHE_GENERATION=g2

usage() {
  echo "usage: scripts/ci-apt-llvm.sh {key | install [--uncached] | verify}" >&2
  echo "  key                 print the cache path and key for actions/cache" >&2
  echo "  install             install the restored archive set, or resolve it" >&2
  echo "                      through apt and leave the archives for the cache" >&2
  echo "  install --uncached  resolve through apt for a caller with no cache" >&2
  echo "  verify              verify the retained candidate without changing it" >&2
  echo "  ALIGN_APT_PACKAGES must list the packages to install." >&2
}

apt_conf_written=0
workdir=""
llvm_repository_ready=0
llvm_keyring_written=0
llvm_sources_written=0
llvm_keyring_directory_written=0
cache_candidate=0

cleanup() {
  local original_status=$? cleanup_status=0
  if [[ "$apt_conf_written" -eq 1 ]]; then
    sudo rm -f "$APT_CONF" || cleanup_status=1
  fi
  if [[ "$llvm_sources_written" -eq 1 ]]; then
    sudo rm -f "$LLVM_SOURCES" || cleanup_status=1
  fi
  if [[ "$llvm_keyring_written" -eq 1 ]]; then
    sudo rm -f "$LLVM_KEYRING" || cleanup_status=1
  fi
  if [[ "$llvm_keyring_directory_written" -eq 1 ]]; then
    sudo rmdir /etc/apt/keyrings || cleanup_status=1
  fi
  if [[ -n "$workdir" ]]; then
    rm -rf "$workdir" || cleanup_status=1
  fi
  # Archive retention is the commit point. A candidate is saveable only when
  # the command and every other owned-path cleanup completed successfully.
  if [[ -n "${archives:-}" ]] \
    && { [[ "$original_status" -ne 0 ]] || [[ "$cleanup_status" -ne 0 ]] \
      || [[ "$cache_candidate" -ne 1 ]]; }
  then
    sudo rm -rf "$archives" || cleanup_status=1
  fi
  [[ "$original_status" -ne 0 ]] && return "$original_status"
  return "$cleanup_status"
}

path_exists() {
  [[ -e "$1" || -L "$1" ]]
}

# Claim the fixed process-global namespace before dpkg, apt, repository
# network, or fixed-path mutation. A later retry may reuse only state whose
# ownership flags were set by this invocation.
validate_install_state() {
  if path_exists "$APT_CONF"; then
    echo "refusing pre-existing apt archive configuration $APT_CONF" >&2
    return 1
  fi
  if path_exists "$LLVM_SOURCES" || path_exists "$LLVM_KEYRING"; then
    echo "refusing pre-existing apt.llvm.org repository state" >&2
    return 1
  fi
  if [[ -L /etc/apt/keyrings || ( -e /etc/apt/keyrings && ! -d /etc/apt/keyrings ) ]]; then
    echo "refusing non-directory apt keyring state" >&2
    return 1
  fi
}

parse_packages() {
  local raw="${ALIGN_APT_PACKAGES:-}" token
  local index previous
  package_args=()
  if [[ "$raw" == *$'\n'* || "$raw" == *$'\r'* ]]; then
    echo "ALIGN_APT_PACKAGES must be one line" >&2
    return 2
  fi
  read -r -a package_args <<< "$raw" || true
  if [[ ${#package_args[@]} -eq 0 ]]; then
    echo "ALIGN_APT_PACKAGES contains no package names" >&2
    return 2
  fi
  for ((index = 0; index < ${#package_args[@]}; index++)); do
    token="${package_args[$index]}"
    # Debian binary package names are at least two characters, start with a
    # lowercase letter or digit, and otherwise contain lowercase alphanumerics,
    # plus, minus, and dot. Deliberately exclude apt options, globs, versions,
    # architecture qualifiers, and other request syntax from this CI surface.
    if [[ ! "$token" =~ ^[a-z0-9][a-z0-9+.-]+$ ]]; then
      echo "ALIGN_APT_PACKAGES item $((index + 1)) is not a binary package name" >&2
      return 2
    fi
    for ((previous = 0; previous < index; previous++)); do
      if [[ "$token" == "${package_args[$previous]}" ]]; then
        echo "ALIGN_APT_PACKAGES contains a duplicate package name" >&2
        return 2
      fi
    done
  done
  packages="${package_args[*]}"
}

# Sorted so that reordering the caller's list does not churn the cache entry.
cache_key() {
  local normalized digest
  normalized="$(printf '%s\n' "${package_args[@]}" | LC_ALL=C sort | tr '\n' ' ')"
  digest="$(printf '%s' "$normalized" | sha256sum | cut -c1-16)"
  # ImageVersion is the dependency baseline the archive set was resolved
  # against. Fail closed rather than key every image to one bucket.
  printf 'apt-llvm%s-%s-%s-%s-image%s-%s\n' \
    "$LLVM_VERSION" "${RUNNER_OS:-Linux}" "${RUNNER_ARCH:-X64}" "$CACHE_GENERATION" \
    "${ImageVersion:?ImageVersion must be set; it pins the dependency baseline}" \
    "$digest"
}

# Every requested package configured, and the two things the build actually
# resolves through — llvm-config and the C driver alignc links with — present.
# A restored set that fails this is discarded. `cc` is checked because no
# requested package names it: it comes from the runner image, and a repair that
# was allowed to remove packages could take it away without any dpkg-query in
# the loop above noticing.
toolchain_complete() {
  local package status
  for package in "${package_args[@]}"; do
    status="$(dpkg-query --show --showformat='${db:Status-Status}' "$package" 2>/dev/null || true)"
    [[ "$status" == "installed" ]] || return 1
  done
  [[ -x "/usr/lib/llvm-${LLVM_VERSION}/bin/llvm-config" ]] || return 1
  command -v cc >/dev/null 2>&1
}

# Truncation and corruption check over the restored set. See the header for
# what this does not defend against.
verify_archives() {
  local expected="$1" actual_names manifest_names listed path
  local archive_files=()
  if [[ ! -d "$archives" || -L "$archives" ]]; then
    echo "the restored package archive path is not a real directory" >&2
    return 1
  fi
  if [[ ! -f "$archives/SHA256SUMS" || -L "$archives/SHA256SUMS" ]]; then
    echo "the restored package set has no SHA256SUMS manifest" >&2
    return 1
  fi
  shopt -s nullglob
  archive_files=("$archives"/*.deb)
  shopt -u nullglob
  [[ ${#archive_files[@]} -eq "$expected" ]] || return 1
  actual_names=""
  for path in "${archive_files[@]}"; do
    if [[ ! -f "$path" || -L "$path" ]]; then
      echo "the restored package set contains a non-regular archive: ${path##*/}" >&2
      return 1
    fi
    actual_names+="${path##*/}"$'\n'
  done
  actual_names="$(printf '%s' "$actual_names" | LC_ALL=C sort)"
  if ! manifest_names="$(awk '
      NF == 2 && length($1) == 64 && $1 !~ /[^0-9a-f]/ \
        && $2 ~ /^\*?\.\/[^/]+\.deb$/ {
          name = $2
          sub(/^\*/, "", name)
          sub(/^\.\//, "", name)
          print name
          next
        }
      { exit 1 }
    ' "$archives/SHA256SUMS" | LC_ALL=C sort)"
  then
    echo "the restored package manifest has a malformed archive row" >&2
    return 1
  fi
  listed="$(printf '%s\n' "$manifest_names" | awk 'NF { count++ } END { print count + 0 }')"
  if [[ "$listed" != "$expected" || "$manifest_names" != "$actual_names" ]]; then
    echo "the restored package manifest does not exactly name all $expected archives" >&2
    return 1
  fi
  ( cd "$archives" && LC_ALL=C sha256sum --check --quiet --strict SHA256SUMS )
}

# Print the llvm-N-dev candidate version, but only when apt would fetch that
# exact version from apt.llvm.org. A bare `Candidate:` is not evidence the
# repository works: an llvm-22-dev already unpacked by a restored set answers it
# out of /var/lib/dpkg/status, which would let a failed repository add look like
# a success and skip the suite fallback. Walks the version table, finds the row
# whose version is the candidate, and requires one of that row's origin lines to
# name apt.llvm.org. Prints nothing when it does not.
llvm_org_candidate() {
  apt-cache policy "llvm-${LLVM_VERSION}-dev" 2>/dev/null | awk '
    /^ *Candidate: / { candidate = $2; next }
    /^ *Version table:/ { in_table = 1; next }
    !in_table { next }
    {
      # A version row is "<version> <priority>", or "*** <version> <priority>"
      # for the installed one. An origin row is "<priority> <uri-or-path> ...",
      # whose second field is never a bare number.
      version = ""
      if ($1 == "***") { version = $2 }
      else if ($2 ~ /^[0-9]+$/) { version = $1 }
      if (version != "") { current = (version == candidate); next }
      if (current && index($0, "apt.llvm.org") > 0) { print candidate; exit }
    }'
}

# The minimum llvm.sh did that this script actually needs: the signing key and
# one sources.list entry. Retryable within one invocation, because the recovery
# path adds the repository before the authoritative install also asks for it.
add_llvm_repository() {
  [[ "$llvm_repository_ready" -eq 1 ]] && return 0

  local codename architecture tool primary_fingerprints suite candidate
  # Every capture below tolerates its own failure so the explicit check, not
  # `set -e`/`pipefail` on the assignment, reports what actually went wrong.
  codename="$(. /etc/os-release 2>/dev/null && printf '%s' "${VERSION_CODENAME:-}")" \
    || codename=""
  if [[ -z "$codename" ]]; then
    echo "/etc/os-release declares no VERSION_CODENAME; cannot pick an apt.llvm.org suite" >&2
    return 1
  fi
  architecture="$(dpkg --print-architecture)" || return 1
  for tool in gpg wget; do
    command -v "$tool" >/dev/null 2>&1 || {
      echo "$tool is required to add the apt.llvm.org repository" >&2
      return 1
    }
  done

  [[ -n "$workdir" ]] || workdir="$(mktemp -d)" || return 1
  wget -q "$LLVM_KEY_URL" -O "$workdir/llvm-snapshot.asc" || {
    echo "cannot download the apt.llvm.org signing key from $LLVM_KEY_URL" >&2
    return 1
  }
  # Trust exactly one primary key. Subkeys bound by that primary key remain in
  # the installed block, but a TLS response cannot smuggle in another primary
  # key and have apt accept signatures from it merely by including the pinned
  # public key alongside it.
  primary_fingerprints="$(gpg --show-keys --with-colons "$workdir/llvm-snapshot.asc" 2>/dev/null \
    | awk -F: '
        $1 == "pub" { want_primary_fingerprint = 1; next }
        want_primary_fingerprint && $1 == "fpr" {
          print $10
          want_primary_fingerprint = 0
        }')" || primary_fingerprints=""
  if [[ "$primary_fingerprints" != "$LLVM_KEY_FINGERPRINT" ]]; then
    echo "apt.llvm.org signing key block is not exactly primary $LLVM_KEY_FINGERPRINT" >&2
    echo "  primary fingerprints offered: ${primary_fingerprints:-none}" >&2
    return 1
  fi
  if { path_exists "$LLVM_KEYRING" && [[ "$llvm_keyring_written" -ne 1 ]]; } \
    || { path_exists "$LLVM_SOURCES" && [[ "$llvm_sources_written" -ne 1 ]]; }
  then
    echo "refusing pre-existing apt.llvm.org repository state" >&2
    return 1
  fi
  if [[ -L /etc/apt/keyrings || ( -e /etc/apt/keyrings && ! -d /etc/apt/keyrings ) ]]; then
    echo "refusing non-directory apt keyring state" >&2
    return 1
  fi
  if [[ ! -d /etc/apt/keyrings ]]; then
    llvm_keyring_directory_written=1
    sudo install -d -m 0755 /etc/apt/keyrings || return 1
  fi
  llvm_keyring_written=1
  sudo install -m 0644 "$workdir/llvm-snapshot.asc" "$LLVM_KEYRING" || return 1

  # apt.llvm.org names a released branch <codename>-<major> and the
  # in-development branch plain <codename>. Try the versioned suite first and
  # fall back, so the major moving to trunk cannot silently leave no candidate.
  for suite in "llvm-toolchain-${codename}-${LLVM_VERSION}" "llvm-toolchain-${codename}"; do
    llvm_sources_written=1
    printf 'deb [arch=%s signed-by=%s] https://apt.llvm.org/%s/ %s main\n' \
      "$architecture" "$LLVM_KEYRING" "$codename" "$suite" \
      | sudo tee "$LLVM_SOURCES" >/dev/null
    # A suite that does not exist 404s and fails the whole update; the
    # candidate probe below, not the exit status, decides whether it worked.
    sudo DEBIAN_FRONTEND=noninteractive apt-get update || true
    candidate="$(llvm_org_candidate)" || candidate=""
    if [[ -n "$candidate" ]]; then
      echo "apt.llvm.org $suite offers llvm-${LLVM_VERSION}-dev $candidate"
      llvm_repository_ready=1
      return 0
    fi
  done

  if sudo rm -f "$LLVM_SOURCES"; then
    llvm_sources_written=0
  fi
  echo "no llvm-${LLVM_VERSION}-dev candidate on apt.llvm.org for $codename/$architecture" >&2
  return 1
}

# Best-effort repair after a restored set failed to install. install_from_apt
# is what has to succeed, so nothing here may take the job down before it runs.
repair_dpkg_state() {
  sudo dpkg --configure --pending || true
  # Ordering is the whole point: apt cannot resolve an apt.llvm.org dependency
  # while it has no package list for apt.llvm.org, so the repository goes in
  # (with its own apt-get update) before the repair, not after.
  add_llvm_repository || true
  # --no-remove first, so a repair cannot solve a conflict by deleting a
  # library the build then fails to link. If that cannot converge, allow the
  # removal: one way a restored set breaks is dpkg being unable to remove a
  # conflicting package that apt would have, and refusing the removal outright
  # leaves no repair at all. That second stage is a general safety net rather
  # than a live path — retiring the g1 entries removed the only known set that
  # needed it, and the `--no-remove` on the authoritative install keeps a new
  # one from being saved. The authoritative install reinstates every requested
  # package and toolchain_complete, which now also checks `cc`, fails closed if
  # a removal took something the build needs.
  sudo DEBIAN_FRONTEND=noninteractive apt-get --fix-broken --no-remove --yes install \
    || sudo DEBIAN_FRONTEND=noninteractive apt-get --fix-broken --yes install \
    || true
}

# $1 is why this run is resolving through apt:
#   cache-miss  an entry will be saved from the result, so an empty resolve is
#               a defect and the manifest has to be written
#   repair      a restored set failed; most packages are already unpacked, so
#               downloading nothing is correct and no entry is saved
#   uncached    the caller keeps no cache at all; same as repair, and the
#               archives are discarded by install_packages afterwards
install_from_apt() {
  local purpose="$1"
  sudo rm -rf "$archives"
  sudo install -d -m 0755 "$archives"
  # apt drops privileges to _apt while fetching, so hand it a writable
  # partial/ directory instead of letting it fall back to an unsandboxed root
  # download.
  sudo install -d -m 0700 -o _apt -g root "$archives/partial"
  if path_exists "$APT_CONF"; then
    echo "refusing pre-existing apt archive configuration $APT_CONF" >&2
    exit 1
  fi
  apt_conf_written=1
  printf 'Dir::Cache::archives "%s";\n' "$archives" | sudo tee "$APT_CONF" >/dev/null

  add_llvm_repository || {
    echo "cannot add the apt.llvm.org repository for LLVM $LLVM_VERSION" >&2
    exit 1
  }
  # --no-remove turns "this request is dpkg-replayable" from a claim into a
  # gate. An apt transaction that removes a package cannot be replayed by
  # `dpkg --install` on a later hit, which is exactly how the g1 entries broke;
  # failing here means main never saves such an entry in the first place. It is
  # unconditional so every cache miss proves the entry is replayable before it
  # can be published.
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-remove "${package_args[@]}"

  sudo rm -f "$APT_CONF"
  apt_conf_written=0
  sudo rm -rf "$archives/partial" "$archives/lock"
  sudo chown -R "$(id -u):$(id -g)" "$archives"

  local resolved=()
  shopt -s nullglob
  resolved=("$archives"/*.deb)
  shopt -u nullglob
  if [[ ${#resolved[@]} -eq 0 ]]; then
    if [[ "$purpose" == cache-miss ]]; then
      echo "apt resolved no archives into $archives, so the cache entry would be" >&2
      echo "empty and every later run would silently take the full install." >&2
      echo "If the runner image now ships the toolchain, drop the cache instead." >&2
      exit 1
    fi
    # No entry is saved from a repair or an uncached run, so downloading
    # nothing means the packages are already installed — the desired end state,
    # not a defect, and there is nothing to write a manifest over.
    echo "apt resolved no archives; every requested package was already installed"
    return 0
  fi
  if [[ "$purpose" == cache-miss ]]; then
    ( cd "$archives" \
      && sha256sum ./*.deb > SHA256SUMS.partial \
      && mv SHA256SUMS.partial SHA256SUMS )
    verify_archives "${#resolved[@]}" || {
      echo "apt produced an archive set that is not safe to cache" >&2
      exit 1
    }
    echo "resolved ${#resolved[@]} archives ($(du -sh "$archives" | cut -f1)) for the cache"
    cache_candidate=1
  else
    echo "resolved ${#resolved[@]} archives ($(du -sh "$archives" | cut -f1))"
  fi
}

install_packages() {
  local restored=()

  if [[ "$uncached" -eq 1 ]]; then
    install_from_apt uncached
    # Nothing will ever read these again.
    sudo rm -rf "$archives"
    toolchain_complete || {
      echo "LLVM ${LLVM_VERSION} and $packages are not fully installed" >&2
      exit 1
    }
    return 0
  fi

  if [[ -d "$archives" ]]; then
    shopt -s nullglob
    restored=("$archives"/*.deb)
    shopt -u nullglob
  fi

  if [[ ${#restored[@]} -gt 0 ]] \
    && verify_archives "${#restored[@]}" \
    && sudo DEBIAN_FRONTEND=noninteractive dpkg --install \
      --force-confold --force-confdef "${restored[@]}" \
    && toolchain_complete
  then
    echo "installed the cached LLVM ${LLVM_VERSION} package set (${#restored[@]} archives)"
  elif [[ ${#restored[@]} -gt 0 ]]; then
    echo "the cached package set is unusable; falling back to a full apt install" >&2
    repair_dpkg_state
    install_from_apt repair
  else
    install_from_apt cache-miss
  fi

  toolchain_complete || {
    echo "LLVM ${LLVM_VERSION} and $packages are not fully installed" >&2
    exit 1
  }
}

verify_candidate() {
  local candidate_archives=()
  shopt -s nullglob
  candidate_archives=("$archives"/*.deb)
  shopt -u nullglob
  if [[ ${#candidate_archives[@]} -eq 0 ]]; then
    echo "the apt cache candidate contains no archives" >&2
    return 1
  fi
  verify_archives "${#candidate_archives[@]}" || return 1
  toolchain_complete || {
    echo "LLVM ${LLVM_VERSION} and $packages are not fully installed" >&2
    return 1
  }
  echo "verified the apt cache candidate (${#candidate_archives[@]} archives)"
}

mode="${1:-}"
uncached=0
case "$mode" in
  key | verify)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    ;;
  install)
    case "${2:-}" in
      "") ;;
      --uncached) uncached=1 ;;
      *) usage; exit 2 ;;
    esac
    [[ $# -le 2 ]] || { usage; exit 2; }
    ;;
  *)
    usage
    exit 2
    ;;
esac

package_args=()
packages=""
parse_packages || { usage; exit 2; }
archives="${RUNNER_TEMP:?RUNNER_TEMP must be set}/apt-archives-llvm-${LLVM_VERSION}"

if [[ "$mode" == "key" ]]; then
  # Assign before printing: inside printf's argument a failed expansion would
  # be swallowed and emit an empty key, which caches the wrong thing forever.
  key="$(cache_key)"
  if [[ -z "$key" ]]; then
    echo "refusing to emit an empty cache key" >&2
    exit 1
  fi
  printf 'path=%s\n' "$archives"
  printf 'key=%s\n' "$key"
  exit 0
fi

if [[ "$mode" == "verify" ]]; then
  verify_candidate
  exit
fi

command -v apt-get >/dev/null 2>&1 || {
  echo "scripts/ci-apt-llvm.sh install targets the Debian-family CI runners" >&2
  exit 2
}
trap cleanup EXIT
validate_install_state
install_packages
