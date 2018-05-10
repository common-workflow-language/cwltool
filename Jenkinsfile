pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
	withPythonEnv('python') {
          pybat 'python setup.py test'
        }
      }
    }
  }
}
