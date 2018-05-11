CALL %~dp0\setup.bat

pip install cwltest %WORKSPACE%
rd /s /q %WORKSPACE%\cwl
git clone https://github.com/common-workflow-language/common-workflow-language.git %WORKSPACE%\cwl
cwltest --test=%WORKSPACE%\cwl\v1.0\conformance_test_v1.0.yaml --classname win7py36 --tool cwltool --junit-xml %WORKSPACE%\conformance.xml -j 2 --basedir %WORKSPACE%\cwl\v1.0\
