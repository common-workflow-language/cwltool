{
"cwlVersion": "v1.0",
"class": "CommandLineTool",
"inputs": [
    {
        "type": "File",
        "default": {
            "class": "File",
            "basename": "extract_regions.py",
            "contents": "#!/usr/bin/env python3\n\nfrom __future__ import print_function, division\nimport sys\n\ninput_filename = sys.argv[1]\nif len(sys.argv) == 3:\n    fuzz = int(sys.argv[2])\nelse:\n    fuzz = 0\ninput_file = open(input_filename)\n\ncount = 0\nfor line in input_file:\n    if not line.startswith(\">\"):\n        continue\n    count += 1\n    contig_regions_file = open(\"contig_regions{}.txt\".format(count), \"w\")\n    proteins_list_file = open(\"proteins{}.txt\".format(count), \"w\")\n    fields = line.split(\"|\")\n    protein_id = fields[0][1:]\n    contig_id = fields[1]\n    r_start = int(fields[6])\n    if r_start > fuzz:\n        r_start = r_start - fuzz\n    r_end = int(fields[7]) + fuzz\n    print(\"{}:{}-{}\".format(contig_id, r_start, r_end), file=contig_regions_file)\n    print(protein_id, file=proteins_list_file)\n    contig_regions_file.close()\n    proteins_list_file.close()\n"
        },
        "inputBinding": {
            "position": 1
        },
        "id": "scripts"
    }
],
"outputs": [
],
"baseCommand": "cat"
}
