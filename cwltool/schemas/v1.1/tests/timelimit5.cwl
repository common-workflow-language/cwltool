class: ExpressionTool
cwlVersion: v1.1
inputs: []
outputs:
  status: string
requirements:
  ToolTimeLimit:
    timelimit: 3
  InlineJavascriptRequirement: {}
expression: |
  ${
    function sleep(milliseconds) {
      var start = new Date().getTime();
      for (var i = 0; i < 1e7; i++) {
        if ((new Date().getTime() - start) > milliseconds){
          break;
        }
      }
    };
    sleep(5000);
    return {"status": "Done"}
  }