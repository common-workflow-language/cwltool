class: CommandLineTool
cwlVersion: v1.1
requirements:
  ShellCommandRequirement: {}
inputs: {}
outputs:
  foo: File
arguments:
  - shellQuote: false
    valueFrom: |
      echo "cow" > "$(runtime.outdir)/foo" &&
      echo "moo" > "$(runtime.tmpdir)/foo" &&
      echo '{"foo": {"path": "$(runtime.outdir)/foo", "class": "File"} }' > cwl.output.json
