pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        withPythonEnv(pythonInstallation: 'Windows-CPython-36') {
          pybat(script: 'pip install .', returnStdout: true)
          pybat 'setup.py test --addopts --junit-xml=tests.xml'
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