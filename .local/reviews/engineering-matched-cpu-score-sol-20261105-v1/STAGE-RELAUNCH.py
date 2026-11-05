#!/usr/bin/python3
"""Run on 175: python3 -P STAGE-RELAUNCH.py run1 (or warmup).
Replays the exact saved create/start request only when the retained name is absent.
An existing completed name remains inspectable; it is not removed or reused.
"""
import pathlib,json,socket,http.client,sys
root=pathlib.Path(__file__).resolve().parent
request=json.loads((root/sys.argv[1]/'LAUNCH.json').read_text())
class Unix(http.client.HTTPConnection):
 def connect(self):
  self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.connect('/var/run/docker.sock')
def api(path,obj=None):
 c=Unix('localhost',timeout=50);c.request('POST','/v1.44'+path,json.dumps(obj) if obj is not None else None,{'Content-Type':'application/json'});r=c.getresponse();b=r.read();c.close()
 if r.status>=400:raise RuntimeError(str(r.status)+' '+b.decode())
 return json.loads(b) if b else None
c=api('/containers/create?name='+request['name'],request['config']);api('/containers/'+c['Id']+'/start');print(c['Id'])
