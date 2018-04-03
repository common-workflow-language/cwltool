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
from prov.identifier import Namespace
from prov.model import PROV
from pathlib2 import Path
# Disabled due to excessive transitive dependencies
#from networkx.drawing.nx_agraph import graphviz_layout
#from networkx.drawing.nx_pydot import write_dot
from .errors import WorkflowException
import prov.graph as graph
import uuid
import urllib
import graphviz
import networkx as nx
import ruamel.yaml as yaml
import warnings
from typing import Any, Dict, Set
from subprocess import check_call
from schema_salad.sourceline import SourceLine
from .process import shortname

warnings.simplefilter('ignore', yaml.error.UnsafeLoaderWarning)
relativised_input_object={}  # type: Dict[str, Any]
_logger = logging.getLogger("cwltool")

# RO folders
METADATA = "metadata"
DATA = "data"
WORKFLOW = "workflow"
SNAPSHOT = "snapshot"
# sub-folders
MAIN = os.path.join(WORKFLOW, "main")
PROVENANCE = os.path.join(METADATA, "provenance")
WFDESC=Namespace("wfdesc", 'http://purl.org/wf4ever/wfdesc#')
WFPROV=Namespace("wfprov", 'http://purl.org/wf4ever/wfprov#')

# BagIt and YAML always use UTF-8
ENCODING="UTF-8"

class ProvenanceException(BaseException):
    pass


# sha1, compatible with the File type's "checksum" field
# e.g. "checksum" = "sha1$47a013e660d408619d894b20806b1d5086aab03b"
# See ./cwltool/schemas/v1.0/Process.yml
hashmethod = hashlib.sha1

