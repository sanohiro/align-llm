# syntax=docker/dockerfile:1.7
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG GIT_COMMIT=f94b90ad6e49cc7f15c4171c5a434aa459e82d2d
ARG BWRAP_COMMIT=1b80120ef26a28e065e67f89bfef873f13bdd317

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg xz-utils git make build-essential pkg-config \
      meson ninja-build libcap-dev libselinux1-dev libssl-dev zlib1g-dev libexpat1-dev \
      gettext perl python3.12 python3.12-dev python3-pip jq file && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y --no-install-recommends \
      lsb-release software-properties-common && \
    wget -q https://apt.llvm.org/llvm.sh -O /tmp/llvm.sh && \
    chmod 0755 /tmp/llvm.sh && /tmp/llvm.sh 22 && \
    apt-get update && apt-get install -y --no-install-recommends \
      llvm-22-dev clang-22 lld-22 libclang-rt-22-dev libc++-22-dev libc++abi-22-dev && \
    rm -rf /var/lib/apt/lists/* /tmp/llvm.sh

RUN git clone --filter=blob:none https://github.com/git/git.git /tmp/git && \
    git -C /tmp/git checkout --detach "$GIT_COMMIT" && \
    test "$(git -C /tmp/git rev-parse HEAD)" = "$GIT_COMMIT" && \
    make -C /tmp/git -j2 prefix=/runtime/git NO_TCLTK=YesPlease NO_GETTEXT=YesPlease \
      NO_CURL=YesPlease all && \
    make -C /tmp/git prefix=/runtime/git NO_TCLTK=YesPlease NO_GETTEXT=YesPlease \
      NO_CURL=YesPlease install && \
    rm -rf /tmp/git

RUN git clone --filter=blob:none https://github.com/containers/bubblewrap.git /tmp/bubblewrap && \
    git -C /tmp/bubblewrap checkout --detach "$BWRAP_COMMIT" && \
    test "$(git -C /tmp/bubblewrap rev-parse HEAD)" = "$BWRAP_COMMIT" && \
    meson setup /tmp/bubblewrap/build /tmp/bubblewrap --prefix=/runtime/bwrap \
      -Dtests=false -Dselinux=disabled && \
    meson compile -C /tmp/bubblewrap/build && meson install -C /tmp/bubblewrap/build && \
    rm -rf /tmp/bubblewrap

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
      sh -s -- -y --profile minimal --default-toolchain 1.96.0 && \
    cp -aL /root/.rustup/toolchains/1.96.0-x86_64-unknown-linux-gnu /runtime/rust && \
    /runtime/rust/bin/rustc --version | grep -F 'rustc 1.96.0 ' && \
    /runtime/rust/bin/cargo --version | grep -F 'cargo 1.96.0 '

COPY scripts/materialize-fresh-tree /usr/local/libexec/align-llm/materialize-fresh-tree

RUN for tree in git rust bwrap; do \
      python3 /usr/local/libexec/align-llm/materialize-fresh-tree \
        "/runtime/$tree" "/runtime/$tree.materialized"; \
      rm -rf "/runtime/$tree"; \
      mv "/runtime/$tree.materialized" "/runtime/$tree"; \
    done && \
    test -z "$(find /runtime/git /runtime/rust /runtime/bwrap -type l -print -quit)"

RUN python3 /usr/local/libexec/align-llm/materialize-fresh-tree \
      /usr/lib/llvm-22 /runtime/cc-suite && \
    mkdir -p /runtime/system && \
    cp -aL /usr/lib/x86_64-linux-gnu /runtime/system/usr-lib-x86_64 && \
    cp -aL /usr/lib/x86_64-linux-gnu /runtime/system/lib-x86_64 && \
    cp -aL /usr/lib/python3.12 /runtime/system/python3.12 && \
    cp -aL /usr/include /runtime/system/include && \
    cp -aL /usr/share/git-core /runtime/system/git-core && \
    if [ -d /usr/share/perl5 ]; then cp -aL /usr/share/perl5 /runtime/system/perl5; else mkdir /runtime/system/perl5; fi && \
    cp -L /lib64/ld-linux-x86-64.so.2 /runtime/system/ld-linux-x86-64.so.2

COPY scripts/build-fresh-image-control scripts/fresh_attestation.py scripts/fresh_manifest.py \
     scripts/generate-fresh-toolchain-manifest /build/align-llm/scripts/
COPY image/fresh /build/align-llm/image/fresh

RUN mkdir -p /usr/local/libexec/align-llm /usr/local/share/align-llm \
      /opt/align-llm/tool-bin /var/cache/align-llm/cargo && \
    python3 /build/align-llm/scripts/build-fresh-image-control \
      --cc /usr/lib/llvm-22/bin/clang --output-dir /usr/local/libexec/align-llm && \
    /usr/lib/llvm-22/bin/clang -std=c11 -O2 -Wall -Wextra -Werror -fPIE -pie \
      -Wl,-z,relro,-z,now -Wl,--build-id=none \
      -o /opt/align-llm/tool-bin/mount-guard /build/align-llm/image/fresh/mount-guard.c && \
    install -m 0755 /build/align-llm/image/fresh/fresh-profile \
      /usr/local/libexec/align-llm/fresh-profile

RUN python3 - <<'PY'
import os
import shutil
import subprocess
from pathlib import Path

root = Path("/opt/align-llm/tool-bin")
source = Path("/build/align-llm/image/fresh/tool-forwarder.c")
cc = "/usr/lib/llvm-22/bin/clang"
forwarders = {
    "git": "/runtime/git/bin/git",
    "cargo": "/runtime/rust/bin/cargo",
    "rustc": "/runtime/rust/bin/rustc",
    "llvm-config": "/runtime/cc-suite/bin/llvm-config",
    "llvm-config-22": "/runtime/cc-suite/bin/llvm-config",
    "cc": "/runtime/cc-suite/bin/clang",
    "cxx": "/runtime/cc-suite/bin/clang++",
    "ar": "/runtime/cc-suite/bin/llvm-ar",
    "ranlib": "/runtime/cc-suite/bin/llvm-ranlib",
    "linker": "/runtime/cc-suite/bin/ld.lld",
    "bwrap": "/runtime/bwrap/bin/bwrap",
    "clang": "/runtime/cc-suite/bin/clang",
    "clang++": "/runtime/cc-suite/bin/clang++",
    "strip": "/runtime/cc-suite/bin/llvm-strip",
    "objdump": "/runtime/cc-suite/bin/llvm-objdump",
    "objcopy": "/runtime/cc-suite/bin/llvm-objcopy",
    "llvm-profdata": "/runtime/cc-suite/bin/llvm-profdata",
    "llvm-profdata-22": "/runtime/cc-suite/bin/llvm-profdata",
    "llvm-bcanalyzer": "/runtime/cc-suite/bin/llvm-bcanalyzer",
    "llvm-bcanalyzer-22": "/runtime/cc-suite/bin/llvm-bcanalyzer",
    "llvm-readobj": "/runtime/cc-suite/bin/llvm-readobj",
    "llvm-nm": "/runtime/cc-suite/bin/llvm-nm",
    "ld": "/runtime/cc-suite/bin/ld.lld",
    "ld.lld": "/runtime/cc-suite/bin/ld.lld",
}
system = {
    "sh": "/usr/bin/dash", "make": "/usr/bin/make", "python3": "/usr/bin/python3.12",
    "env": "/usr/bin/env", "bash": "/usr/bin/bash", "prlimit": "/usr/bin/prlimit",
    "id": "/usr/bin/id", "basename": "/usr/bin/basename", "cat": "/usr/bin/cat",
    "chmod": "/usr/bin/chmod", "cmp": "/usr/bin/cmp", "cp": "/usr/bin/cp",
    "diff": "/usr/bin/diff", "dirname": "/usr/bin/dirname", "find": "/usr/bin/find",
    "grep": "/usr/bin/grep", "head": "/usr/bin/head", "mkdir": "/usr/bin/mkdir",
    "mktemp": "/usr/bin/mktemp", "mv": "/usr/bin/mv", "readlink": "/usr/bin/readlink",
    "realpath": "/usr/bin/realpath", "rm": "/usr/bin/rm", "rmdir": "/usr/bin/rmdir",
    "sed": "/usr/bin/sed", "seq": "/usr/bin/seq", "sleep": "/usr/bin/sleep",
    "stat": "/usr/bin/stat", "tail": "/usr/bin/tail", "tee": "/usr/bin/tee",
    "touch": "/usr/bin/touch", "tr": "/usr/bin/tr", "wc": "/usr/bin/wc",
}
for name, target in forwarders.items():
    subprocess.run([
        cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-fPIE", "-pie",
        "-Wl,-z,relro,-z,now", "-Wl,--build-id=none", f'-DTOOL_TARGET="{target}"',
        "-o", str(root / name), str(source),
    ], check=True)
for name, path in system.items():
    shutil.copyfile(Path(path).resolve(strict=True), root / name)
for path in root.iterdir():
    path.chmod(0o755)
PY

RUN python3 /build/align-llm/scripts/generate-fresh-toolchain-manifest \
      --bootstrap /usr/local/libexec/align-llm/fresh-bootstrap \
      --tool-root /opt/align-llm/tool-bin \
      --runtime /runtime/git=/runtime/git \
      --runtime /runtime/rust=/runtime/rust \
      --runtime /runtime/cc-suite=/runtime/cc-suite \
      --runtime /runtime/bwrap=/runtime/bwrap \
      --runtime /runtime/system/usr-lib-x86_64=/usr/lib/x86_64-linux-gnu \
      --runtime /runtime/system/lib-x86_64=/lib/x86_64-linux-gnu \
      --runtime /runtime/system/python3.12=/usr/lib/python3.12 \
      --runtime /runtime/system/include=/usr/include \
      --runtime /runtime/system/git-core=/usr/share/git-core \
      --runtime /runtime/system/perl5=/usr/share/perl5 \
      --runtime /runtime/system/ld-linux-x86-64.so.2=/lib64/ld-linux-x86-64.so.2 \
      --cache-root /var/cache/align-llm/cargo \
      --cache-manifest /usr/local/share/align-llm/fresh-cargo-cache.json \
      --output /usr/local/share/align-llm/fresh-toolchain.json

RUN mkdir -p /usr/local/share/align-llm/self-test/project/scripts \
      /usr/local/share/align-llm/self-test/align && \
    install -m 0755 /build/align-llm/image/fresh/fixtures/fresh-align-compiler \
      /usr/local/share/align-llm/self-test/project/scripts/fresh-align-compiler && \
    git -C /usr/local/share/align-llm/self-test/project init && \
    git -C /usr/local/share/align-llm/self-test/project config user.name 'FRESH-IMAGE' && \
    git -C /usr/local/share/align-llm/self-test/project config user.email 'fresh-image@example.invalid' && \
    git -C /usr/local/share/align-llm/self-test/project add scripts/fresh-align-compiler && \
    GIT_AUTHOR_DATE='2000-01-01T00:00:00Z' GIT_COMMITTER_DATE='2000-01-01T00:00:00Z' \
      git -C /usr/local/share/align-llm/self-test/project commit -m 'Install synthetic worker' && \
    rm -rf /build

ARG IMAGE_PUBLIC_KEY_HEX
ARG RUN_PUBLIC_KEY_HEX
RUN python3 - <<'PY'
import os
import re
from pathlib import Path

image = os.environ.get("IMAGE_PUBLIC_KEY_HEX", "")
run = os.environ.get("RUN_PUBLIC_KEY_HEX", "")
for name, value in (("image-verifier.pub", image), ("run-verifier.pub", run)):
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SystemExit(f"missing or invalid build key: {name}")
    path = Path("/usr/local/share/align-llm") / name
    path.write_bytes(bytes.fromhex(value))
    path.chmod(0o444)
PY

ENTRYPOINT ["/usr/local/libexec/align-llm/fresh-supervise"]
CMD ["--mode", "self-test"]
