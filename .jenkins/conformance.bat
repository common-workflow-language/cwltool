CALL %~dp0\setup.bat

pip install cwltest %WORKSPACE%
cwltest --test=%WORKSPACE%\common-workflow-language\v1.0\conformance_test_v1.0.yaml --classname win7py36 --tool cwltool --junit-xml %WORKSPACE%\conformance.xml -j 2 --basedir %WORKSPACE%\common-workflow-language\v1.0\