class ResearchObject():
    def __init__(self, tmpPrefix="tmp"):
        # type: (...) -> None
        self.tmpPrefix = tmpPrefix
        self.folder = tempfile.mkdtemp(prefix=tmpPrefix)
        # map of filename "data/de/alsdklkas": 12398123 bytes
        self.bagged_size = {} #type: Dict
        self.tagfiles = set() #type: Set

        # These should be replaced by generate_provDoc when workflow/run IDs are known:
        u = uuid.uuid4()
        self.workflowRunURI = "urn:uuid:%s" % u
        self.base_uri = "arcp://uuid,%s/" % u
        self.wf_ns = Namespace("ex", "http://example.com/wf-%s#" % u)
        self.cwltoolVersion = "cwltool (unknown version)"
        ##
        # This function will be added by create_job()
        self.make_fs_access = None
        ##

        self._initialize()
        _logger.info(u"[provenance] Temporary research object: %s", self.folder)

    def _initialize(self):
        # type: (...) -> None
        for f in (METADATA, DATA, WORKFLOW, SNAPSHOT, PROVENANCE):
            os.makedirs(os.path.join(self.folder, f))
        self._initialize_bagit()

    def _initialize_bagit(self):
        # type: (...) -> None
        # Write fixed bagit header
        bagit = os.path.join(self.folder, "bagit.txt")
        with io.open(bagit, "w", encoding = ENCODING) as bagitFile:
            # TODO: \n or \r\n ?
            # Special case, bagit.txt is ASCII only
            bagitFile.write(unicode("BagIt-Version: 0.97\n".encode(ENCODING)))
            bagitFile.write(unicode(("Tag-File-Character-Encoding: %s\n" % ENCODING).encode(ENCODING)))

    def _finalize(self):
        self._write_ro_manifest()
        self._write_bag_info()

    def add_tagfile(self, path):
        checksums = {}
        with open(path) as fp:
            # FIXME: Should have more efficient open_tagfile() that 
            # does all checksums in one go while writing through, 
            # adding checksums after closing. 
            # Below probably OK for now as metadata files
            # are not too large..?
            
            checksums["sha1"]= self._checksum_copy(fp, hashmethod=hashlib.sha1)
            fp.seek(0)
            # Older Python's might not have all checksums
            if "sha256" in hashlib.__all__:
                fp.seek(0)
                checksums["sha256"]= self._checksum_copy(fp, hashmethod=hashlib.sha256)            
            if "sha512" in hashlib.__all__:
                fp.seek(0)
                checksums["sha512"]= self._checksum_copy(fp, hashmethod=hashlib.sha512)
        rel_path = self._posix_path(os.path.relpath(path, self.folder))
        self.tagfiles.add(rel_path)
        self._add_to_manifest(rel_path, checksums)


    def _write_ro_manifest(self):


        # TODO: write metadata/manifest.json
        pass

    def _write_bag_info(self):
        info = os.path.join(self.folder, "bag-info.txt")        
        with open(info, "w") as infoFile:            
            infoFile.write(("External-Description: Research Object of CWL workflow run\n").encode(ENCODING))
            infoFile.write(("Bag-Software-Agent: %s\n" % self.cwltoolVersion).encode(ENCODING))
            infoFile.write(("Bagging-Date: %s\n" % datetime.date.today().isoformat()).encode(ENCODING))
            # FIXME: require sha-512 to comply with profile
            # FIXME: Update profile
            #infoFile.write(("BagIt-Profile-Identifier: https://w3id.org/ro/bagit/profile\n").encode(ENCODING))
            
            # Calculate size of data/ (assuming no external fetch.txt files)
            totalSize = sum(self.bagged_size.values())
            numFiles = len(self.bagged_size)
            infoFile.write(("Payload-Oxum: %d.%d\n" % (totalSize, numFiles)).encode(ENCODING))
            # NOTE: We can't use the urn:uuid:{UUID} of the workflow run (a prov:Activity) 
            # as identifier for the RO/bagit (a prov:Entity). However the arcp base URI is good.
            infoFile.write(("External-Identifier: %s\n" % self.base_uri).encode(ENCODING))
        self.add_tagfile(info)
        # TODO: Checksum of metadata files?
        _logger.info(u"[provenance] Generated bagit metadata: %s", self.folder)

    def generate_provDoc(self, document, cwltoolVersion, engineUUID, workflowRunUUID):
        '''
        add basic namespaces
        '''
        # For consistent formatting, ensure it's a valid UUID instance
        if not isinstance(workflowRunUUID, uuid.UUID):
            workflowRunUUID = uuid.UUID(str(workflowRunUUID))

        self.cwltoolVersion = cwltoolVersion
        document.add_namespace('wfprov', 'http://purl.org/wf4ever/wfprov#')
        #document.add_namespace('prov', 'http://www.w3.org/ns/prov#')
        document.add_namespace('wfdesc', 'http://purl.org/wf4ever/wfdesc#')
        document.add_namespace('run', 'urn:uuid:')
        document.add_namespace('engine', 'urn:uuid:')
        # NOTE: Internet draft expired 2004-03-04 (!)
        #  https://tools.ietf.org/html/draft-thiemann-hash-urn-01
        # TODO: Change to nih:sha-256; hashes
        #  https://tools.ietf.org/html/rfc6920#section-7
        document.add_namespace('data', 'urn:hash::sha1:')
        workflowRunID="run:%s" % workflowRunUUID
        self.workflowRunURI = "urn:uuid:%s" % workflowRunUUID
        # https://tools.ietf.org/id/draft-soilandreyes-arcp
        self.base_uri = "arcp://uuid,%s/" % workflowRunUUID
        ## info only, won't really be used by prov as sub-resources use /
        document.add_namespace('researchobject', self.base_uri)
        roIdentifierWorkflow= self.base_uri + "workflow/packed.cwl#"
        self.wf_ns = document.add_namespace("wf", roIdentifierWorkflow)
        roIdentifierInput=self.base_uri + "workflow/primary-job.json#"
        document.add_namespace("input", roIdentifierInput)
        document.agent(engineUUID, {prov.PROV_TYPE: PROV["SoftwareAgent"], "prov:type": WFPROV["WorkflowEngine"], "prov:label": cwltoolVersion})
        #define workflow run level activity
        document.activity(workflowRunID, datetime.datetime.now(), None, {prov.PROV_TYPE: WFPROV["WorkflowRun"], "prov:label": "Run of workflow/packed.cwl#main"})
        #association between SoftwareAgent and WorkflowRun
        # FIXME: Below assumes main workflow always called "#main", 
        # is this always true after packing?
        mainWorkflow = "wf:main"
        document.wasAssociatedWith(workflowRunID, engineUUID, mainWorkflow)
        document.wasStartedBy(workflowRunID, None, engineUUID, datetime.datetime.now())        
        return workflowRunID


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
                    self.add_tagfile(path)
            elif key == "secondaryFiles" or key == "listing":
                for files in value:
                    if isinstance(files, dict):
                        self.snapshot_generation(files)
            else:
                pass

    def packed_workflow(self, packed):
        '''
        packs workflow and commandline tools to generate re-runnable workflow object in RO
        '''
        path = os.path.join(self.folder, WORKFLOW, "packed.cwl")
        with open(path, "w") as f:
            # YAML is always UTF8
            f.write(packed.encode(ENCODING))
        self.add_tagfile(path)            
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
        '''
        copies inputs to Data
        '''
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

    def _add_to_manifest(self, rel_path, checksums):
        if (posixpath.isabs(rel_path)):
            raise ProvenanceException("rel_path must be relative: %s" % rel_path)        
        
        if (posixpath.commonprefix(["data/", rel_path]) == "data/"):
            # payload file, go to manifest
            manifest = "manifest"
        else:
            # metadata file, go to tag manifest
            manifest = "tagmanifest"

        # Add checksums to corresponding manifest files
        for (method,hash) in checksums.items():
            # File not in manifest because we bailed out on 
            # existence in bagged_size above
            manifestpath = os.path.join(self.folder,
                "%s-%s.txt" % (manifest, method.lower()))
            with open(manifestpath, "a") as checksumFile:
                line = "%s %s\n" % (hash, rel_path)
                _logger.debug(u"[provenance] Added to %s: %s", manifestpath, line)
                checksumFile.write(line.encode(ENCODING))


    def _add_to_bagit(self, rel_path, **checksums):
        if (posixpath.isabs(rel_path)):
            raise ProvenanceException("rel_path must be relative: %s" % rel_path)
        local_path = os.path.join(self.folder, self._local_path(rel_path))
        if not os.path.exists(local_path):
            raise ProvenanceException("File %s does not exist within RO: %s" % rel_path, local_path)

        if (rel_path in self.bagged_size):
            # Already added, assume checksum OK
            return
        self.bagged_size[rel_path] = os.path.getsize(local_path)

        if "sha1" not in checksums:
            # ensure we always have sha1
            checksums = dict(checksums)
            with open(local_path) as fp:
                # FIXME: Need sha-256 / sha-512 as well for RO BagIt profile?
                checksums["sha1"]= self._checksum_copy(fp, hashmethod=hashlib.sha1)

        self._add_to_manifest(rel_path, checksums)

    def create_job(self, job, make_fs_access, kwargs):
        #TODO handle nested workflow at level 2 provenance
        #TODO customise the file
        '''
        This function takes the dictionary input object and generates
        a json file containing the relative paths and link to the associated
        cwl document
        '''
        self.make_fs_access = make_fs_access
        relativised_input_objecttemp2={}
        relativised_input_objecttemp={}
        self._relativise_files(job, kwargs, relativised_input_objecttemp2)
        path=os.path.join(self.folder, WORKFLOW, "primary-job.json")
        _logger.info(u"[provenance] Generated customised job file: %s", path)
        with open(path, "w") as f:
            json.dump(job, f, indent=4)
        self.add_tagfile(path)

        #Generate dictionary with keys as workflow level input IDs and values as
        #1) for files the relativised location containing hash
        #2) for other attributes, the actual value.
        with open(path, 'r') as f:
            # FIXME: Why read back the file we just wrote? It should still
            # be in the "job" object
            primaryInput_file = json.load(f)
        relativised_input_objecttemp={}
        for key, value in primaryInput_file.iteritems():
            if isinstance(value, dict):
                if value.get("class") == "File":
                    relativised_input_objecttemp[key]=value
            else:
                relativised_input_objecttemp[key]=value
        relativised_input_object.update({k: v for k, v in relativised_input_objecttemp.items() if v})
        return relativised_input_object, relativised_input_objecttemp2

    def _relativise_files(self, structure, kwargs, relativised_input_objecttemp2):
        '''
        save any file objects into RO and update the local paths
        '''
        # Base case - we found a File we need to update
        _logger.debug(u"[provenance] Relativising: %s", structure)
        if isinstance(structure, dict):
            if structure.get("class") == "File":
                #standardised fs access object creation
                fsaccess = self.make_fs_access("")
                # TODO: Replace location/path with new add_data_file() paths
                with fsaccess.open(structure["location"], "rb") as f:
                    relative_path=self.add_data_file(f)
                    ref_location=structure["location"]
                    structure["location"]= "../"+relative_path
                    if not "checksum" in structure:
                        # FIXME: This naively relies on add_data_file setting hash as filename
                        structure["checksum"] = "sha1$%s" % posixpath.basename(relative_path)
                    relativised_input_objecttemp2[ref_location] = structure["location"]

            for o in structure.values():
                self._relativise_files(o, kwargs, relativised_input_objecttemp2)
            return

        if isinstance(structure, str) or isinstance(structure, unicode):
            # Just a string value, no need to iterate further
            return
        try:
            for o in iter(structure):
                # Recurse and rewrite any nested File objects
                self._relativise_files(o, kwargs, relativised_input_objecttemp2)
        except TypeError:
            pass

    def finalize_provProfile(self, document):
        '''
        Transfer the provenance related files to RO
        '''
        original_path=os.path.join(self.folder, PROVENANCE)
        # TODO: Generate filename per workflow run also for nested workflows
        # nested-47b74496-9ffd-42e4-b1ad-9a10fc93b9ce-cwlprov.provn
        basename = original_path + "/primary.cwlprov"
        # TODO: Also support other profiles than CWLProv, e.g. ProvOne
        
        # https://www.w3.org/TR/prov-n/
        document.serialize(basename + ".provn", format="provn", indent=2)
        self.add_tagfile(basename + ".provn")
        
        # https://www.w3.org/TR/prov-xml/
        document.serialize(basename + ".xml", format="xml", indent=4)
        self.add_tagfile(basename + ".xml")
        
        # https://www.w3.org/Submission/prov-json/
        document.serialize(basename + ".json", format="json", indent=2)
        self.add_tagfile(basename + ".json")
        
        # "rdf" aka https://www.w3.org/TR/prov-o/ 
        # which can be serialized to ttl/nt/jsonld (and more!)

        # https://www.w3.org/TR/turtle/
        document.serialize(basename + ".ttl", format="rdf", rdf_format="turtle")
        self.add_tagfile(basename + ".ttl")
        
        # https://www.w3.org/TR/n-triples/
        document.serialize(basename + ".nt", format="rdf", rdf_format="ntriples")
        self.add_tagfile(basename + ".nt")
        
        # https://www.w3.org/TR/json-ld/
        # TODO: Use a nice JSON-LD context
        # see also https://eprints.soton.ac.uk/395985/
        # 404 Not Found on https://provenance.ecs.soton.ac.uk/prov.jsonld :(
        document.serialize(basename + ".jsonld", format="rdf", rdf_format="json-ld")
        self.add_tagfile(basename + ".jsonld")
        _logger.info("[provenance] added all tag files")
        # https://www.graphviz.org/ dot
        provDot= basename + ".dot"
