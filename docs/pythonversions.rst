=============================
Python version support policy
=============================

Cwltool will always support `stable Python 3 releases with active branches
<https://devguide.python.org/#status-of-python-branches>`_.

For versions that are no longer supported by Python upstream, cwltool
support also extends to the default Python version included in the
following major Linux distributions:

* Debian (`stable <https://wiki.debian.org/DebianStable>`_, `oldstable <https://wiki.debian.org/DebianOldStable>`_)
* Ubuntu (`LTS release standard support <https://wiki.ubuntu.com/Releases>`_)
* Centos 7 (`while in maintenance <https://wiki.centos.org/About/Product>`_)

If there is a conflict between a third party package dependency which
has dropped support for a Python version that cwltool should support
according to this policy, then possible options (such as pinning the
dependency, eliminating the dependency, or changing Python version
support of cwltool) should be discussed among the cwltool maintainers
and downstream users before making the decision to drop support for a
Python version before the date outlined in this policy.  The reasoning
for dropping support for a Python version should be outlined here.

As of February 2022, here are approximate cwltool support periods for
across Python versions:

====== ======================
Python cwltool end of support
====== ======================
2.7    ended January 2020
3.5    ended October 2020
3.6    June 2024 (Centos 7 EOL)
3.7    June 2023 (upstream EOL)
3.8    April 2025 (Ubuntu 20.04 EOL)
3.9    October 2025 (upstream EOL)
3.10   October 2026 (upstream EOL)
====== ======================

Default Python version of supported Linux distributions, for reference
(as of February 2022)

====== =============================================
Python Linux distros where it is the default version
====== =============================================
3.6    Ubuntu 18.04, Centos 7
3.7    Debian 10
3.8    Ubuntu 20.04
3.9    Debian 11
3.10   None
====== =============================================
