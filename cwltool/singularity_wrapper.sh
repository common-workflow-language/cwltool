#!/usr/bin/env bash
set -euo pipefail

# singularity_wrapper.sh
#
# DESCRIPTION
#   Wrapper around Singularity/Apptainer for CWL + MPI + Singularity.
#
#   This script identifies environment variables added by an MPI launcher
#   (e.g. srun, mpirun) and adds these environment variables as Singularity
#   environment variables using the format ``SINGULARITYENV_$KEY=$VALUE``.
#
#   This allows CWL (which uses ``--cleanenv``) to launch MPI + Singularity.
#
# USAGE
#   singularity_wrapper.sh <baseline-env-file> <singularity-bin> <args>
#
# ARGUMENTS
#   <baseline-env-file>
#       Path to the file containing KEY=VALUE pairs with the baseline env.
#
#   <singularity-bin>
#       Path to singularity/apptainer executable.
#
#   [args...]
#       Arguments passed to the singularity binary.
#
# EXAMPLE
#   singularity_wrapper.sh env.txt singularity --cleanenv exec image.sif
#
# DEPENDENCIES
#   It uses the following binaries:
#   - printenv

usage() {
    cat >&2 <<EOF
singularity_wrapper.sh

Wrapper around Singularity/Apptainer for CWL + MPI + Singularity.

USAGE:
  singularity_wrapper.sh <baseline-env-file> <singularity-bin> [args...]
EOF
    exit 1
}

if [[ "${1:-}" == "--help" ]]; then
    usage
fi

[[ $# -ge 2 ]] || usage

BASELINE_FILE="$1"
SINGULARITY_BIN="$2"
shift 2

if [[ ! -f "$BASELINE_FILE" ]]; then
    echo "Error: baseline env file not found: $BASELINE_FILE" >&2
    exit 2
fi

# Read baseline env into a variable.
BASELINE_CONTENT=$'\n'"$(cat "$BASELINE_FILE")"$'\n'

# Build new environment variables for Singularity (i.e. ``SINGULARITYENV_KEY=VALUE``).
# Excludes empty variables and variables whose name do not follow POSIX (e.g. some
# Bash environments on HPC clusters such as BSC MareNostrum5, ``BASH_FUNC_module%%=``).
while IFS='=' read -r k v; do
    [[ -n "$k" ]] || continue
    [[ "$k" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    # If the current env doesn't exist (``! -z``) in the given baseline env (``BASE_ENV``),
    # then we want to add it as ``--env`` in singularity.
    # Check if the key exists in the BASELINE_CONTENT string in the
    # form \n$KEY= (that's why we start the BASELINE and end it with \n).
    if [[ ! "$BASELINE_CONTENT" == *$'\n'"$k"=* ]]; then
        # Debug
        # echo "Adding env var for Singularity command: SINGULARITYENV_$k=$v" >&2
        export "SINGULARITYENV_$k=$v"
    fi
done < <(printenv)

# Launch the Singularity binary.
exec "$SINGULARITY_BIN" "${@}"
