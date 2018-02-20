{
    "class": "Workflow", 
    "label": "Hello World", 
    "doc": "Outputs a message using echo", 
    "inputs": [
        {
            "type": "string", 
            "id": "#main/usermessage"
        }
    ], 
    "outputs": [
        {
            "outputSource": "#main/step0/response", 
            "type": "File", 
            "id": "#main/response"
        }
    ], 
    "steps": [
        {
            "run": {
                "class": "CommandLineTool", 
                "inputs": [
                    {
                        "type": "string", 
                        "doc": "The message to print", 
                        "default": "Hello World", 
                        "inputBinding": {
                            "position": 1
                        }, 
                        "id": "#main/step0/9478b38e-60ae-4a32-9866-2ba1153bb1d5/message"
                    }
                ], 
                "baseCommand": "echo", 
                "arguments": [
                    "-n", 
                    "-e"
                ], 
                "stdout": "response.txt", 
                "outputs": [
                    {
                        "type": "File", 
                        "id": "#main/step0/9478b38e-60ae-4a32-9866-2ba1153bb1d5/response", 
                        "outputBinding": {
                            "glob": "response.txt"
                        }
                    }
                ], 
                "id": "#main/step0/9478b38e-60ae-4a32-9866-2ba1153bb1d5"
            }, 
            "in": [
                {
                    "source": "#main/usermessage", 
                    "id": "#main/step0/message"
                }
            ], 
            "out": [
                "#main/step0/response"
            ], 
            "id": "#main/step0"
        }
    ], 
    "id": "#main", 
    "cwlVersion": "v1.0"
}