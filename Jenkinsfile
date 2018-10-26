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
          bat '.jenkins/test.bat'
        }
      }
    }
    stage('CWL-conformance-test') {
      steps {
        withPythonEnv(pythonInstallation: 'Windows-CPython-36') {
          bat '.jenkins/conformance.bat'
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
