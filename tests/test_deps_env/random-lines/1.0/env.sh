
#PACKAGE_DIRECTORY="/path/to/cwlroot"

# This shouldn't need to use bash-isms - but we don't know the full path to this file,
# so for testing it is setup this way. For actual deployments just using full paths
# directly would be preferable.
PACKAGE_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/"
export PATH=$PATH:$PACKAGE_DIRECTORY/scripts
