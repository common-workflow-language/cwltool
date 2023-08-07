=============================
Python version support policy
=============================

`cwltool` will always support `Python 3 versions that are officially supported by the Python Software Foundation
<https://devguide.python.org/versions/#versions>`_.

For versions that are no longer supported by the Python Software Foundation (or "upstream" for short), cwltool
support also extends to the latest Python versions included in the
following major Linux distributions:

* Debian (`stable <https://www.debian.org/releases/>`_)
* Ubuntu (`LTS release standard support <https://wiki.ubuntu.com/Releases>`_)

This means that users may need to install a newer version of Python
from their Linux distributor if the default version is too old.

If there is a conflict between a third party package dependency which
has dropped support for a Python version that cwltool should support
according to this policy, then possible options (such as pinning the
dependency, eliminating the dependency, or changing Python version
support of cwltool) should be discussed among the cwltool maintainers
and downstream users before making the decision to drop support for a
Python version before the date outlined in this policy.  The reasoning
for dropping support for a Python version should be outlined here.

As of 2023-08-14, here are approximate cwltool support periods for Python versions (`EOL` == "End of Life", the end of the support period by that provider):

====== ======================
Python cwltool end of support
====== ======================
2.7    ended 2020-01 (upstream EOL)
3.5    ended 2020-10 (upstream EOL)
3.6    ended 2023-08-31 (change in cwltool policy)
3.7    ended 2023-07-27 (upstream EOL)
3.8    2024-10-14 (upstream EOL)
3.9    2025-10-01 (upstream EOL)
3.10   2027-04-01 (Ubuntu 22.04 LTS EOL)
3.11   2027-10-01 (upstream EOL)
3.12   2028-10-01 (planned upstream EOL)
3.13   2029-10-01 (planned upstream EOL)
====== ======================

Python version of supported Linux distributions, for reference
(as of August 2023)

============== =============================================
Python Version Linux distros where it is a supported version
============== =============================================
3.6            Ubuntu 18.04 LTS
3.7            Debian 10
3.8            Ubuntu 20.04 LTS
3.9            Debian 11, Ubuntu 20.04 LTS
3.10           Ubuntu 22.04 LTS
3.11           Debian 12
3.12           Debian 13 (planned)
============== =============================================
