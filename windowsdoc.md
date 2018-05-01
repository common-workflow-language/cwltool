# Windows Compatibility
The CWL reference runner, cwltool, is compatible with Microsoft Windows when
Docker is installed. On Windows, all CWL CommandLineTools are executed using
[Docker software containers](https://docs.docker.com/docker-for-windows/). The
default Docker Container is
[Alpine with Bash support](https://github.com/frol/docker-alpine-bash). You can
specify other Docker Containers for your tools and workflows using hints,
[requirements](http://www.commonwl.org/v1.0/CommandLineTool.html#DockerRequirement)),
or the `--default-container` cwltool option.

## Supported Windows versions
* Windows 10 with native [Docker for Windows](https://docs.docker.com/docker-for-windows/).
* Windows 7, 8, and 8.1 with [Docker ToolBox](https://docs.docker.com/toolbox/toolbox_install_windows/).

If you are using Docker Toolbox, then you must run cwltool in the Docker
Quickstart Terminal.

## Installation

You can install cwltool using pip or directly from source code.

### Requirements

Before installing cwltool, please install:

* [Python 2 or 3](https://www.python.org/downloads/windows/)
* [Docker](https://docs.docker.com/docker-for-windows/install/)
* [Node.js](https://nodejs.org/en/download/) (optional, please install if your
  workflows or tools contain [Javascript Expressions](http://www.commonwl.org/v1.0/CommandLineTool.html#InlineJavascriptRequirement))

### Install using pip (recommended)

```
pip install cwltool
```

### Install from source

```
git clone https://github.com/common-workflow-language/cwltool.git
cd cwltool
pip install .
```

***Note:*** In order to test if cwltool has been successfully installed on your
Windows system, run `cwltool` in `cmd`. If you see help instructions, cwltool was successfully installed.

```
   CWL document required, no input file was provided
   usage: cwltool [-h] [--basedir BASEDIR] [--outdir OUTDIR] [--no-container]
                  [--preserve-environment ENVVAR] [--preserve-entire-environment]
                  [--rm-container | --leave-container]
                  [--tmpdir-prefix TMPDIR_PREFIX]
                  .......................
```

## Running tests

There are two types of tests available for cwltool: unit tests and conformance tests.

### Unit tests

To run cwltool's unit tests, run the following command:
```
python -m pytest --pyarg cwltool
```

Or go to the checkout of the cwltool Git repository on your system and run:

```
python setup.py test
```



### Conformance tests

To run the CWL conformance tests, follow these instructions:

```
pip install cwltest mock
git clone https://github.com/common-workflow-language/common-workflow-language.git
cd common-workflow-language/v1.0
cwltest --test conformance_test_v1.0.yaml -j 4 --tool cwltool
```
The `-j` options is used to run multiple tests in parallel.

## Troubleshooting

You may encounter some problems with Docker on Windows.

### Docker doesn't work on Windows, even outside cwltool

Make sure you followed all instructions carefully while installing Docker.
Please check the Environment variables. If the problem persists, we recommend
consulting the [online Docker Community](https://forums.docker.com/).

### Your local drives are not being shared with Docker Containers

* ***On native Docker for Windows (supported by Windows 10):***
On your tray, next to your clock, right-click on Docker, then click on Settings,
there you'll find the shared rdives: Here you can share your drives with Docker.
If you encounter a problem with your firewall, please
[refer this to post](https://blog.olandese.nl/2017/05/03/solve-docker-for-windows-error-a-firewall-is-blocking-file-sharing-between-windows-and-the-containers/).

* ***On Docker Toolbox:***
Docker Toolbox uses Virtualbox to create a linux base on which Docker machine runs.
Your Docker Container will be created inside Virtualbox. To share drives
in virtualbox, go to ****Virtualbox->settings->shared folders->Machine Folders****
Here Map the drives you want to share with your Docker Container.
If you want to keep these settings permanent (Recommended!), You should mark the
`make permanent` checkbox or else these settings will be erased every time your
virtualbox closes.

### In a Docker Container with shared drives, not all files are shown on `ls`

This means your drives/folders are not shared properly. Docker uses caching,
which may result in not all files and folders being listed on ls. In order to
solve this problem, make your drive mapping settings permanent (see previous
question).

### Can't create/modify a file in Docker when using cwltool

When folders are shared with Docker Container, they inherit their current file
access permissions. If you can write to a folder (with your current privileges)
on your local machine, you should be able to write to that folder inside Docker
Container also (provided same user initiated Docker). In all it is a file
permission issue.

### Workflows with Javascript Expressions occasionally give Timeout errors
To evaluate Javascript Expressions, cwltool looks for Nodejs on your system.
In case Nodejs isn't installed, JS expressions are executed in a Docker Container.
In order to avoid waiting forever in case error occurs, cwltool times out js
expression evaluation after a timeout period (by default 20 seconds). You can
provide a custom timeout period using `--eval-timeout` argument. So if you face
this error, the best option is to install Nodejs on your local system. If you
can't then use the `--eval-timeout` argument and set a higher timeout value.

*If you still have problems with setting up and using Docker on Windows, please
consult the online Docker Community. If the problem is specific to cwltool,
create an [issue on cwltool](https://github.com/common-workflow-language/cwltool/issues).*

