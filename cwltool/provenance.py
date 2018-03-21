from __future__ import absolute_import
import io
import json
import os
import os.path
import posixpath
import shutil
import tempfile
import itertools
import logging
import hashlib
from shutil import copyfile
import io
import time
import copy
import datetime
import prov.model as prov
from pathlib2 import Path
from networkx.drawing.nx_agraph import graphviz_layout
from networkx.drawing.nx_agraph import write_dot
from networkx.drawing.nx_pydot import write_dot
from .errors import WorkflowException
import prov.graph as graph
import uuid
import graphviz
import networkx as nx
import ruamel.yaml as yaml
import warnings
from typing import Any, Dict
from subprocess import check_call
from schema_salad.sourceline import SourceLine
from .process import shortname

warnings.simplefilter('ignore', yaml.error.UnsafeLoaderWarning)
relativised_input_object={}  # type: Dict[str, Any]
_logger = logging.getLogger("cwltool")

# RO folders
METADATA = "Metadata"
DATA = "Data"
OUTPUT= "Output"
WORKFLOW = "Workflow"
SNAPSHOT = "Snapshot"
# sub-folders
MAIN = os.path.join(WORKFLOW, "main")
PROVENANCE = os.path.join(METADATA, "Provenance")

class ProvenanceException(BaseException):
    pass


# sha1, compatible with the File type's "checksum" field
# e.g. "checksum" = "sha1$47a013e660d408619d894b20806b1d5086aab03b"
# See ./cwltool/schemas/v1.0/Process.yml
hashmethod = hashlib.sha1

