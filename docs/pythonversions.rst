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

As of Feburary 2022, here are approximate support periods for various
Python versions:

====== ======================
Python cwltool end of support
====== ======================
3.6    June 2024 (Centos 7 EOL)
3.7    June 2023 (upstream EOL)
3.8    April 2025 (Ubuntu 20.04 EOL)
3.9    October 2025 (upstream EOL)
3.10   October 2026 (upstream EOL)
====== ======================

For reference (as of Feburary 2022)

====== =============================================
Python Linux distros where it is the default version
====== =============================================
3.6    Ubuntu 18.04, Centos 7
3.7    Debian 10
3.8    Ubuntu 20.04
3.9    Debian 11
3.10   None
====== =============================================

If there is a conflict between an essential dependency which has
dropped support for a Python version that cwltool should still
support, the all available options (such pinning the dependency,
removing the dependency, or dropping Python version support) will be
discussed with cwltool maintainers in consultation with downstream
users before making the decision to drop support for a Python version
earlier than outlined in this policy.