## NOTE: graphviz rendering disabled
## .. as nx requires excessive/tricky dependencies
#        provgraph=graph.prov_to_graph(document)
#        pos = nx.nx_agraph.graphviz_layout(provgraph)
#        nx.draw(provgraph, pos=pos)
#        write_dot(provgraph, provDot)
#        check_call(['dot','-Tpng',provDot,'-o',original_path+'/ProvenanceVisualGraph.png'])
#        self.add_tagfile(provDot)

    def startProcess(self, r, document, engineUUID, WorkflowRunID):
            '''
            record start of each step
            ''' 
            ProcessRunID="run:"+str(uuid.uuid4())
            #each subprocess is defined as an activity()
            ProcessName= urllib.quote(str(r.name), safe=":/,#")
            provLabel="Run of workflow/packed.cwl#main/"+ProcessName
            ProcessProvActivity = document.activity(ProcessRunID, None, None, {prov.PROV_TYPE: WFPROV["ProcessRun"], "prov:label": provLabel})
            
            if hasattr(r, 'name') and ".cwl" not in getattr(r, "name") and "workflow main" not in getattr(r, "name"):
                document.wasAssociatedWith(ProcessRunID, engineUUID, str("wf:main/"+ProcessName))
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
                document.entity(shahash, {prov.PROV_TYPE:WFPROV["Artifact"]})
                
            for o in relativised_input_object.values():
                self.declare_artefact(o, document, job_order_object)
            return

        if isinstance(relativised_input_object, str) or isinstance(relativised_input_object, unicode):
            # Just a string value, no need to iterate further
            # FIXME: Should these be added as PROV entities as well?
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
            # FIXME: What are these magic array[][] positions???
            output_checksum="data:"+str(tuple_entry[1][5:])

            if ProcessRunID:
                name = urllib.quote(name, safe=":/,#")
                stepProv = self.wf_ns["main"+"/"+name+"/"+str(tuple_entry[0])]

                document.entity(output_checksum, {prov.PROV_TYPE: WFPROV["Artifact"]})
                document.wasGeneratedBy(output_checksum, ProcessRunID, datetime.datetime.now(), None, {"prov:role":stepProv})
            else:
                outputProvRole = self.wf_ns["main"+"/"+str(tuple_entry[0])]
                document.entity(output_checksum, {prov.PROV_TYPE:WFPROV["Artifact"]})
                document.wasGeneratedBy(output_checksum, WorkflowRunID, datetime.datetime.now(), None, {"prov:role":outputProvRole })

                # FIXME: What are these magic array positions???
                with open(tuple_entry[2][7:]) as fp:
                    rel_path = self.add_data_file(fp)
                    _logger.info(u"[provenance] Adding output file %s to RO", rel_path)

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
            provRole = self.wf_ns["main"+"/"+name+"/"+str(key)]
            ProcessRunID=str(ProcessProvActivity.identifier)
            if isinstance(value, dict) and 'location' in value:
                location=str(value['location'])
                #filename=location.split("/")[-1]
                filename=posixpath.basename(location)
                
                if 'checksum' in value:
                    c = value['checksum']
                    _logger.info("[provenance] Used data w/ checksum %s", c)
                    (method, checksum) = value['checksum'].split("$", 1)
                    if (method == "sha1"):
                        document.used(ProcessRunID, "data:%s" % checksum, datetime.datetime.now(),None, {"prov:role":provRole })
                        return # successfully logged
                    else:
                        _logger.warn("[provenance] Unknown checksum algorithm %s", method)
                        pass
                else:
                    _logger.info("[provenance] Used data w/o checksum %s", location)
                    # FIXME: Store manually
                    pass

                # If we made it here, then we didn't log it correctly with checksum above,
                # we'll have to hash it again (and potentially add it to RO)
                # TODO: Avoid duplication of code here and in 
                # _relativise_files()
                # TODO: check we don't double-hash everything now
                fsaccess = self.make_fs_access("")
                with fsaccess.open(location, "rb") as f:
                    relative_path=self.add_data_file(f)
                    checksum = posixpath.basename(relative_path)
                    document.used(ProcessRunID, "data:%s" % checksum, datetime.datetime.now(),None, {"prov:role":provRole })

            else:  # add the actual data value in the prov document
                # Convert to bytes so we can get a hash (and add to RO)
                b = io.BytesIO(str(value).encode(ENCODING))
                data_file = self.add_data_file(b)
                # FIXME: Don't naively assume add_data_file uses hash in filename!
                data_id="data:" + posixpath.split(data_file)[1]
                document.entity(data_id, {prov.PROV_TYPE:WFPROV["Artifact"], prov.PROV_VALUE:str(value)})
                document.used(ProcessRunID, data_id, datetime.datetime.now(),None, {"prov:role":provRole })

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
        '''
        create prospective provenance recording for the workflow as wfdesc prov:Plan
        '''

        # FIXME: Workflow is not always called "#main"!
        document.entity("wf:main", {prov.PROV_TYPE: WFDESC["Process"], "prov:type": PROV["Plan"], "prov:label":"Prospective provenance"})

        steps=[]
        for s in r.steps:
            # FIXME: Use URI fragment identifier for step name, e.g. for spaces
            stepnametemp="wf:main/"+str(s.name)[5:]
            stepname=urllib.quote(stepnametemp, safe=":/,#")
            steps.append(stepname)
            step = document.entity(stepname, {prov.PROV_TYPE: WFDESC["Process"], "prov:type": PROV["Plan"]})
            document.entity("wf:main", {"wfdesc:hasSubProcess":step, "prov:label":"Prospective provenance"})

        # TODO: Declare roles/parameters as well


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
            saveTo = os.path.abspath(saveTo)
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
