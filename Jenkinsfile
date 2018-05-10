pipeline {
  agent {
    node {
      label 'windows'
    }

  }
  stages {
    stage('build') {
      steps {
        pybat 'python setup.py test'
      }
    }
  }
}