class ResearchObject():
    def __init__(self, tmpPrefix="tmp"):
        # type: (...) -> None
        self.folder = tempfile.mkdtemp(prefix=tmpPrefix)
        self.tmpPrefix = tmpPrefix
        self._initialize()
        _logger.info(u"[provenance] Temporary research object: %s", self.folder)

    def _initialize(self):
        # type: (...) -> None
        for f in (METADATA, DATA, WORKFLOW, SNAPSHOT, PROVENANCE):
            os.makedirs(os.path.join(self.folder, f))

    def _finalize(self):
        # TODO: Write manifest and bagit metadata
        # _logger.info(u"[provenance] Generated research object manifest: %s", self.folder)
        pass


    def generate_provDoc(self, document, cwlversionProv, engineUUID, WorkflowRunUUID):
        '''
        add basic namespaces
        '''
        document.add_namespace('wfprov', 'http://purl.org/wf4ever/wfprov#')
        document.add_namespace('prov', 'http://www.w3.org/ns/prov')
        document.add_namespace('wfdesc', 'http://purl.org/wf4ever/wfdesc#')
        document.add_namespace('run', 'urn:uuid:')
        document.add_namespace('engine', 'urn:uuid4:')
        document.add_namespace('data', 'urn:hash:sha1')
        WorkflowRunID="run:"+WorkflowRunUUID
        roIdentifierWorkflow="app://"+WorkflowRunUUID+"/workflow/packed.cwl#"
        document.add_namespace("wf", roIdentifierWorkflow)
        roIdentifierInput="app://"+WorkflowRunUUID+"/workflow/master-job.json#"
        document.add_namespace("input", roIdentifierInput)
        document.agent(engineUUID, {prov.PROV_TYPE: "prov:SoftwareAgent", "prov:type": "wfprov:WorkflowEngine", "prov:label": cwlversionProv})
        #define workflow run level activity
        document.activity(WorkflowRunID, datetime.datetime.now(), None, {prov.PROV_TYPE: "wfprov:WorkflowRun", "prov:label": "Run of workflow/packed.cwl#main"})
        #association between SoftwareAgent and WorkflowRun
        mainWorkflow = "wf:main"
        document.wasAssociatedWith(WorkflowRunID, engineUUID, mainWorkflow)
        return WorkflowRunID


    def snapshot_generation(self, ProvDep):
        '''
        Copies all the cwl files involved in this workflow run to snapshot
        directory
        '''

        for key, value in ProvDep.items():
            if key == "location" and value.split("/")[-1]:
                filename= value.split("/")[-1]
                path = os.path.join(self.folder, SNAPSHOT, filename)
                filepath=''
                if "file://" in value:
                    filepath=value[7:]
                else:
                    filepath=value
                file_to_cp = Path(filepath)
                if file_to_cp.exists():
                    shutil.copy(filepath, path)
            elif key == "secondaryFiles" or key == "listing":
                for files in value:
                    if isinstance(files, dict):
                        self.snapshot_generation(files)
            else:
                pass

    def packed_workflow(self, packed):
        path = os.path.join(self.folder, WORKFLOW, "packed.cwl")
        with open(path, "w") as f:
            # YAML is always UTF8
            f.write(packed.encode("UTF-8"))
        _logger.info(u"[provenance] Added packed workflow: %s", path)
        return (path)

    def _checksum_copy(self, fp, copy_to_fp=None,
                       hashmethod=hashmethod, buffersize=1024*1024):
        checksum = hashmethod()
        contents = fp.read(buffersize)
        while contents != b"":
            if copy_to_fp is not None:
                copy_to_fp.write(contents)
            checksum.update(contents)
            contents = fp.read(buffersize)
        if copy_to_fp is not None:
            copy_to_fp.flush()
        return checksum.hexdigest().lower()


    def add_data_file(self, from_fp):
        with tempfile.NamedTemporaryFile(
                prefix=self.tmpPrefix, delete=False) as tmp:
            checksum = self._checksum_copy(from_fp, tmp)

        # Calculate hash-based file path
        folder = os.path.join(self.folder, DATA, checksum[0:2])
        path = os.path.join(folder, checksum)
        # os.rename assumed safe, as our temp file should
        # be in same file system as our temp folder
        if not os.path.isdir(folder):
            os.makedirs(folder)
        os.rename(tmp.name, path)

        # Relative posix path
        # (to avoid \ on Windows)
        rel_path = self._posix_path(os.path.relpath(path, self.folder))

        # Register in bagit checksum
        if hashmethod == hashlib.sha1:
            self._add_to_bagit(rel_path, sha1=checksum)
        else:
            _logger.warning(u"[provenance] Unknown hash method %s for bagit manifest",
                hashmethod)
            # Inefficient, bagit support need to checksum again
            self._add_to_bagit(rel_path)
        _logger.info(u"[provenance] Added data file %s", path)
        _logger.info(u"[provenance] Relative path for data file %s", rel_path)
        return rel_path

    def _convert_path(self, path, from_path=os.path, to_path=posixpath):
        if from_path == to_path:
            return path
        if (from_path.isabs(path)):
            raise ProvenanceException("path must be relative: %s" % path)
            # ..as it might include system paths like "C:\" or /tmp
        split = path.split(from_path.sep)
        converted = to_path.sep.join(split)
        return converted

    def _posix_path(self, local_path):
        return self._convert_path(local_path, os.path, posixpath)

    def _local_path(self, posix_path):
        return self._convert_path(posix_path, posixpath, os.path)

    def _add_to_bagit(self, rel_path, **checksums):
        if (posixpath.isabs(rel_path)):
            raise ProvenanceException("rel_path must be relative: %s" % rel_path)
        local_path = os.path.join(self.folder, self._local_path(rel_path))
        if not os.path.exists(local_path):
            raise ProvenanceException("File %s does not exist within RO: %s" % rel_path, local_path)

        if "sha1" not in checksums:
            # ensure we always have sha1
            checksums = dict(checksums)
            with open(local_path) as fp:
                checksums["sha1"]= self._checksum_copy(fp, hashmethod=hashlib.sha1)

        # Add checksums to corresponding manifest files
        for (method,hash) in checksums.items():
            # Quite naive for now - assume file is not already listed in manifest
            manifest = os.path.join(self.folder,
                "manifest-" + method.lower() + ".txt")
            with open(manifest, "a") as checksumFile:
                line = "%s %s\n" % (hash, rel_path)
                _logger.info(u"[provenance] Added to %s: %s", manifest, line)
                checksumFile.write(line)

    def create_job(self, job, make_fs_access, kwargs):
        #TODO handle nested workflow at level 2 provenance
        #TODO customise the file
        '''
        This function takes the dictionary input object and generates
        a json file containing the relative paths and link to the associated
        cwl document
        '''
        relativised_input_objecttemp2={}
        relativised_input_objecttemp={}
        self._relativise_files(job, kwargs, make_fs_access, relativised_input_objecttemp2)
        path=os.path.join(self.folder, WORKFLOW, "master-job.json")
        _logger.info(u"[provenance] Generated customised job file: %s", path)
        with open(path, "w") as f:
            json.dump(job, f, indent=4)
        #Generate dictionary with keys as workflow level input IDs and values as
        #1) for files the relativised location containing hash
        #2) for other attributes, the actual value.
        with open(path, 'r') as f:
            MasterInput_file = json.load(f)
        relativised_input_objecttemp={}
        for key, value in MasterInput_file.iteritems():
            if isinstance(value, dict):
                if value.get("class") == "File":
                    relativised_input_objecttemp[key]=value
            else:
                relativised_input_objecttemp[key]=value
        relativised_input_object.update({k: v for k, v in relativised_input_objecttemp.items() if v})
        return relativised_input_object, relativised_input_objecttemp2

    def _relativise_files(self, structure, kwargs, make_fs_access, relativised_input_objecttemp2):
        '''
        save any file objects into RO and update the local paths
        '''
        # Base case - we found a File we need to update
        _logger.debug(u"[provenance] Relativising: %s", structure)
        if isinstance(structure, dict):
            if structure.get("class") == "File":
                #standardised fs access object creation
                fsaccess = make_fs_access("")
                # TODO: Replace location/path with new add_data_file() paths
                with fsaccess.open(structure["location"], "rb") as f:
                    relative_path=self.add_data_file(f)
                    ref_location=structure["location"]
                    structure["location"]= "../"+relative_path
                    relativised_input_objecttemp2[ref_location] = structure["location"]

            for o in structure.values():
                self._relativise_files(o, kwargs, make_fs_access, relativised_input_objecttemp2)
            return

        if isinstance(structure, str) or isinstance(structure, unicode):
            # Just a string value, no need to iterate further
            return
        try:
            for o in iter(structure):
                # Recurse and rewrite any nested File objects
                self._relativise_files(o, kwargs, make_fs_access, relativised_input_objecttemp2)
        except TypeError:
            pass

    def finalize_provProfile(self, document):
        '''
        Transfer the provenance related files to RO
        '''
        original_path=os.path.join(self.folder, PROVENANCE)
        provPath=original_path+"/ProvenanceProfile.json"
        provNpath=original_path+"/ProvNrepresentation.provn"
        provDot=original_path+'/ProvenanceDotGraph.dot'
        document.serialize(provPath, indent=2)
        ProvNfile= open(provNpath,"w+")
        ProvNfile.write(document.get_provn())
        provgraph=graph.prov_to_graph(document)
        pos = nx.nx_agraph.graphviz_layout(provgraph)
        nx.draw(provgraph, pos=pos)
        write_dot(provgraph, provDot)
        check_call(['dot','-Tpng',provDot,'-o',original_path+'/ProvenanceVisualGraph.png'])

    def startProcess(self, r, document, engineUUID, WorkflowRunID):
            '''
            record start of each step
            ''' 
            ProcessRunID="run:"+str(uuid.uuid4())
            #each subprocess is defined as an activity()
            provLabel="Run of workflow/packed.cwl#main/"+str(r.name)
            ProcessProvActivity = document.activity(ProcessRunID, None, None, {prov.PROV_TYPE: "wfprov:ProcessRun", "prov:label": provLabel})
            
            if hasattr(r, 'name') and ".cwl" not in getattr(r, "name") and "workflow main" not in getattr(r, "name"):
                document.wasAssociatedWith(ProcessRunID, engineUUID, str("wf:main/"+r.name))
            document.wasStartedBy(ProcessRunID, None, WorkflowRunID, datetime.datetime.now(), None, None)
            return ProcessProvActivity

    def declare_artefact(self, relativised_input_object, document, job_order_object): 
        '''
        create data artefact entities for all file objects.
        '''
        if isinstance(relativised_input_object, dict):
            # Base case - we found a File we need to update
            if relativised_input_object.get("class") == "File":
                #create an artefact
                shahash="data:"+relativised_input_object["location"].split("/")[-1] 
                document.entity(shahash, {prov.PROV_TYPE:"wfprov:Artifact"})
                
            for o in relativised_input_object.values():
                self.declare_artefact(o, document, job_order_object)
            return

        if isinstance(relativised_input_object, str) or isinstance(relativised_input_object, unicode):
            # Just a string value, no need to iterate further
            return

        try:
            for o in iter(relativised_input_object):
                # Recurse and rewrite any nested File objects
                self.declare_artefact(o, document, job_order_object)
        except TypeError:
            pass


    def generate_outputProv(self, final_output, document, WorkflowRunID=None, ProcessRunID=None, name=None):
        '''
        create wasGeneratedBy() for each output and copy each output file in the RO
        '''
        key_files=[]
        for key, value in final_output.items():

            if isinstance(value, list):
                key_files.append(self.array_output(key, value))
            elif isinstance (value, dict):
                key_files.append(self.dict_output(key, value))

        merged_total= list(itertools.chain.from_iterable(key_files))

        #generate data artefacts at workflow level
        for tuple_entry in merged_total:
            output_checksum="data:"+str(tuple_entry[1][5:])

            if ProcessRunID:
                stepProv =  "wf:main"+"/"+name+"/"+str(tuple_entry[0])
                document.entity(output_checksum, {prov.PROV_TYPE:"wfprov:SubProcessArtifact"})
                document.wasGeneratedBy(output_checksum, ProcessRunID, datetime.datetime.now(), None, {"prov:role":stepProv})
            else:
                outputProvRole ="wf:main"+"/"+str(tuple_entry[0])
                document.entity(output_checksum, {prov.PROV_TYPE:"wfprov:Artifact"})
                document.wasGeneratedBy(output_checksum, WorkflowRunID, datetime.datetime.now(), None, {"prov:role":outputProvRole })

                #copy the file in Outputs
                outputfile_path= os.path.join(self.folder, OUTPUT, tuple_entry[1][5:7])
                path = os.path.join(outputfile_path, tuple_entry[1][5:])
                if not os.path.isdir(path):
                    os.makedirs(path)
                _logger.info(u"[provenance] Moving output files to RO")
                shutil.copy(tuple_entry[2][7:], path) 

    def array_output(self, key, current_l): 
        '''
        helper function for generate_outputProv()
        for the case when we have an array of files as output
        '''
        new_l=[]
        for y in current_l:
            if isinstance(y, dict):
                new_l.append((key, y['checksum'], y['location']))

        return new_l

    def dict_output(self, key, current_dict):
        '''
        helper function for generate_outputProv()
        for the case when the output is key:value where value is a file item
        '''
        new_d = []
        if current_dict.get("class") == "File":
            new_d.append((key, current_dict['checksum'], current_dict['location']))
        return new_d

    def used_artefacts(self, job_order, ProcessProvActivity, document, reference_locations, name):
        '''
        adds used() for each data artefact
        '''
        for key, value in job_order.items():
            provRole=name+"/"+str(key)
            ProcessRunID=str(ProcessProvActivity.identifier)
            if 'location' in str(value):
                location=str(value['location'])
                filename=str(value["location"]).split("/")[-1]
                if location in reference_locations:  # workflow level inputs referenced as hash in prov document
                    document.used(ProcessRunID, "data:"+str(reference_locations[location]), datetime.datetime.now(), None, {"prov:role":provRole })
                elif len(filename)==40 and int(filename, 16): #for the case when you re-run the master-job.json
                    document.used(ProcessRunID, "data:"+filename, datetime.datetime.now(),None, {"prov:role":provRole })
                else:  # add checksum created by cwltool of the intermediate data products. NOTE: will only work if --compute-checksums is enabled.
                    document.used(ProcessRunID, "data:"+str(value['checksum'][5:]), datetime.datetime.now(),None, {"prov:role":provRole })
            else:  # add the actual data value in the prov document
                ArtefactValue="data:"+str(value)
                document.entity(ArtefactValue, {prov.PROV_TYPE:"wfprov:Artifact"})
                document.used(ProcessRunID, ArtefactValue, datetime.datetime.now(),None, {"prov:role":provRole })

    def copy_job_order(self, r, job_order_object):
        '''
        creates copy of job object for provenance
        '''
        customised_job={} #new job object for RO
        for e, i in enumerate(r.tool["inputs"]):
            with SourceLine(r.tool["inputs"], e, WorkflowException, _logger.isEnabledFor(logging.DEBUG)):
                iid = shortname(i["id"])
                if iid in job_order_object:
                    customised_job[iid]= copy.deepcopy(job_order_object[iid]) #add the input element in dictionary for provenance
                elif "default" in i:
                    customised_job[iid]= copy.deepcopy(i["default"]) #add the defualt elements in the dictionary for provenance
                else:
                    raise WorkflowException(
                        u"Input '%s' not in input object and does not have a default value." % (i["id"]))
        return customised_job

    def prospective_prov(self, document, r):
        steps=[]
        for s in r.steps:
            stepname="wf:main/"+str(s.name)[5:]
            steps.append(stepname)
            document.entity(stepname, {prov.PROV_TYPE: "wfdesc:Process", "prov:type": "prov:Plan"})
        #create prospective provenance recording for the workflow
        document.entity("wf:main", {prov.PROV_TYPE: "wfdesc:Process", "prov:type": "prov:Plan", "wfdesc:hasSubProcess=":str(steps),  "prov:label":"Prospective provenance"})


