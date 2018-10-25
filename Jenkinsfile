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
          bat(script: 'pip install .', returnStdout: true)
          bat 'jenkins.bat'
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
