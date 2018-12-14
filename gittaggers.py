import subprocess
import time
import pkg_resources
from setuptools.command.egg_info import egg_info

SETUPTOOLS_VER = pkg_resources.get_distribution(
    "setuptools").version.split('.')

[major,minor,sub] = [ int(item) for item in SETUPTOOLS_VER ]

RECENT_SETUPTOOLS = major > 40 or (major == 40 and minor or (major == 40 and minor==0 and sub > 0))
# 40.6.3 does not have vtags
if major == 40 and minor == 6 and sub == 3:
    RECENT_SETUPTOOLS=False

class EggInfoFromGit(egg_info):
    """Tag the build with git commit timestamp.

    If a build tag has already been set (e.g., "egg_info -b", building
    from source package), leave it alone.
    """

    def git_timestamp_tag(self):
        gitinfo = subprocess.check_output(
            ['git', 'log', '--first-parent', '--max-count=1',
             '--format=format:%ct', '.']).strip()
        return time.strftime('.%Y%m%d%H%M%S', time.gmtime(int(gitinfo)))

    def tags(self):
        if self.tag_build is None:
            try:
                self.tag_build = self.git_timestamp_tag()
            except subprocess.CalledProcessError:
                pass
        return egg_info.tags(self)

    if RECENT_SETUPTOOLS:
        vtags = property(tags)
