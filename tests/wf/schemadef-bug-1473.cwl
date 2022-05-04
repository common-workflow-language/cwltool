{
    "$graph": [
        {
            "class": "ExpressionTool",
            "id": "#flatten-array-fastq-list__1.0.0.cwl",
            "label": "flatten-array-fastq-list-schema v(1.0.0)",
            "doc": "Documentation for flatten-array-fastq-list-schema v1.0.0\n",
            "requirements": [
                {
                    "class": "InlineJavascriptRequirement"
                },
                {
                    "types": [
                        {
                            "type": "record",
                            "name": "#fastq-list-row__1.0.0.yaml/fastq-list-row",
                            "fields": [
                                {
                                    "label": "lane",
                                    "doc": "The lane that the sample was run on\n",
                                    "type": "int",
                                    "name": "#fastq-list-row__1.0.0.yaml/fastq-list-row/lane"
                                },
                                {
                                    "label": "read 1",
                                    "doc": "The path to R1 of a sample\n",
                                    "type": "File",
                                    "streamable": true,
                                    "name": "#fastq-list-row__1.0.0.yaml/fastq-list-row/read_1"
                                },
                                {
                                    "label": "read 2",
                                    "doc": "The path to R2 of a sample\n",
                                    "type": [
                                        "null",
                                        "File"
                                    ],
                                    "streamable": true,
                                    "name": "#fastq-list-row__1.0.0.yaml/fastq-list-row/read_2"
                                },
                                {
                                    "label": "rgid",
                                    "doc": "The read-group id of the sample.\nOften an index\n",
                                    "type": "string",
                                    "name": "#fastq-list-row__1.0.0.yaml/fastq-list-row/rgid"
                                },
                                {
                                    "label": "rglb",
                                    "doc": "The read-group library of the sample.\n",
                                    "type": "string",
                                    "name": "#fastq-list-row__1.0.0.yaml/fastq-list-row/rglb"
                                },
                                {
                                    "label": "rgsm",
                                    "doc": "The read-group sample name\n",
                                    "type": "string",
                                    "name": "#fastq-list-row__1.0.0.yaml/fastq-list-row/rgsm"
                                }
                            ],
                            "id": "#fastq-list-row__1.0.0.yaml"
                        }
                    ],
                    "class": "SchemaDefRequirement"
                }
            ],
            "inputs": [
                {
                    "label": "two dim array",
                    "doc": "two dimensional array with fastq list row\n",
                    "type": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": "#fastq-list-row__1.0.0.yaml/fastq-list-row"
                        }
                    },
                    "inputBinding": {
                        "loadContents": true
                    },
                    "id": "#flatten-array-fastq-list__1.0.0.cwl/arrayTwoDim"
                }
            ],
            "outputs": [
                {
                    "label": "one dim array",
                    "doc": "one dimensional array\n",
                    "type": {
                        "type": "array",
                        "items": "#fastq-list-row__1.0.0.yaml/fastq-list-row"
                    },
                    "id": "#flatten-array-fastq-list__1.0.0.cwl/array1d"
                }
            ],
            "expression": "${\n  var newArray= [];\n  for (var i = 0; i < inputs.arrayTwoDim.length; i++) {\n    for (var k = 0; k < inputs.arrayTwoDim[i].length; k++) {\n      newArray.push((inputs.arrayTwoDim[i])[k]);\n    }\n  }\n  return { 'array1d' : newArray }\n}\n",
            "https://schema.org/author": {
                "class": "https://schema.org/Person",
                "https://schema.org/name": "Sehrish Kanwal",
                "https://schema.org/email": "sehrish.kanwal@umccr.org"
            },
            "$namespaces": {
                "s": "https://schema.org/"
            }
        },
        {
            "class": "ExpressionTool",
            "id": "#get-samplesheet-midfix-regex__1.0.0.cwl",
            "label": "get-samplesheet-midfix-regex v(1.0.0)",
            "doc": "Documentation for get-samplesheet-midfix-regex v1.0.0\n",
            "requirements": [
                {
                    "expressionLib": [
                        "var get_batch_name_from_samplesheet = function(samplesheet_basename) { /* Get everything between SampleSheet and csv https://regex101.com/r/KlF7LW/1 */ var samplesheet_regex = /SampleSheet\\.(\\S+)\\.csv/g; return samplesheet_regex.exec(samplesheet_basename)[1]; }",
                        "var get_batch_names = function(file_objs) { /* For each file object extract the midfix */\n/* Initialise batch names */ var batch_names = [];\nfor (var i = 0; i < file_objs.length; i++){ /* But of that basename, get the midfix */ batch_names.push(get_batch_name_from_samplesheet(file_objs[i].basename)); }\nreturn batch_names; }"
                    ],
                    "class": "InlineJavascriptRequirement"
                }
            ],
            "inputs": [
                {
                    "label": "sample sheets",
                    "doc": "Input samplesheet to extract midfix from\n",
                    "type": {
                        "type": "array",
                        "items": "File"
                    },
                    "id": "#get-samplesheet-midfix-regex__1.0.0.cwl/samplesheets"
                }
            ],
            "outputs": [
                {
                    "label": "output batch names",
                    "doc": "List of output batch names\n",
                    "type": {
                        "type": "array",
                        "items": "string"
                    },
                    "id": "#get-samplesheet-midfix-regex__1.0.0.cwl/batch_names"
                }
            ],
            "expression": "${\n  return {\"batch_names\": get_batch_names(inputs.samplesheets)};\n}",
            "https://schema.org/author": {
                "class": "https://schema.org/Person",
                "https://schema.org/name": "Sehrish Kanwal",
                "https://schema.org/email": "sehrish.kanwal@umccr.org"
            }
        },
        {
            "class": "CommandLineTool",
            "id": "#bclConvert__3.7.5.cwl",
            "label": "bclConvert v(3.7.5)",
            "doc": "Runs the BCL Convert application off standard architecture\n",
            "hints": [
                {
                    "dockerPull": "docker.io/umccr/bcl-convert:3.7.5",
                    "class": "DockerRequirement"
                },
                {
                    "coresMin": 72,
                    "ramMin": 64000,
                    "class": "ResourceRequirement",
                    "http://platform.illumina.com/rdf/ica/resources": {
                        "type": "standardHiCpu",
                        "size": "large"
                    }
                }
            ],
            "requirements": [
                {
                    "listing": [
                        {
                            "entryname": "scripts/run_bclconvert.sh",
                            "entry": "#!/usr/bin/bash\n\n# Fail on non-zero exit code\nset -euo pipefail\n\n# Run bcl-convert with input parameters\neval bcl-convert '\"\\${@}\"'\n\n# Delete undetermined indices\nif [[ \"$(inputs.delete_undetermined_indices)\" == \"true\" ]]; then\n  echo \"Deleting undetermined indices\" 1>&2\n  find \"$(inputs.output_directory)\" -mindepth 1 -maxdepth 1 -name 'Undetermined_S0_*' -exec rm {} \\\\;\nfi\n"
                        }
                    ],
                    "class": "InitialWorkDirRequirement"
                },
                {
                    "class": "InlineJavascriptRequirement"
                },
                {
                    "types": [
                        {
                            "$import": "#fastq-list-row__1.0.0.yaml"
                        }
                    ],
                    "class": "SchemaDefRequirement"
                }
            ],
            "baseCommand": [
                "bash"
            ],
            "arguments": [
                {
                    "position": -1,
                    "valueFrom": "scripts/run_bclconvert.sh"
                }
            ],
            "inputs": [
                {
                    "label": "bcl conversion threads",
                    "doc": "Specifies number of threads used for conversion per tile.\nMust be between 1 and available hardware threads,\ninclusive.\n",
                    "type": [
                        "null",
                        "int"
                    ],
                    "inputBinding": {
                        "prefix": "--bcl-conversion-threads"
                    },
                    "id": "#bclConvert__3.7.5.cwl/bcl_conversion_threads"
                },
                {
                    "label": "bcl input directory",
                    "doc": "A main command-line option that indicates the path to the run\nfolder directory\n",
                    "type": "Directory",
                    "inputBinding": {
                        "prefix": "--bcl-input-directory"
                    },
                    "id": "#bclConvert__3.7.5.cwl/bcl_input_directory"
                },
                {
                    "label": "bcl num compression threads",
                    "doc": "Specifies number of CPU threads used for compression of\noutput FASTQ files. Must be between 1 and available\nhardware threads, inclusive.\n",
                    "type": [
                        "null",
                        "int"
                    ],
                    "inputBinding": {
                        "prefix": "--bcl-num-compression-threads"
                    },
                    "id": "#bclConvert__3.7.5.cwl/bcl_num_compression_threads"
                },
                {
                    "label": "bcl num decompression threads",
                    "doc": "Specifies number of CPU threads used for decompression\nof input base call files. Must be between 1 and available\nhardware threads, inclusive.\n",
                    "type": [
                        "null",
                        "int"
                    ],
                    "inputBinding": {
                        "prefix": "--bcl-num-decompression-threads"
                    },
                    "id": "#bclConvert__3.7.5.cwl/bcl_num_decompression_threads"
                },
                {
                    "label": "bcl num parallel tiles",
                    "doc": "Specifies number of tiles being converted to FASTQ files in\nparallel. Must be between 1 and available hardware threads,\ninclusive.\n",
                    "type": [
                        "null",
                        "int"
                    ],
                    "inputBinding": {
                        "prefix": "--bcl-num-parallel-tiles"
                    },
                    "id": "#bclConvert__3.7.5.cwl/bcl_num_parallel_tiles"
                },
                {
                    "label": "convert only one lane",
                    "doc": "Convert only the specified lane number. The value must\nbe less than or equal to the number of lanes specified in the\nRunInfo.xml. Must be a single integer value.\n",
                    "type": [
                        "null",
                        "int"
                    ],
                    "inputBinding": {
                        "prefix": "--bcl-only-lane"
                    },
                    "id": "#bclConvert__3.7.5.cwl/bcl_only_lane"
                },
                {
                    "label": "bcl sample project subdirectories",
                    "doc": "true \u2014 Allows creation of Sample_Project subdirectories\nas specified in the sample sheet. This option must be set to true for\nthe Sample_Project column in the data section to be used.\nDefault set to false.\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "inputBinding": {
                        "prefix": "--bcl-sampleproject-subdirectories",
                        "valueFrom": "$(self.toString())"
                    },
                    "id": "#bclConvert__3.7.5.cwl/bcl_sampleproject_subdirectories"
                },
                {
                    "label": "delete undetermined indices",
                    "doc": "Delete undetermined indices on completion of the run\nDefault: false\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "id": "#bclConvert__3.7.5.cwl/delete_undetermined_indices"
                },
                {
                    "label": "first tile only",
                    "doc": "true \u2014 Only process the first tile of the first swath of the\ntop surface of each lane specified in the sample sheet.\nfalse \u2014 Process all tiles in each lane, as specified in the sample\nsheet. Default is false\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "inputBinding": {
                        "prefix": "--first-tile-only",
                        "valueFrom": "$(self.toString())"
                    },
                    "id": "#bclConvert__3.7.5.cwl/first_tile_only"
                },
                {
                    "label": "force",
                    "doc": "Allow for the directory specified by the --output-directory\noption to already exist. Default is false\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "inputBinding": {
                        "prefix": "--force"
                    },
                    "id": "#bclConvert__3.7.5.cwl/force"
                },
                {
                    "label": "output directory",
                    "doc": "A required command-line option that indicates the path to\ndemultuplexed fastq output. The directory must not exist, unless -f,\nforce is specified\n",
                    "type": "string",
                    "inputBinding": {
                        "prefix": "--output-directory"
                    },
                    "id": "#bclConvert__3.7.5.cwl/output_directory"
                },
                {
                    "label": "sample sheet",
                    "doc": "Indicates the path to the sample sheet to specify the\nsample sheet location and name, if different from the default.\n",
                    "type": [
                        "null",
                        "File"
                    ],
                    "inputBinding": {
                        "prefix": "--sample-sheet"
                    },
                    "id": "#bclConvert__3.7.5.cwl/samplesheet"
                },
                {
                    "label": "shared thread odirect output",
                    "doc": "Uses experimental shared-thread file output code, which\nrequires O_DIRECT mode. Must be true or false.\nThis file output method is optimized for sample counts\ngreater than 100,000. It is not recommended for lower\nsample counts or using a distributed file system target such\nas GPFS or Lustre. Default is false\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "inputBinding": {
                        "prefix": "--shared-thread-odirect-output"
                    },
                    "id": "#bclConvert__3.7.5.cwl/shared_thread_odirect_output"
                },
                {
                    "label": "strict mode",
                    "doc": "true \u2014 Abort the program if any filter, locs, bcl, or bci lane\nfiles are missing or corrupt.\nfalse \u2014 Continue processing if any filter, locs, bcl, or bci lane files\nare missing. Return a warning message for each missing or corrupt\nfile.\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "inputBinding": {
                        "prefix": "--strict-mode",
                        "valueFrom": "$(self.toString())"
                    },
                    "id": "#bclConvert__3.7.5.cwl/strict_mode"
                }
            ],
            "outputs": [
                {
                    "label": "bcl convert directory output",
                    "doc": "Output directory containing the fastq files, reports and stats\n",
                    "type": "Directory",
                    "outputBinding": {
                        "glob": "$(inputs.output_directory)"
                    },
                    "id": "#bclConvert__3.7.5.cwl/bcl_convert_directory_output"
                },
                {
                    "label": "fastq list rows",
                    "doc": "This schema contains the following inputs:\n* rgid: The id of the sample\n* rgsm: The name of the sample\n* rglb: The library of the sample\n* lane: The lane of the sample\n* read_1: The read 1 File of the sample\n* read_2: The read 2 File of the sample (optional)\n",
                    "type": {
                        "type": "array",
                        "items": "#fastq-list-row__1.0.0.yaml/fastq-list-row"
                    },
                    "outputBinding": {
                        "glob": "$(inputs.output_directory)/Reports/fastq_list.csv",
                        "loadContents": true,
                        "outputEval": "${\n    /*\n    Load inputs initialise output variables\n    */\n    var output_array = [];\n    var lines = self[0].contents.split(\"\\n\")\n\n    /*\n    Generate output object by iterating through fastq_list csv\n    */\n    for (var i=0; i < lines.length - 1; i++){\n        /*\n        First line is a header row skip it\n        */\n        if (i === 0){\n          continue;\n        }\n\n        /*\n        Split row and collect corresponding file paths\n        */\n        var rgid = lines[i].split(\",\")[0];\n        var rgsm = lines[i].split(\",\")[1];\n        var rglb = lines[i].split(\",\")[2];\n        var lane = parseInt(lines[i].split(\",\")[3]);\n        var read_1_path = lines[i].split(\",\")[4];\n        var read_2_path = lines[i].split(\",\")[5];\n\n        /*\n        Initialise the output row as a dict\n        */\n        var output_fastq_list_row = {\n                                      \"rgid\": rgid,\n                                      \"rglb\": rglb,\n                                      \"rgsm\": rgsm,\n                                      \"lane\": lane,\n                                      \"read_1\": {\n                                        \"class\": \"File\",\n                                        \"path\": read_1_path\n                                      },\n        }\n\n\n        if (read_2_path !== \"\"){\n          /*\n          read 2 path exists\n          */\n          output_fastq_list_row[\"read_2\"] = {\n            \"class\": \"File\",\n            \"path\": read_2_path\n          }\n        }\n\n        /*\n        Append object to output array\n        */\n        output_array.push(output_fastq_list_row);\n    }\n    return output_array;\n}\n"
                    },
                    "id": "#bclConvert__3.7.5.cwl/fastq_list_rows"
                }
            ],
            "successCodes": [
                0
            ],
            "https://schema.org/author": {
                "class": "https://schema.org/Person",
                "https://schema.org/name": "Sehrish Kanwal",
                "https://schema.org/email": "sehrish.kanwal@umccr.org"
            }
        },
        {
            "class": "CommandLineTool",
            "id": "#custom-samplesheet-split-by-settings__1.0.0.cwl",
            "label": "custom-samplesheet-split-by-settings v(1.0.0)",
            "doc": "Use before running bcl-convert workflow to ensure that the bclConvert workflow can run in parallel.\nSamples will be split into separate samplesheets based on their cycles specification\n",
            "hints": [
                {
                    "dockerPull": "docker.io/umccr/alpine_pandas:latest-cwl",
                    "class": "DockerRequirement"
                },
                {
                    "class": "ResourceRequirement",
                    "http://platform.illumina.com/rdf/ica/resources": {
                        "tier": "standard",
                        "type": "standard",
                        "size": "small",
                        "coresMin": 2,
                        "ramMin": 4000
                    }
                }
            ],
            "requirements": [
                {
                    "listing": [
                        {
                            "entryname": "samplesheet-by-settings.py",
                            "entry": "#!/usr/bin/env python3\n\n\"\"\"\nTake in a samplesheet,\nLook through headers, rename as necessary\nLook through samples, update settings logic as necessary\nSplit samplesheet out into separate settings files\nWrite to separate files\nIf --samplesheet-format is set to v2 then:\n* rename Settings.Adapter to Settings.AdapterRead1\n* Reduce Data to the columns Lane, Sample_ID, index, index2, Sample_Project\n* Add FileFormatVersion=2 to Header\n* Convert Reads from list to dict with Read1Cycles and Read2Cycles as keys\n\"\"\"\n\n# Imports\nimport re\nimport os\nimport pandas as pd\nimport numpy as np\nimport logging\nimport argparse\nfrom pathlib import Path\nimport sys\nfrom copy import deepcopy\nimport json\n\n# Set logging level\nlogging.basicConfig(level=logging.DEBUG)\n\n# Globals\nSAMPLESHEET_HEADER_REGEX = r\"^\\[(\\S+)\\](,+)?\"  # https://regex101.com/r/5nbe9I/1\nV2_SAMPLESHEET_HEADER_VALUES = {\"Data\": \"BCLConvert_Data\",\n                                \"Settings\": \"BCLConvert_Settings\"}\nV2_FILE_FORMAT_VERSION = \"2\"\nV2_DEFAULT_INSTRUMENT_TYPE = \"NovaSeq 6000\"\n\n\ndef get_args():\n    \"\"\"\n    Get arguments for the command\n    \"\"\"\n    parser = argparse.ArgumentParser(description=\"Create samplesheets based on settings inputs.\"\n                                                 \"Expects a v1 samplesheet as input and settings by samples\"\n                                                 \"as inputs through separated jsonised strings / arrays\")\n\n    # Arguments\n    parser.add_argument(\"--samplesheet-csv\", required=True,\n                        help=\"Path to v1 samplesheet csv\")\n    parser.add_argument(\"--out-dir\", required=False,\n                        help=\"Output directory for samplesheets, set to cwd if not specified\")\n    parser.add_argument(\"--settings-by-samples\", action=\"append\", nargs='*', required=False,\n                        default=[],\n                        help=\"Settings logic for each sample\")\n    parser.add_argument(\"--ignore-missing-samples\", required=False,\n                        default=False, action=\"store_true\",\n                        help=\"If not set, error if samples in the samplesheet are not present in --settings-by-samples arg\")\n    parser.add_argument(\"--samplesheet-format\", required=False,\n                        choices=[\"v1\", \"v2\"], default=\"v1\",\n                        help=\"Type of samplesheet we wish to output\")\n\n    return parser.parse_args()\n\n\ndef set_args(args):\n    \"\"\"\n    Convert --settings-by-samples to dict\n    :return:\n    \"\"\"\n\n    # Get user args\n    samplesheet_csv_arg = getattr(args, \"samplesheet_csv\", None)\n    outdir_arg = getattr(args, \"out_dir\", None)\n    settings_by_samples_arg = getattr(args, \"settings_by_samples\", [])\n\n    # Convert samplesheet csv to path\n    samplesheet_csv_path = Path(samplesheet_csv_arg)\n    # Check its a file\n    if not samplesheet_csv_path.is_file():\n        logging.error(\"Could not find file {}\".format(samplesheet_csv_path))\n        sys.exit(1)\n    # Set attribute as Path object\n    setattr(args, \"samplesheet_csv\", samplesheet_csv_path)\n\n    # Checking the output path\n    if outdir_arg is None:\n        outdir_arg = os.getcwd()\n    outdir_path = Path(outdir_arg)\n    if not outdir_path.parent.is_dir():\n        logging.error(\"Could not create --out-dir, make sure parents exist. Exiting\")\n        sys.exit(1)\n    elif not outdir_path.is_dir():\n        outdir_path.mkdir(parents=False)\n    setattr(args, \"out_dir\", outdir_path)\n\n    # Load json lists\n    settings_by_samples_list = []\n    for settings_by_samples in settings_by_samples_arg:\n        settings_by_samples_list.append(json.loads(settings_by_samples[0]))\n\n    # Set attr as dicts grouped by each batch_name\n    settings_by_batch_names = {}\n    for settings_by_samples in settings_by_samples_list:\n        # Initialise batch name\n        batch_name_key = settings_by_samples.get(\"batch_name\")\n        settings_by_batch_names[batch_name_key] = {}\n        # Add in sample ids\n        settings_by_batch_names[batch_name_key][\"samples\"] = settings_by_samples.get(\"samples\")\n        # Add in settings\n        settings_by_batch_names[batch_name_key][\"settings\"] = settings_by_samples.get(\"settings\")\n\n    # Write attributes back to args dict\n    setattr(args, \"settings_by_batch_names\", settings_by_batch_names)\n\n    # Return args\n    return args\n\n\ndef read_samplesheet_csv(samplesheet_csv_path):\n    \"\"\"\n    Read the samplesheet like a dodgy INI parser\n    :param samplesheet_csv_path:\n    :return:\n    \"\"\"\n    with open(samplesheet_csv_path, \"r\") as samplesheet_csv_h:\n        # Read samplesheet in\n        sample_sheet_sections = {}\n        current_section = None\n        current_section_item_list = []\n        header_match_regex = re.compile(SAMPLESHEET_HEADER_REGEX)\n\n        for line in samplesheet_csv_h.readlines():\n            # Check if blank line\n            if line.strip().rstrip(\",\") == \"\":\n                continue\n            # Check if the current line is a header\n            header_match_obj = header_match_regex.match(line.strip())\n            if header_match_obj is not None and current_section is None:\n                # First line, don't need to write out previous section to obj\n                # Set current section to first group\n                current_section = header_match_obj.group(1)\n                current_section_item_list = []\n            elif header_match_obj is not None and current_section is not None:\n                # A header further down, write out previous section and then reset sections\n                sample_sheet_sections[current_section] = current_section_item_list\n                # Now reset sections\n                current_section = header_match_obj.group(1)\n                current_section_item_list = []\n            # Make sure the first line is a section\n            elif current_section is None and header_match_obj is None:\n                logging.error(\"Top line of csv was not a section header. Exiting\")\n                sys.exit(1)\n            else:  # We're in a section\n                if not current_section == \"Data\":\n                    # Strip trailing slashes from line\n                    current_section_item_list.append(line.strip().rstrip(\",\"))\n                else:\n                    # Don't strip trailing slashes from line\n                    current_section_item_list.append(line.strip())\n\n        # Write out the last section\n        sample_sheet_sections[current_section] = current_section_item_list\n\n        return sample_sheet_sections\n\n\ndef configure_samplesheet_obj(sample_sheet_obj):\n    \"\"\"\n    Each section of the samplesheet obj is in a ',' delimiter ini format\n    Except for [Reads] which is just a list\n    And [Data] which is a dataframe\n    :param sample_sheet_obj:\n    :return:\n    \"\"\"\n\n    for section_name, section_str_list in sample_sheet_obj.items():\n        if section_name == \"Data\":\n            # Convert to dataframe\n            sample_sheet_obj[section_name] = pd.DataFrame(columns=section_str_list[0].split(\",\"),\n                                                          data=[row.split(\",\") for row in\n                                                                section_str_list[1:]])\n        elif section_name == \"Reads\":\n            # Keep as a list\n            continue\n        else:\n            # Convert to dict\n            sample_sheet_obj[section_name] = {line.split(\",\", 1)[0]: line.split(\",\", 1)[-1]\n                                              for line in section_str_list\n                                              if not line.split(\",\", 1)[0] == \"\"}\n            # Check all values are non empty\n            for key, value in sample_sheet_obj[section_name].items():\n                if value == \"\" or value.startswith(\",\"):\n                    logging.error(\"Could not parse key \\\"{}\\\" in section \\\"{}\\\"\".format(key, section_name))\n                    logging.error(\"Value retrieved was \\\"{}\\\"\".format(value))\n                    sys.exit(1)\n\n    return sample_sheet_obj\n\n\ndef lower_under_score_to_camel_case(string):\n    \"\"\"\n    Quick script to update a string from \"this_type\" to \"ThisType\"\n    Necessary for the bclconvert settings to be in camel case\n    Parameters\n    ----------\n    string\n    Returns\n    -------\n    \"\"\"\n\n    camel_case_string_list = []\n    words_list = string.split(\"_\")\n\n    for word in words_list:\n        camel_case_string_list.append(word.title())\n\n    return \"\".join(map(str, camel_case_string_list))\n\n\ndef strip_ns_from_indexes(samplesheetobj_data_df):\n    \"\"\"\n    Strip Ns from the end of the index and index2 headers\n    :param samplesheetobj_data_df:\n    :return:\n    \"\"\"\n\n    samplesheetobj_data_df['index'] = samplesheetobj_data_df['index'].apply(lambda x: x.rstrip(\"N\"))\n    if 'index2' in samplesheetobj_data_df.columns.tolist():\n        samplesheetobj_data_df['index2'] = samplesheetobj_data_df['index2'].apply(lambda x: x.rstrip(\"N\"))\n        samplesheetobj_data_df['index2'] = samplesheetobj_data_df['index2'].replace(\"\", np.nan)\n\n    return samplesheetobj_data_df\n\n\ndef rename_settings_and_data_headers_v2(samplesheet_obj):\n    \"\"\"\n    :return:\n    \"\"\"\n\n    for v1_key, v2_key in V2_SAMPLESHEET_HEADER_VALUES.items():\n        if v1_key in samplesheet_obj.keys():\n            samplesheet_obj[v2_key] = samplesheet_obj.pop(v1_key)\n\n    return samplesheet_obj\n\n\ndef add_file_format_version_v2(samplesheet_header):\n    \"\"\"\n    Add FileFormatVersion key pair to samplesheet header for v2 samplesheet\n    :param samplesheet_header:\n    :return:\n    \"\"\"\n\n    samplesheet_header['FileFormatVersion'] = V2_FILE_FORMAT_VERSION\n\n    return samplesheet_header\n\n\ndef set_instrument_type(samplesheet_header):\n    \"\"\"\n    Fix InstrumentType if it's not specified\n    :param samplesheet_header:\n    :return:\n    \"\"\"\n\n    if \"InstrumentType\" not in samplesheet_header.keys():\n        samplesheet_header[\"InstrumentType\"] = V2_DEFAULT_INSTRUMENT_TYPE\n\n    return samplesheet_header\n\n\ndef update_settings_v2(samplesheet_settings):\n    \"\"\"\n    Convert Adapter To AdapterRead1 for v2 samplesheet\n    :param samplesheet_settings:\n    :return:\n    \"\"\"\n\n    # Rename Adapter to AdapterRead1\n    if \"Adapter\" in samplesheet_settings.keys() and not \"AdapterRead1\" in samplesheet_settings.keys():\n        samplesheet_settings[\"AdapterRead1\"] = samplesheet_settings.pop(\"Adapter\")\n    elif \"Adapter\" in samplesheet_settings.keys() and \"AdapterRead1\" in samplesheet_settings.keys():\n        _ = samplesheet_settings.pop(\"Adapter\")\n\n    # Drop any settings where settings are \"\" - needed for \"AdapterRead2\"\n    samplesheet_settings = {\n                             key: val\n                             for key, val in samplesheet_settings.items()\n                             if not val == \"\"\n                           }\n    return samplesheet_settings\n\n\ndef truncate_data_columns_v2(samplesheet_data_df):\n    \"\"\"\n    Truncate data columns to v2 columns\n    Lane,Sample_ID,index,index2,Sample_Project\n    :param samplesheet_data_df:\n    :return:\n    \"\"\"\n\n    v2_columns = [\"Lane\", \"Sample_ID\", \"index\", \"index2\", \"Sample_Project\"]\n    samplesheet_data_df = samplesheet_data_df.filter(items=v2_columns)\n\n    return samplesheet_data_df\n\n\ndef convert_reads_from_list_to_dict_v2(samplesheet_reads):\n    \"\"\"\n    Convert Reads from a list to a dict format\n    :param samplesheet_reads:\n    :return:\n    \"\"\"\n\n    samplesheet_reads = {\"Read{}Cycles\".format(i + 1): rnum for i, rnum in enumerate(samplesheet_reads)}\n\n    return samplesheet_reads\n\n\ndef convert_samplesheet_to_v2(samplesheet_obj):\n    \"\"\"\n    Runs through necessary steps to convert object to v2 samplesheet\n    :param samplesheet_obj:\n    :return:\n    \"\"\"\n    samplesheet_obj[\"Header\"] = add_file_format_version_v2(samplesheet_obj[\"Header\"])\n    samplesheet_obj[\"Header\"] = set_instrument_type(samplesheet_obj[\"Header\"])\n    samplesheet_obj[\"Settings\"] = update_settings_v2(samplesheet_obj[\"Settings\"])\n    samplesheet_obj[\"Data\"] = truncate_data_columns_v2(samplesheet_obj[\"Data\"])\n    samplesheet_obj[\"Reads\"] = convert_reads_from_list_to_dict_v2(samplesheet_obj[\"Reads\"])\n    samplesheet_obj = rename_settings_and_data_headers_v2(samplesheet_obj)\n\n    return samplesheet_obj\n\n\ndef check_samples(samplesheet_obj, settings_by_samples, ignore_missing_samples=False):\n    \"\"\"\n    If settings_by_samples is defined, ensure that each sample is present\n    \"\"\"\n    all_samples_in_samplesheet = samplesheet_obj[\"Data\"][\"Sample_ID\"].tolist()\n    popped_samples = []\n\n    if len(settings_by_samples.keys()) == 0:\n        # No problem as we're not splitting samples by sample sheet\n        return\n\n    for batch_name, batch_settings_and_samples_dict in settings_by_samples.items():\n        samples = batch_settings_and_samples_dict.get(\"samples\")\n        for sample in samples:\n            if sample in popped_samples:\n                logging.error(\"Sample \\\"{}\\\" registered multiple times\".format(sample))\n                sys.exit(1)\n            elif sample not in all_samples_in_samplesheet:\n                logging.error(\"Could not find sample \\\"{}\\\"\".format(sample))\n                sys.exit(1)\n            else:\n                popped_samples.append(all_samples_in_samplesheet.pop(all_samples_in_samplesheet.index(sample)))\n\n    if ignore_missing_samples:\n        # No issue\n        return\n\n    if not len(all_samples_in_samplesheet) == 0:\n        logging.error(\"The following samples have no associated batch name: {}\".format(\n            \", \".join(map(str, [\"\\\"{}\\\"\".format(sample) for sample in all_samples_in_samplesheet]))\n        ))\n        sys.exit(1)\n\n\ndef write_out_samplesheets(samplesheet_obj, out_dir, settings_by_samples,\n                           is_v2=False):\n    \"\"\"\n    Write out samplesheets to each csv file\n    :return:\n    \"\"\"\n\n    if not len(list(settings_by_samples.keys())) == 0:\n        for batch_name, batch_settings_and_samples_dict in settings_by_samples.items():\n            # Get settings\n            settings = batch_settings_and_samples_dict.get(\"settings\")\n            samples = batch_settings_and_samples_dict.get(\"samples\")\n            # Duplicate samplesheet_obj\n            samplesheet_obj_by_settings_copy = deepcopy(samplesheet_obj)\n            # Convert df to csv string\n            samplesheet_obj_by_settings_copy[\"Data\"] = samplesheet_obj_by_settings_copy[\"Data\"].query(\"Sample_ID in @samples\")\n            # Update settings\n            for setting_key, setting_val in settings.items():\n                \"\"\"\n                Update settings\n                \"\"\"\n                if setting_val is None:\n                    # Don't add None var\n                    continue\n                # Update setting value for boolean types\n                if type(setting_val) == bool:\n                    setting_val = 1 if setting_val else 0\n                # Then assign to settings dict\n                samplesheet_obj_by_settings_copy[\"Settings\"][\n                    lower_under_score_to_camel_case(setting_key)] = setting_val\n\n            # Write out config\n            write_samplesheet(samplesheet_obj=samplesheet_obj_by_settings_copy,\n                              output_file=out_dir / \"SampleSheet.{}.csv\".format(batch_name),\n                              is_v2=is_v2)\n\n    else:  # No splitting required\n        write_samplesheet(samplesheet_obj=samplesheet_obj,\n                          output_file=out_dir / \"SampleSheet.csv\",\n                          is_v2=is_v2)\n\n\ndef write_samplesheet(samplesheet_obj, output_file, is_v2):\n    \"\"\"\n    Write out the samplesheet object and a given file\n    :param samplesheet_obj:\n    :param output_file:\n    :param is_v2\n    :return:\n    \"\"\"\n\n    # Rename samplesheet at the last possible moment\n    if is_v2:\n        # Drop index2 if all are \"N/A\"\n        if 'index2' in samplesheet_obj[\"Data\"].columns.tolist() and \\\n                samplesheet_obj[\"Data\"][\"index2\"].isna().all():\n            samplesheet_obj[\"Data\"] = samplesheet_obj[\"Data\"].drop(columns=\"index2\")\n\n        samplesheet_obj = convert_samplesheet_to_v2(samplesheet_obj)\n\n    # Write the output file\n    with open(output_file, 'w') as samplesheet_h:\n        for section, section_values in samplesheet_obj.items():\n            # Write out the section header\n            samplesheet_h.write(\"[{}]\\n\".format(section))\n            # Write out values\n            if type(section_values) == list:  # [Reads] for v1 samplesheets\n                # Write out each item in a new line\n                samplesheet_h.write(\"\\n\".join(section_values))\n            elif type(section_values) == dict:\n                samplesheet_h.write(\"\\n\".join(map(str, [\"{},{}\".format(key, value)\n                                                        for key, value in section_values.items()])))\n            elif type(section_values) == pd.DataFrame:\n                section_values.to_csv(samplesheet_h, index=False, header=True, sep=\",\")\n            # Add new line before the next section\n            samplesheet_h.write(\"\\n\\n\")\n\n\ndef main():\n    # Get args\n    args = get_args()\n\n    # Check / set args\n    logging.info(\"Checking args\")\n    args = set_args(args=args)\n\n    # Read config\n    logging.info(\"Reading samplesheet\")\n    samplesheet_obj = read_samplesheet_csv(samplesheet_csv_path=args.samplesheet_csv)\n\n    # Configure samplesheet\n    logging.info(\"Configuring samplesheet\")\n    samplesheet_obj = configure_samplesheet_obj(samplesheet_obj)\n\n    # Check missing samples\n    logging.info(\"Checking missing samples\")\n    check_samples(samplesheet_obj=samplesheet_obj,\n                  settings_by_samples=getattr(args, \"settings_by_batch_names\", {}),\n                  ignore_missing_samples=args.ignore_missing_samples)\n\n    # Strip Ns from samplesheet indexes\n    logging.info(\"Stripping Ns from indexes\")\n    samplesheet_obj[\"Data\"] = strip_ns_from_indexes(samplesheet_obj[\"Data\"])\n\n    # Write out samplesheets\n    logging.info(\"Writing out samplesheets\")\n    write_out_samplesheets(samplesheet_obj=samplesheet_obj,\n                           out_dir=args.out_dir,\n                           settings_by_samples=getattr(args, \"settings_by_batch_names\", {}),\n                           is_v2=True if args.samplesheet_format == \"v2\" else False)\n\n# Run main script\nif __name__ == \"__main__\":\n    main()\n"
                        }
                    ],
                    "class": "InitialWorkDirRequirement"
                },
                {
                    "class": "InlineJavascriptRequirement"
                },
                {
                    "types": [
                        {
                            "type": "record",
                            "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples",
                            "fields": [
                                {
                                    "label": "batch name",
                                    "doc": "The name for this combination of settings and sample ids.\nWill be used as the midfix for the name of the sample sheet.\nWill be used as the output directory in the bclconvert workflow\n",
                                    "type": "string",
                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/batch_name"
                                },
                                {
                                    "label": "samples",
                                    "doc": "The list of Sample_IDs with these BClConvert settings\n",
                                    "type": {
                                        "type": "array",
                                        "items": "string"
                                    },
                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/samples"
                                },
                                {
                                    "label": "settings by override cylces",
                                    "doc": "Additional bcl convert settings\n",
                                    "type": [
                                        "null",
                                        {
                                            "type": "record",
                                            "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings",
                                            "fields": [
                                                {
                                                    "label": "adapter behavior",
                                                    "doc": "Defines whether the software\nmasks or trims Read 1 and/or\nRead 2 adapter sequence(s).\nWhen AdapterRead1 or\nAdapterRead2 is not specified, this\nsetting cannot be specified.\n\u2022 mask\u2014The software masks the\nidentified Read 1 and/or Read 2\nsequence(s) with N.\n\u2022 trim\u2014The software trims the\nidentified Read 1 and/or Read 2\nsequence(s)\n",
                                                    "type": [
                                                        "null",
                                                        {
                                                            "type": "enum",
                                                            "symbols": [
                                                                "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/adapter_behavior/mask",
                                                                "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/adapter_behavior/trim"
                                                            ]
                                                        }
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/adapter_behavior"
                                                },
                                                {
                                                    "label": "adapter read 1",
                                                    "doc": "The sequence of the Read 1\nadapter to be masked or trimmed.\nTo trim multiple adapters, separate\nthe sequences with a plus sign (+)\nto indicate independent adapters\nthat must be independently\nassessed for masking or trimming\nfor each read.\nAllowed characters: A, T, C, G.\n",
                                                    "type": [
                                                        "null",
                                                        "string"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/adapter_read_1"
                                                },
                                                {
                                                    "label": "adapter read 2",
                                                    "doc": "The sequence of the Read 2\nadapter to be masked or trimmed.\nTo trim multiple adapters, separate\nthe sequences with a plus sign (+)\nto indicate independent adapters\nthat must be independently\nassessed for masking or trimming\nfor each read.\nAllowed characters: A, T, C, G.\n",
                                                    "type": [
                                                        "null",
                                                        "string"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/adapter_read_2"
                                                },
                                                {
                                                    "label": "adapter stringency",
                                                    "doc": "he minimum match rate that\ntriggers masking or trimming. This\nvalue is calculated as MatchCount\n/ (MatchCount+MismatchCount).\nAccepted values are 0.5\u20131. The\ndefault value of 0.9 indicates that\nonly reads with \u2265 90% sequence\nidentity with the adapter are\ntrimmed.\n",
                                                    "type": [
                                                        "null",
                                                        "float"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/adapter_stringency"
                                                },
                                                {
                                                    "label": "barcode mismatches index 1",
                                                    "doc": "The number of mismatches\nallowed for index1. Accepted\nvalues are 0, 1, or 2.\n",
                                                    "type": [
                                                        "null",
                                                        "int"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/barcode_mismatches_index_1"
                                                },
                                                {
                                                    "label": "barcode mismatches index 2",
                                                    "doc": "The number of mismatches\nallowed for index2. Accepted\nvalues are 0, 1, or 2.\n",
                                                    "type": [
                                                        "null",
                                                        "int"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/barcode_mismatches_index_2"
                                                },
                                                {
                                                    "label": "create fastq for index reads",
                                                    "doc": "Specifies whether software will\noutput fastqs for index reads. If\nindex reads are defined as a\nUMI then fastqs for the UMI will\nbe output (if TrimUMI is also set\nto 0). At least 1 index read must\nbe specified in the sample\nsheet.\n\u2022 0\u2014Fastq files will not be output\nfor index reads.\n\u2022 1\u2014Fastq files will be output for\nfastq reads.\n",
                                                    "type": [
                                                        "null",
                                                        "boolean"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/create_fastq_for_index_reads"
                                                },
                                                {
                                                    "label": "mask short reads",
                                                    "doc": "The minimum read length\ncontaining A, T, C, G values after\nadapter trimming. Reads with\nless than this number of bases\nbecome completely masked. If\nthis value is less than 22, the\ndefault becomes the\nMinimumTrimmedReadLength.\n",
                                                    "type": [
                                                        "null",
                                                        "int"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/mask_short_reads"
                                                },
                                                {
                                                    "label": "minimum adapter overlap",
                                                    "doc": "Do not trim any bases unless the\nadapter matches are greater than\nor equal to the user specified\number of bases. At least one\nAdapterRead1 or\nAdapterRead2 must be specified\nto use\nMinimumAdapterOverlap.\nAllowed characters: 1, 2, 3.\n",
                                                    "type": [
                                                        "null",
                                                        "int"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/minimum_adapter_overlap"
                                                },
                                                {
                                                    "label": "minimum trimmed read length",
                                                    "doc": "The minimum read length after\nadapter trimming. The software\ntrims adapter sequences from\nreads to the value of this\nparameter. Bases below the\nspecified value are masked with\nN.\n",
                                                    "type": [
                                                        "null",
                                                        "int"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/minimum_trimmed_read_length"
                                                },
                                                {
                                                    "label": "override cycles",
                                                    "doc": "Specifies the sequencing and\nindexing cycles that should be\nused when processing the data.\nThe following format must be\nused:\n* Must be same number of\nsemicolon delimited fields in\nstring as sequencing and\nindexing reads specified in\nRunInfo.xml\n* Indexing reads are specified\nwith an I.\n* Sequencing reads are specified\nwith a Y. UMI cycles are\nspecified with an U.\n* Trimmed reads are specified\nwith N.\n* The number of cycles specified\nfor each read must sum to the\number of cycles specified for\nthat read in the RunInfo.xml.\n* Only one Y or I sequence can\nbe specified per read.\nExample: Y151;I8;I8;Y151\n",
                                                    "type": [
                                                        "null",
                                                        "string"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/override_cycles"
                                                },
                                                {
                                                    "label": "trim umi",
                                                    "doc": "Specifies whether UMI cycles\nwill be excluded from fastq files.\nAt least one UMI is required to\nbe specified in the Sample\nSheet when this setting is\nprovided.\n\u2022 0\u2014UMI cycles will be output to\nfastq files.\n\u2022 1\u2014 UMI cycles will not be\noutput to fastq files.\n",
                                                    "type": [
                                                        "null",
                                                        "boolean"
                                                    ],
                                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings/settings/trim_umi"
                                                }
                                            ]
                                        }
                                    ],
                                    "name": "#settings-by-samples__1.0.0.yaml/settings-by-samples/settings"
                                }
                            ],
                            "id": "#settings-by-samples__1.0.0.yaml"
                        }
                    ],
                    "class": "SchemaDefRequirement"
                }
            ],
            "baseCommand": [
                "python3",
                "samplesheet-by-settings.py"
            ],
            "inputs": [
                {
                    "label": "ignore missing samples",
                    "doc": "Don't raise an error if samples from the override cycles list are missing. Just remove them\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "inputBinding": {
                        "prefix": "--ignore-missing-samples"
                    },
                    "id": "#custom-samplesheet-split-by-settings__1.0.0.cwl/ignore_missing_samples"
                },
                {
                    "label": "out dir",
                    "doc": "Where to place the output samplesheet csv files\n",
                    "type": [
                        "null",
                        "string"
                    ],
                    "inputBinding": {
                        "prefix": "--out-dir"
                    },
                    "default": "samplesheets-by-override-cycles",
                    "id": "#custom-samplesheet-split-by-settings__1.0.0.cwl/out_dir"
                },
                {
                    "label": "samplesheet csv",
                    "doc": "The path to the original samplesheet csv file\n",
                    "type": "File",
                    "inputBinding": {
                        "prefix": "--samplesheet-csv"
                    },
                    "id": "#custom-samplesheet-split-by-settings__1.0.0.cwl/samplesheet_csv"
                },
                {
                    "label": "samplesheet format",
                    "type": [
                        "null",
                        {
                            "type": "enum",
                            "symbols": [
                                "#custom-samplesheet-split-by-settings__1.0.0.cwl/samplesheet_format/v1",
                                "#custom-samplesheet-split-by-settings__1.0.0.cwl/samplesheet_format/v2"
                            ]
                        }
                    ],
                    "doc": "Set samplesheet to be in v1 or v2 format\n",
                    "inputBinding": {
                        "prefix": "--samplesheet-format"
                    },
                    "id": "#custom-samplesheet-split-by-settings__1.0.0.cwl/samplesheet_format"
                },
                {
                    "label": "settings by samples",
                    "doc": "Takes in an object form of settings by samples. This is used to split samplesheets\n",
                    "type": [
                        "null",
                        {
                            "type": "array",
                            "items": "#settings-by-samples__1.0.0.yaml/settings-by-samples",
                            "inputBinding": {
                                "prefix": "--settings-by-samples=",
                                "separate": false,
                                "valueFrom": "${\n  /*\n  Format is {\"batch_name\": \"WGS\", \"sample_ids\":[\"S1\", \"S2\", \"S3\"], \"settings\":{\"adapter_read_1\":\"foo\", \"setting_2\":\"bar\"}}\n  Although BCLConvert settings are in camel-case, we have settings in lower case, with underscore separation instead\n  Settings are translated to camel case in the workflow. adapter_read_1 becomes AdapterRead1\n  */\n  return JSON.stringify(self);\n}\n"
                            }
                        }
                    ],
                    "inputBinding": {
                        "position": 1
                    },
                    "id": "#custom-samplesheet-split-by-settings__1.0.0.cwl/settings_by_samples"
                }
            ],
            "outputs": [
                {
                    "label": "samplesheets outdir",
                    "doc": "Directory of samplesheets\n",
                    "type": "Directory",
                    "outputBinding": {
                        "glob": "$(inputs.out_dir)"
                    },
                    "id": "#custom-samplesheet-split-by-settings__1.0.0.cwl/samplesheet_outdir"
                },
                {
                    "label": "output samplesheets",
                    "doc": "List of output samplesheets\n",
                    "type": {
                        "type": "array",
                        "items": "File"
                    },
                    "outputBinding": {
                        "glob": "$(inputs.out_dir)/*.csv"
                    },
                    "id": "#custom-samplesheet-split-by-settings__1.0.0.cwl/samplesheets"
                }
            ],
            "successCodes": [
                0
            ],
            "https://schema.org/author": {
                "class": "https://schema.org/Person",
                "https://schema.org/name": "Sehrish Kanwal",
                "https://schema.org/email": "sehrish.kanwal@umccr.org"
            }
        },
        {
            "class": "CommandLineTool",
            "id": "#custom-touch-file__1.0.0.cwl",
            "label": "custom-create-dummy-file v(1.0.0)",
            "doc": "Documentation for custom-create-dummy-file v1.0.0\n",
            "hints": [
                {
                    "dockerPull": "docker.io/alpine:latest",
                    "class": "DockerRequirement"
                },
                {
                    "coresMin": 1,
                    "ramMin": 1000,
                    "class": "ResourceRequirement",
                    "http://platform.illumina.com/rdf/ica/resources": {
                        "tier": "standard",
                        "type": "standard",
                        "size": "small"
                    }
                }
            ],
            "requirements": [
                {
                    "class": "InlineJavascriptRequirement"
                }
            ],
            "baseCommand": [
                "touch"
            ],
            "inputs": [
                {
                    "label": "file name",
                    "doc": "Name of the file to create\n",
                    "type": "string",
                    "default": "dummy_file.txt",
                    "inputBinding": {
                        "position": 1
                    },
                    "id": "#custom-touch-file__1.0.0.cwl/file_name"
                }
            ],
            "outputs": [
                {
                    "label": "dummy file",
                    "doc": "Output dummy file\n",
                    "type": "File",
                    "outputBinding": {
                        "glob": "$(inputs.file_name)"
                    },
                    "id": "#custom-touch-file__1.0.0.cwl/dummy_file_output"
                }
            ],
            "successCodes": [
                0
            ],
            "https://schema.org/author": {
                "class": "https://schema.org/Person",
                "https://schema.org/name": "Alexis Lucattini",
                "https://schema.org/email": "Alexis.Lucattini@umccr.org",
                "https://schema.org/identifier": "https://orcid.org/0000-0001-9754-647X"
            }
        },
        {
            "class": "CommandLineTool",
            "id": "#multiqc-interop__1.2.1.cwl",
            "label": "multiqc-interop v(1.2.1)",
            "doc": "Producing QC report using interop matrix\n",
            "hints": [
                {
                    "dockerPull": "docker.io/umccr/multiqc_dragen:1.2.1",
                    "class": "DockerRequirement"
                },
                {
                    "coresMin": 1,
                    "ramMin": 4000,
                    "class": "ResourceRequirement",
                    "http://platform.illumina.com/rdf/ica/resources": {
                        "type": "standard",
                        "size": "medium"
                    }
                }
            ],
            "requirements": [
                {
                    "listing": [
                        {
                            "entryname": "generate_interop_files.sh",
                            "entry": "#!/usr/bin/env bash\n\n# Fail on non-zero exit of subshell\nset -euo pipefail\n\n# Generate interop files\ninterop_summary --csv=1 \"$(inputs.input_directory.path)\" > interop_summary.csv\ninterop_index-summary --csv=1 \"$(inputs.input_directory.path)\" > interop_index-summary.csv\n"
                        },
                        {
                            "entryname": "run_multiqc_interop.sh",
                            "entry": "#!/usr/bin/env bash\n\n# Fail on non-zero exit of subshell\nset -euo pipefail\n\n# multiqc interop module needs to run a series of commands \n# ref: https://github.com/umccr-illumina/stratus/blob/806c76609af4755159b12cf5302d4e4e11cc614b/TES/multiqc.json\necho \"Generating interop files\" 1>&2\nbash generate_interop_files.sh\n\n# Now run multiqc\necho \"Running multiqc\" 1>&2\neval multiqc --module interop '\"\\${@}\"' interop_summary.csv interop_index-summary.csv\n"
                        }
                    ],
                    "class": "InitialWorkDirRequirement"
                },
                {
                    "class": "InlineJavascriptRequirement"
                }
            ],
            "baseCommand": [
                "bash",
                "run_multiqc_interop.sh"
            ],
            "inputs": [
                {
                    "label": "dummy file",
                    "doc": "testing inputs stream logic\nIf used will set input mode to stream on ICA which\nsaves having to download the entire input folder\n",
                    "type": [
                        "null",
                        "File"
                    ],
                    "streamable": true,
                    "id": "#multiqc-interop__1.2.1.cwl/dummy_file"
                },
                {
                    "label": "input directory",
                    "doc": "The bcl directory\n",
                    "type": "Directory",
                    "inputBinding": {
                        "position": 100
                    },
                    "id": "#multiqc-interop__1.2.1.cwl/input_directory"
                },
                {
                    "label": "output directory",
                    "doc": "The output directory, defaults to \"multiqc-outdir\"\n",
                    "type": [
                        "null",
                        "string"
                    ],
                    "default": "multiqc-outdir",
                    "inputBinding": {
                        "prefix": "--outdir"
                    },
                    "id": "#multiqc-interop__1.2.1.cwl/output_directory_name"
                },
                {
                    "label": "output filename",
                    "doc": "Report filename in html format.\nDefaults to 'multiqc-report.html'\n",
                    "type": [
                        "null",
                        "string"
                    ],
                    "default": "multiqc-report.html",
                    "inputBinding": {
                        "prefix": "--filename"
                    },
                    "id": "#multiqc-interop__1.2.1.cwl/output_filename"
                },
                {
                    "label": "title",
                    "doc": "Report title.\nPrinted as page header, used for filename if not otherwise specified.\n",
                    "type": "string",
                    "inputBinding": {
                        "prefix": "--title"
                    },
                    "id": "#multiqc-interop__1.2.1.cwl/title"
                }
            ],
            "outputs": [
                {
                    "label": "multiqc output",
                    "doc": "output directory with interop multiQC matrices\n",
                    "type": "Directory",
                    "outputBinding": {
                        "glob": "$(inputs.output_directory_name)"
                    },
                    "id": "#multiqc-interop__1.2.1.cwl/interop_multi_qc_out"
                }
            ],
            "successCodes": [
                0
            ],
            "https://schema.org/author": {
                "class": "https://schema.org/Person",
                "https://schema.org/name": "Sehrish Kanwal",
                "https://schema.org/email": "sehrish.kanwal@umccr.org"
            }
        },
        {
            "class": "CommandLineTool",
            "id": "#multiqc__1.11.0.cwl",
            "label": "multiqc v(1.11.0)",
            "doc": "Documentation for multiqc v1.11.0\n",
            "hints": [
                {
                    "dockerPull": "quay.io/biocontainers/multiqc:1.11--pyhdfd78af_0",
                    "class": "DockerRequirement"
                },
                {
                    "coresMin": 2,
                    "ramMin": 4000,
                    "class": "ResourceRequirement",
                    "http://platform.illumina.com/rdf/ica/resources": {
                        "tier": "standard",
                        "type": "standard",
                        "size": "xlarge"
                    }
                }
            ],
            "requirements": [
                {
                    "listing": [
                        {
                            "entryname": "run_multiqc.sh",
                            "entry": "#!/usr/bin/env bash\n\n# Set up to fail\nset -euo pipefail\n\n# Create input dir\nmkdir \"$(get_input_dir())\"\n\n# Create an array of dirs\ninput_dir_path_array=( $(inputs.input_directories.map(function(a) {return '\"' + a.path + '\"';}).join(' ')) )\ninput_dir_basename_array=( $(inputs.input_directories.map(function(a) {return '\"' + a.basename + '\"';}).join(' ')) )\n\n# Iterate through input direcotires\nfor input_dir_path in \"\\${input_dir_path_array[@]}\"; do\n  ln -s \"\\${input_dir_path}\" \"$(get_input_dir())/\"\ndone\n\n# Run multiqc\neval multiqc '\"\\${@}\"'\n\n# Unlink input directories - otherwise ICA tries to upload them onto gds (and fails)\nfor input_dir_basename in \"\\${input_dir_basename_array[@]}\"; do\n  unlink \"$(get_input_dir())/\\${input_dir_basename}\"\ndone\n"
                        }
                    ],
                    "class": "InitialWorkDirRequirement"
                },
                {
                    "expressionLib": [
                        "var get_input_dir = function(){ /* Just returns the name of the input directory */ return \"multiqc_input_dir\"; }"
                    ],
                    "class": "InlineJavascriptRequirement"
                }
            ],
            "baseCommand": [
                "bash",
                "run_multiqc.sh"
            ],
            "arguments": [
                {
                    "position": 100,
                    "valueFrom": "$(get_input_dir())"
                }
            ],
            "inputs": [
                {
                    "label": "cl config",
                    "doc": "Override config from the cli\n",
                    "type": [
                        "null",
                        "string"
                    ],
                    "inputBinding": {
                        "prefix": "--cl_config"
                    },
                    "id": "#multiqc__1.11.0.cwl/cl_config"
                },
                {
                    "label": "comment",
                    "doc": "Custom comment, will be printed at the top of the report.\n",
                    "type": [
                        "null",
                        "string"
                    ],
                    "inputBinding": {
                        "prefix": "--comment"
                    },
                    "id": "#multiqc__1.11.0.cwl/comment"
                },
                {
                    "label": "config",
                    "doc": "Configuration file for bclconvert\n",
                    "type": [
                        "null",
                        "File"
                    ],
                    "streamable": true,
                    "inputBinding": {
                        "prefix": "--config"
                    },
                    "id": "#multiqc__1.11.0.cwl/config"
                },
                {
                    "label": "dummy file",
                    "doc": "testing inputs stream logic\nIf used will set input mode to stream on ICA which\nsaves having to download the entire input folder\n",
                    "type": [
                        "null",
                        "File"
                    ],
                    "streamable": true,
                    "id": "#multiqc__1.11.0.cwl/dummy_file"
                },
                {
                    "label": "input directories",
                    "doc": "The list of directories to place in the analysis\n",
                    "type": {
                        "type": "array",
                        "items": "Directory"
                    },
                    "id": "#multiqc__1.11.0.cwl/input_directories"
                },
                {
                    "label": "output directory",
                    "doc": "The output directory\n",
                    "type": "string",
                    "inputBinding": {
                        "prefix": "--outdir",
                        "valueFrom": "$(runtime.outdir)/$(self)"
                    },
                    "id": "#multiqc__1.11.0.cwl/output_directory_name"
                },
                {
                    "label": "output filename",
                    "doc": "Report filename in html format.\nDefaults to 'multiqc-report.html\"\n",
                    "type": "string",
                    "inputBinding": {
                        "prefix": "--filename"
                    },
                    "id": "#multiqc__1.11.0.cwl/output_filename"
                },
                {
                    "label": "title",
                    "doc": "Report title.\nPrinted as page header, used for filename if not otherwise specified.\n",
                    "type": "string",
                    "inputBinding": {
                        "prefix": "--title"
                    },
                    "id": "#multiqc__1.11.0.cwl/title"
                }
            ],
            "outputs": [
                {
                    "label": "output directory",
                    "doc": "Directory that contains all multiqc analysis data\n",
                    "type": "Directory",
                    "outputBinding": {
                        "glob": "$(inputs.output_directory_name)"
                    },
                    "id": "#multiqc__1.11.0.cwl/output_directory"
                },
                {
                    "label": "output file",
                    "doc": "Output html file\n",
                    "type": "File",
                    "outputBinding": {
                        "glob": "$(inputs.output_directory_name)/$(inputs.output_filename)"
                    },
                    "id": "#multiqc__1.11.0.cwl/output_file"
                }
            ],
            "successCodes": [
                0
            ],
            "https://schema.org/author": {
                "class": "https://schema.org/Person",
                "https://schema.org/name": "Alexis Lucattini",
                "https://schema.org/email": "Alexis.Lucattini@umccr.org",
                "https://schema.org/identifier": "https://orcid.org/0000-0001-9754-647X"
            }
        },
        {
            "class": "Workflow",
            "id": "#main",
            "label": "bcl-conversion v(3.7.5)",
            "doc": "Runs bcl-convert v3.7.5 with multiqc output of the bcl input directory\n",
            "requirements": [
                {
                    "class": "InlineJavascriptRequirement"
                },
                {
                    "class": "MultipleInputFeatureRequirement"
                },
                {
                    "class": "ScatterFeatureRequirement"
                },
                {
                    "types": [
                        {
                            "$import": "#settings-by-samples__1.0.0.yaml"
                        },
                        {
                            "$import": "#fastq-list-row__1.0.0.yaml"
                        }
                    ],
                    "class": "SchemaDefRequirement"
                },
                {
                    "class": "StepInputExpressionRequirement"
                }
            ],
            "inputs": [
                {
                    "label": "bcl input directory",
                    "doc": "Path to the bcl files\n",
                    "type": "Directory",
                    "id": "#bcl_input_directory"
                },
                {
                    "label": "bcl only lane",
                    "doc": "Convert only the specified lane number. The value must\nbe less than or equal to the number of lanes specified in the\nRunInfo.xml. Must be a single integer value.\n",
                    "type": [
                        "null",
                        "int"
                    ],
                    "id": "#bcl_only_lane_bcl_conversion"
                },
                {
                    "label": "bcl sampleproject subdirectories",
                    "doc": "true \u2014 Allows creation of Sample_Project subdirectories\nas specified in the sample sheet. This option must be set to true for\nthe Sample_Project column in the data section to be used.\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "id": "#bcl_sampleproject_subdirectories_bcl_conversion"
                },
                {
                    "label": "delete undetermined indices",
                    "doc": "Delete undetermined indices on completion of the run\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "default": true,
                    "id": "#delete_undetermined_indices_bcl_conversion"
                },
                {
                    "label": "first tile only",
                    "doc": "true \u2014 Only process the first tile of the first swath of the\n  top surface of each lane specified in the sample sheet.\nfalse \u2014 Process all tiles in each lane, as specified in the sample\n  sheet.\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "id": "#first_tile_only_bcl_conversion"
                },
                {
                    "label": "ignore missing samples",
                    "doc": "Remove the samples not present in the override cycles record\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "default": true,
                    "id": "#ignore_missing_samples"
                },
                {
                    "label": "runfolder name",
                    "doc": "Required - used in naming run specific folder, reports and headings\n",
                    "type": "string",
                    "id": "#runfolder_name"
                },
                {
                    "label": "sample sheet",
                    "doc": "The path to the full samplesheet\n",
                    "type": "File",
                    "id": "#samplesheet"
                },
                {
                    "label": "samplesheet outdir",
                    "doc": "Output directory of the samplesheets split by settings\n",
                    "type": [
                        "null",
                        "string"
                    ],
                    "id": "#samplesheet_outdir"
                },
                {
                    "label": "set samplesheet output format",
                    "doc": "Convert headers to v2 samplesheet format\n",
                    "type": [
                        "null",
                        {
                            "type": "enum",
                            "symbols": [
                                "#/samplesheet_output_format/v1",
                                "#/samplesheet_output_format/v2"
                            ]
                        }
                    ],
                    "id": "#samplesheet_output_format"
                },
                {
                    "label": "settings by samples",
                    "doc": "List of settings by samples\n",
                    "type": [
                        "null",
                        {
                            "type": "array",
                            "items": "#settings-by-samples__1.0.0.yaml/settings-by-samples"
                        }
                    ],
                    "id": "#settings_by_samples"
                },
                {
                    "label": "strict mode bcl conversion",
                    "doc": "true \u2014 Abort the program if any filter, locs, bcl, or bci lane\nfiles are missing or corrupt.\nfalse \u2014 Continue processing if any filter, locs, bcl, or bci lane files\nare missing. Return a warning message for each missing or corrupt\nfile.\n",
                    "type": [
                        "null",
                        "boolean"
                    ],
                    "id": "#strict_mode_bcl_conversion"
                }
            ],
            "steps": [
                {
                    "label": "bcl convert",
                    "doc": "BCLConvert is then scattered across each of the samplesheets.\n",
                    "scatter": [
                        "#bcl_convert_step/samplesheet",
                        "#bcl_convert_step/output_directory"
                    ],
                    "scatterMethod": "dotproduct",
                    "in": [
                        {
                            "source": "#bcl_input_directory",
                            "id": "#bcl_convert_step/bcl_input_directory"
                        },
                        {
                            "source": "#bcl_only_lane_bcl_conversion",
                            "id": "#bcl_convert_step/bcl_only_lane"
                        },
                        {
                            "source": "#bcl_sampleproject_subdirectories_bcl_conversion",
                            "id": "#bcl_convert_step/bcl_sampleproject_subdirectories"
                        },
                        {
                            "source": "#delete_undetermined_indices_bcl_conversion",
                            "id": "#bcl_convert_step/delete_undetermined_indices"
                        },
                        {
                            "source": "#first_tile_only_bcl_conversion",
                            "id": "#bcl_convert_step/first_tile_only"
                        },
                        {
                            "source": "#get_batch_dirs/batch_names",
                            "id": "#bcl_convert_step/output_directory"
                        },
                        {
                            "source": "#samplesheet_split_by_settings_step/samplesheets",
                            "id": "#bcl_convert_step/samplesheet"
                        },
                        {
                            "source": "#strict_mode_bcl_conversion",
                            "id": "#bcl_convert_step/strict_mode"
                        }
                    ],
                    "out": [
                        {
                            "id": "#bcl_convert_step/bcl_convert_directory_output"
                        },
                        {
                            "id": "#bcl_convert_step/fastq_list_rows"
                        }
                    ],
                    "run": "#bclConvert__3.7.5.cwl",
                    "id": "#bcl_convert_step"
                },
                {
                    "label": "bclconvert qc step",
                    "doc": "The bclconvert qc step - from scatter this takes in an array of dirs\n",
                    "in": [
                        {
                            "valueFrom": "${\n   return JSON.stringify({\"bclconvert\": { \"genome_size\": \"hg38_genome\" }});\n }\n",
                            "id": "#bclconvert_qc_step/cl_config"
                        },
                        {
                            "source": "#create_dummy_file_step/dummy_file_output",
                            "id": "#bclconvert_qc_step/dummy_file"
                        },
                        {
                            "source": "#bcl_convert_step/bcl_convert_directory_output",
                            "id": "#bclconvert_qc_step/input_directories"
                        },
                        {
                            "source": "#runfolder_name",
                            "valueFrom": "$(self)_bclconvert_multiqc",
                            "id": "#bclconvert_qc_step/output_directory_name"
                        },
                        {
                            "source": "#runfolder_name",
                            "valueFrom": "$(self)_bclconvert_multiqc.html",
                            "id": "#bclconvert_qc_step/output_filename"
                        },
                        {
                            "source": "#runfolder_name",
                            "valueFrom": "UMCCR MultiQC BCLConvert report for $(self)",
                            "id": "#bclconvert_qc_step/title"
                        }
                    ],
                    "out": [
                        {
                            "id": "#bclconvert_qc_step/output_directory"
                        }
                    ],
                    "run": "#multiqc__1.11.0.cwl",
                    "id": "#bclconvert_qc_step"
                },
                {
                    "label": "create dummy file",
                    "doc": "Intermediate step for letting multiqc-interop be placed in stream mode\n",
                    "in": [],
                    "out": [
                        {
                            "id": "#create_dummy_file_step/dummy_file_output"
                        }
                    ],
                    "run": "#custom-touch-file__1.0.0.cwl",
                    "id": "#create_dummy_file_step"
                },
                {
                    "label": "flatten fastq list rows array",
                    "doc": "fastq list rows is an array and bcl convert is from a directory output.\nThis scatters the arrays to a single array\n",
                    "in": [
                        {
                            "source": "#bcl_convert_step/fastq_list_rows",
                            "id": "#flatten_fastq_list_rows_array/arrayTwoDim"
                        }
                    ],
                    "out": [
                        {
                            "id": "#flatten_fastq_list_rows_array/array1d"
                        }
                    ],
                    "run": "#flatten-array-fastq-list__1.0.0.cwl",
                    "id": "#flatten_fastq_list_rows_array"
                },
                {
                    "label": "get batch directories",
                    "doc": "Get the directory names of each of the directories we wish to scatter over\n",
                    "in": [
                        {
                            "source": "#samplesheet_split_by_settings_step/samplesheets",
                            "id": "#get_batch_dirs/samplesheets"
                        }
                    ],
                    "out": [
                        {
                            "id": "#get_batch_dirs/batch_names"
                        }
                    ],
                    "run": "#get-samplesheet-midfix-regex__1.0.0.cwl",
                    "id": "#get_batch_dirs"
                },
                {
                    "label": "interop qc step",
                    "doc": "Run the multiqc by first also generating the interop files for use\n",
                    "in": [
                        {
                            "source": "#create_dummy_file_step/dummy_file_output",
                            "id": "#interop_qc_step/dummy_file"
                        },
                        {
                            "source": "#bcl_input_directory",
                            "id": "#interop_qc_step/input_directory"
                        },
                        {
                            "source": "#runfolder_name",
                            "valueFrom": "$(self)_interop_multiqc",
                            "id": "#interop_qc_step/output_directory_name"
                        },
                        {
                            "source": "#runfolder_name",
                            "valueFrom": "$(self)_interop_multiqc.html",
                            "id": "#interop_qc_step/output_filename"
                        },
                        {
                            "source": "#runfolder_name",
                            "valueFrom": "UMCCR MultiQC Interop report for $(self)",
                            "id": "#interop_qc_step/title"
                        }
                    ],
                    "out": [
                        {
                            "id": "#interop_qc_step/interop_multi_qc_out"
                        }
                    ],
                    "run": "#multiqc-interop__1.2.1.cwl",
                    "id": "#interop_qc_step"
                },
                {
                    "label": "Split samplesheet by settings step",
                    "doc": "Samplesheet is split by the different input types.\nThese are generally a difference in override cycles parameters or adapter trimming settings\nThis then scatters multiple bclconvert workflows split by sample id\n",
                    "in": [
                        {
                            "source": "#ignore_missing_samples",
                            "id": "#samplesheet_split_by_settings_step/ignore_missing_samples"
                        },
                        {
                            "source": "#samplesheet_outdir",
                            "id": "#samplesheet_split_by_settings_step/out_dir"
                        },
                        {
                            "source": "#samplesheet",
                            "id": "#samplesheet_split_by_settings_step/samplesheet_csv"
                        },
                        {
                            "source": "#samplesheet_output_format",
                            "id": "#samplesheet_split_by_settings_step/samplesheet_format"
                        },
                        {
                            "source": "#settings_by_samples",
                            "id": "#samplesheet_split_by_settings_step/settings_by_samples"
                        }
                    ],
                    "out": [
                        {
                            "id": "#samplesheet_split_by_settings_step/samplesheets"
                        },
                        {
                            "id": "#samplesheet_split_by_settings_step/samplesheet_outdir"
                        }
                    ],
                    "run": "#custom-samplesheet-split-by-settings__1.0.0.cwl",
                    "id": "#samplesheet_split_by_settings_step"
                }
            ],
            "outputs": [
                {
                    "label": "bclconvert multiqc",
                    "doc": "multiqc directory output that contains bclconvert multiqc data\n",
                    "type": "Directory",
                    "outputSource": "#bclconvert_qc_step/output_directory",
                    "id": "#bclconvert_multiqc_out"
                },
                {
                    "label": "Output fastq directories",
                    "doc": "The outputs from the bclconvert-step\n",
                    "type": {
                        "type": "array",
                        "items": "Directory"
                    },
                    "outputSource": "#bcl_convert_step/bcl_convert_directory_output",
                    "id": "#fastq_directories"
                },
                {
                    "label": "rows of fastq list csv file",
                    "doc": "Contains the fastq list row schema for each of the output fastq files\n",
                    "type": {
                        "type": "array",
                        "items": "#fastq-list-row__1.0.0.yaml/fastq-list-row"
                    },
                    "outputSource": "#flatten_fastq_list_rows_array/array1d",
                    "id": "#fastq_list_rows"
                },
                {
                    "label": "interop multiqc",
                    "doc": "multiqc directory output that contains interop data\n",
                    "type": "Directory",
                    "outputSource": "#interop_qc_step/interop_multi_qc_out",
                    "id": "#interop_multiqc_out"
                },
                {
                    "label": "split samplesheets",
                    "doc": "List of samplesheets split by override cycles\n",
                    "type": {
                        "type": "array",
                        "items": "File"
                    },
                    "outputSource": "#samplesheet_split_by_settings_step/samplesheets",
                    "id": "#split_sheets"
                },
                {
                    "label": "split sheets dir",
                    "doc": "The directory containing the samplesheets used for each bcl convert\n",
                    "type": "Directory",
                    "outputSource": "#samplesheet_split_by_settings_step/samplesheet_outdir",
                    "id": "#split_sheets_dir"
                }
            ],
            "https://schema.org/author": {
                "class": "https://schema.org/Person",
                "https://schema.org/name": "Sehrish Kanwal",
                "https://schema.org/email": "sehrish.kanwal@umccr.org"
            }
        }
    ],
    "cwlVersion": "v1.1",
    "$schemas": [
        "https://schema.org/version/latest/schemaorg-current-http.rdf"
    ]
}
