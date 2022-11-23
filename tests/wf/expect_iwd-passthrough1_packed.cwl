{
    "class": "CommandLineTool",
    "cwlVersion": "v1.2",
    "doc": "YAML |- syntax does not add trailing newline so in the listing entry\nbelow there is no whitespace surrounding the value\n$(inputs.filelist), so it is evaluated as a File object.  Compare to\niwd-passthrough2.cwl\n",
    "requirements": [
        {
            "listing": [
                {
                    "entryname": "renamed-filelist.txt",
                    "entry": "$(inputs.filelist)"
                }
            ],
            "class": "InitialWorkDirRequirement"
        }
    ],
    "inputs": [
        {
            "type": "File",
            "id": "filelist"
        }
    ],
    "outputs": [
        {
            "type": "File",
            "outputBinding": {
                "glob": "renamed-filelist.txt"
            },
            "id": "filelist"
        }
    ],
    "baseCommand": "true"
}
