CALL %~dp0\setup.bat

pip install cwltest %WORKSPACE%
rd /s /q %WORKSPACE%\cwl
git clone https://github.com/common-workflow-language/common-workflow-language.git %WORKSPACE%\cwl
pushd %WORKSPACE%\cwl\v1.0
FOR /F "tokens=* USEBACKQ" %%F in ('cwltest --test=%%WORKSPACE%%\cwl\v1.0\conformance_test_v1.0.yaml -l ^| find /c /v ""') do (SET TESTS=%%F)
cwltest --test=%WORKSPACE%\cwl\v1.0\conformance_test_v1.0.yaml --classname win7py36 --tool cwltool --junit-xml %WORKSPACE%\conformance.xml -j 2 --basedir %WORKSPACE%\cwl\v1.0\ -n1-56,58-%TESTS%
popd
