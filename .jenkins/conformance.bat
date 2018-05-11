CALL %~dp0\setup.bat

pip install cwltest .
cwltest --test=common-workflow-language\v1.0\conformance_test_v1.0.yaml --classname win7py36 --tool cwltool --junit-xml conformance.xml -j 2 --basedir common-workflow-language\v1.0
