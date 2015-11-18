import cwltool.avro_ld.schema
import cwltool.avro_ld.makedoc

import sys

with open(sys.argv[1]) as f:
    cwltool.avro_ld.makedoc.avrold_doc([{"name": " ",
                                         "type": "doc",
                                         "doc": f.read().decode("utf-8")}],
                                       sys.stdout)
