pipeline {
  agent {
    node {
      label 'windows'
    }
  }
  environment {
    CODECOV_TOKEN = credentials('jenkins-codecov-token')
  }
  stages {
    stage('build') {
      steps {
        withPythonEnv(pythonInstallation: 'Windows-CPython-36') {
          bat 'jenkins.bat'
        }
      }
    }
    stage('CWL-conformance-test') {
      steps {
        git 'https://github.com/common-workflow-language/common-workflow-language.git'
        withPythonEnv(pythonInstallation: 'Windows-CPython-36') {
          pybat '.jenkins/conformance_test.bat'
        }
      }
    }
  }
  post {
    always {
      junit 'tests.xml,**/conformance.xml'

    }

  }
}
