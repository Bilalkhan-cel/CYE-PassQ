import json
from datetime import datetime , time

with open("branches.json") as f:
    data=json.load(f)


def reset():
    for branch , info in data.items():
        info['current_tokens']=1 
        with open("branches.json","w") as q:
            json.dump(data,q)

def branch_has_space(location):
    """Read-only: True if this branch can still issue a token today."""
    info = data.get(location)
    return bool(info) and info['current_tokens'] <= info['max_tokens']

def check_location(location):
     for branch , info in data.items():
        if datetime.now().time() < time(19,0):
            if branch==location:
                if info['current_tokens'] <= info['max_tokens']:
                    num=info['current_tokens']
                    info['current_tokens']+=1 
                    with open("branches.json","w") as q:
                        json.dump(data,q)
                        return num
                else:
        
                    return 801  
        else:
            info['current_tokens']=1 
            with open("branches.json","w") as q:
                json.dump(data,q)
                return 0
      



      
    
