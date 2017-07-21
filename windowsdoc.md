## **Windows Compatible Cwltool**  
Windows Compatible cwltool means that now you can create and run your workflows usinng cwltool on windows under a docker container.
On windows, all tools and workflows will be executed inside a linux based docker container. If a Docker Container is not provided explicitly(using [Docker Requirement](http://www.commonwl.org/v1.0/CommandLineTool.html#DockerRequirement)) by user, we use a minimal, posix compliant Alpine Docker image which has Bash pre installed as fallback(Default) [Docker Container](https://github.com/frol/docker-alpine-bash).  
You can also provide your own Default Docker Container using `--default-container` argument.

### ***Requirements***:  
* python 2 or 3, Yes Now we support python 3 too.  
* Docker

### ***Best Practises***:  
You should install nodejs on your system if your Workflow contains [Javascript Expressions](http://www.commonwl.org/v1.0/CommandLineTool.html#InlineJavascriptRequirement).

### ***Installation***:  
**Using Pip**:  
You can install cwltool on windows using pip  
`pip install cwltool`

**Developing from source**:  
`git clone https://github.com/common-workflow-language/cwltool.git`  
`cd cwltool`  
`python setup.py develop`

***Note:*** In order to test if cwltool has been successfully installed on your windows system, run `cwltool` on your `cmd`. A screen showing help instructions should be there.

### ***Running Cwltool's Unittest***  
If you want to run cwltool's unit test, go to cwltool's repository on your system and run  
`python setup.py test`

### ***Running Conformance tests using cwltool***  
Download cwltest using `pip install cwltest`  
Clone `Common-Workflow-language` repository using `git clone https://github.com/common-workflow-language/common-workflow-language.git`   
change directory using `cd common-workflow-language/v1.0`  
Run Tests with `cwltest --test conformance_test_v1.0.yaml -j 4 --tool cwltool`, here `-j` arg is used to run multiple tests in parallel.

&nbsp;
&nbsp;

> ***Installing cwltool on windows is smooth but you may face some problems in setting up Docker. Some of the common issues and their solution are mentioned below.***

**Docker doesn't work on windows, even outside cwltool.**  
Make sure you followed all instructions carefully while installing Docker. Especially setting up Environment variables. Consult online Docker community if problem persists.

**You Local Drives are not being Shared with Docker Container.**  
* ***On native Docker for windows(supported by Windows 10):***  
On your tray, next to your clock, right-click on Docker, then click on Settings, there you'll find the Shared Drives: Here you can share your Drives with Docker.  
If you encounter a Firewall issue, you can [refer this post](https://blog.olandese.nl/2017/05/03/solve-docker-for-windows-error-a-firewall-is-blocking-file-sharing-between-windows-and-the-containers/).

* ***On Docker Toolbox:***  
Docker Toolbox uses Virtualbox to create linux base on which Docker machine runs. Your Docker Container will be created inside Virtualbox. To share you Drives
in virtualbox, go to ****Virtualbox->settings->shared folders->Machine Folders****
Here Map your Drives you want to share with your Docker Container.  
If you want to keep these settings permanent(Recommended!), You should mark `make permanent` checkbox or else these settings will be erased everytime your virtualbox closes.

**In a Docker Container with Shared Drives, few Files are shown on `ls` but most of them doesn't.**  
This means your Drives/Folders are not shared properly. When a path is mentioned in docker, it gets cached. So the few folder names that appear on `ls` is because of that.  
In order to solve this problem follow the previous question.

**Can't create/modify a file in Docker when using cwltool.**  
When folders are shared with docker Container, they inherit their current file access permission. If you can write to a folder(with your current privileges) on your local machine, you should be able to write to that folder inside Docker Container also(provided same user initiated Docker). In all it is a file permission issue.

**Workflows with Javascript Expressions occasionally gives Timeout error.**  
For evaluating `Javascript expressions` cwltool looks for Nodejs on your system, in case if it can't find a Nodejs installation it creates a node Docker container to execute JS expressions.  
In order to avoid waiting forever in case some error occurs, cwltool times out js expression evaluation after timeout period ends. You can provide a custom timeout period using `--eval-timeout` argument, by default its value is 20 sec.  
So if you face this error, best option is to install Nodejs on your local system. If you can't then use the `--eval-timeout` argument and set a higher timeout value.
 
> ***If you still face some issues setting up Docker on windows, please consult online Docker Community. If the Problem is specific to cwltool, create a issue on cwltool. We would definitely try to help you.***