#**************************************

    def close(self, saveTo=None):
        """Close the Research Object, optionally saving to specified folder.

        Closing will remove any temporary files used by this research object.
        After calling this method, this ResearchObject instance can no longer
        be used, except for no-op calls to .close().

        The 'saveTo' folder should not exist - if it does, it will be deleted.

        It is safe to call this function multiple times without the
        'saveTo' argument, e.g. within a try..finally block to
        ensure the temporary files of this RO are removed.
        """
        if saveTo is None:
            if self.folder:
                _logger.info(u"[provenance] Deleting temporary %s", self.folder)
                shutil.rmtree(self.folder, ignore_errors=True)
        else:
            _logger.info(u"[provenance] Finalizing Research Object")
            self._finalize()  # write manifest etc.
            # TODO: Write as archive (.zip or .tar) based on extension?

            if os.path.isdir(saveTo):
                _logger.info(u"[provenance] Deleting existing %s", saveTo)
                shutil.rmtree(saveTo)

            shutil.move(self.folder, saveTo)
            _logger.info(u"[provenance] Research Object saved to %s", saveTo)
        # Forget our temporary folder, which should no longer exists
        # This makes later close() a no-op
        self.folder = None

def create_researchObject(tmpPrefix  # type: str
             ):
    return ResearchObject(tmpPrefix)
