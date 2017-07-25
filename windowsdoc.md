## **Windows Compatible Cwltool**  
Windows Compatible cwltool means that now you can create and run your workflows using cwltool on Windows under a [Docker Container](https://docs.docker.com/docker-for-windows/).
On Windows, all tools and workflows will be executed inside a linux based Docker Container. If a Docker Container is not provided explicitly (using [Docker Requirement](http://www.commonwl.org/v1.0/CommandLineTool.html#DockerRequirement)) by user, we use a minimal, posix compliant Alpine Docker image which has Bash pre installed as fallback (Default) [Docker Container](https://github.com/frol/docker-alpine-bash).  
You can also provide your own default Docker Container using `--default-container` argument.

### ***Windows Version Supported***:
* Windows 10 with native [Docker for Windows](https://docs.docker.com/docker-for-windows/).
* Windows 8.1 with [Docker ToolBox](https://docs.docker.com/toolbox/toolbox_install_windows/).
* Windows 7 & 8 with Docker ToolBox may work (Not tested).

### ***Requirements***:  
* Python 2 or 3.  
* Docker

### ***Best Practises***:  
You should install [Node.js](https://nodejs.org/) on your system if your workflow contains [Javascript Expressions](http://www.commonwl.org/v1.0/CommandLineTool.html#InlineJavascriptRequirement).

### ***Installation***:  
**Using Pip**:  
You can install cwltool on Windows using pip  
`pip install cwltool`

**Installing from source**:  
```
   git clone https://github.com/common-workflow-language/cwltool.git  
   cd cwltool  
   python setup.py develop
```
***Note:*** In order to test if cwltool has been successfully installed on your Windows system, run `cwltool` on your `cmd`. A screen showing help instructions should be there.

### ***Running Cwltool's Unit Tests***  
If you want to run cwltool's unit test, go to cwltool's repository on your system and run  
`python setup.py test`

### ***Running Conformance tests using cwltool***  
```pip install cwltest  
   git clone https://github.com/common-workflow-language/common-workflow-language.git   
   cd common-workflow-language/v1.0  
   cwltest --test conformance_test_v1.0.yaml -j 4 --tool cwltool
```
Here `-j` arg is used to run multiple tests in parallel.  

&nbsp;
&nbsp;

> #### Installing cwltool on Windows is smooth but you may face some problems in setting up Docker. Some of the common issues and their solution are mentioned below.

**Docker doesn't work on Windows, even outside cwltool.**  
Make into proper sentences: Make sure you followed all instructions carefully while installing Docker. Please check the Environment variables. If the problem persists, we recommend consulting the [online Docker Community](https://forums.docker.com/).

**Your local drives are not being shared with Docker Container.**  
* ***On native Docker for Windows (supported by Windows 10):***  
On your tray, next to your clock, right-click on Docker, then click on Settings, there you'll find the shared rives: Here you can share your drives with Docker.  
If you encounter a problem with your firewall, please [refer this post](https://blog.olandese.nl/2017/05/03/solve-docker-for-windows-error-a-firewall-is-blocking-file-sharing-between-windows-and-the-containers/).

* ***On Docker Toolbox:***  
Docker Toolbox uses Virtualbox to create a linux base on which Docker machine runs. Your Docker Container will be created inside Virtualbox. To share drives
in virtualbox, go to ****Virtualbox->settings->shared folders->Machine Folders****
Here Map the drives you want to share with your Docker Container.  
If you want to keep these settings permanent (Recommended!), You should mark the `make permanent` checkbox or else these settings will be erased every time your virtualbox closes.

**In a Docker Container with shared drives, not all files are shown on `ls`.**  
This means your drives/folders are not shared properly. Docker uses caching, which may result in not all files and folders being listed on ls.  
In order to solve this problem, make your drive mapping settings permanent (see previous question).

**Can't create/modify a file in Docker when using cwltool.**  
When folders are shared with Docker Container, they inherit their current file access permissions. If you can write to a folder (with your current privileges) on your local machine, you should be able to write to that folder inside Docker Container also (provided same user initiated Docker). In all it is a file permission issue.

**Workflows with Javascript Expressions occasionally give Timeout errors.**  
To evaluate Javascript Expressions, cwltool looks for Nodejs on your system. In case Nodejs isn't installed, JS expressions are executed in a Docker Container.  
In order to avoid waiting forever in case error occurs, cwltool times out js expression evaluation after a timeout period (by default 20 seconds). You can provide a custom timeout period using `--eval-timeout` argument.  
So if you face this error, the best option is to install Nodejs on your local system. If you can't then use the `--eval-timeout` argument and set a higher timeout value.
 
> #### If you still face some issues setting up and using Docker on Windows, please consult the online Docker Community. If the problem is specific to cwltool, create an [issue on cwltool](https://github.com/common-workflow-language/cwltool/issues).

