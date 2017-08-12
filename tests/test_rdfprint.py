from __future__ import absolute_import
import unittest

from six import StringIO
from cwltool.main import main

class RDF_Print(unittest.TestCase):

    def test_rdf_print(self):
        self.maxDiff = None

        expected_output = """@prefix CommandLineBinding: <https://w3id.org/cwl/cwl#CommandLineBinding/> .
@prefix CommandLineTool: <https://w3id.org/cwl/cwl#CommandLineTool/> .
@prefix CommandOutputBinding: <https://w3id.org/cwl/cwl#CommandOutputBinding/> .
@prefix Dirent: <https://w3id.org/cwl/cwl#Dirent/> .
@prefix DockerRequirement: <https://w3id.org/cwl/cwl#DockerRequirement/> .
@prefix EnvVarRequirement: <https://w3id.org/cwl/cwl#EnvVarRequirement/> .
@prefix EnvironmentDef: <https://w3id.org/cwl/cwl#EnvironmentDef/> .
@prefix ExpressionTool: <https://w3id.org/cwl/cwl#ExpressionTool/> .
@prefix File: <https://w3id.org/cwl/cwl#File/> .
@prefix InlineJavascriptRequirement: <https://w3id.org/cwl/cwl#InlineJavascriptRequirement/> .
@prefix LinkMergeMethod: <https://w3id.org/cwl/cwl#LinkMergeMethod/> .
@prefix Parameter: <https://w3id.org/cwl/cwl#Parameter/> .
@prefix ResourceRequirement: <https://w3id.org/cwl/cwl#ResourceRequirement/> .
@prefix ScatterMethod: <https://w3id.org/cwl/cwl#ScatterMethod/> .
@prefix SchemaDefRequirement: <https://w3id.org/cwl/cwl#SchemaDefRequirement/> .
@prefix SoftwarePackage: <https://w3id.org/cwl/cwl#SoftwarePackage/> .
@prefix SoftwareRequirement: <https://w3id.org/cwl/cwl#SoftwareRequirement/> .
@prefix Workflow: <https://w3id.org/cwl/cwl#Workflow/> .
@prefix cwl: <https://w3id.org/cwl/cwl#> .
@prefix ns1: <rdfs:> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sld: <https://w3id.org/cwl/salad#> .
@prefix xml: <http://www.w3.org/XML/1998/namespace> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://raw.githubusercontent.com/common-workflow-language/workflows/master/workflows/hello/hello.cwl> a cwl:Workflow ;
    Workflow:steps <https://raw.githubusercontent.com/common-workflow-language/workflows/master/workflows/hello/hello.cwl#step0> ;
    cwl:cwlVersion cwl:v1.0 ;
    cwl:outputs <https://raw.githubusercontent.com/common-workflow-language/workflows/master/workflows/hello/hello.cwl#response> ;
    ns1:comment "Outputs a message using echo" ;
    ns1:label "Hello World" .

<https://raw.githubusercontent.com/common-workflow-language/workflows/master/workflows/hello/hello.cwl#response> cwl:outputSource <https://raw.githubusercontent.com/common-workflow-language/workflows/master/workflows/hello/hello.cwl#step0/response> ;
    sld:type cwl:File .
"""

        argsl = ['--print-rdf', 'https://raw.githubusercontent.com/common-workflow-language/workflows/master/workflows/hello/hello.cwl']

        # capture stdout
        out = StringIO()
        main(argsl=argsl, stdout=out)
        # check substring in the actual print-rdf
        self.assertTrue(expected_output in out.getvalue(), True)
