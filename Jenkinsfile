pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  options {
    timeout(30)
  }
  stages {
    stage('build') {
      steps {
        withPythonEnv(pythonInstallation: 'Windows-CPython-36') {
          pybat(script: 'pip install .', returnStdout: true)
          pybat 'jenkins.bat'
        }

      }
    }
  }
  post {
    always {
      junit 'tests.xml'

    }

  }
}
