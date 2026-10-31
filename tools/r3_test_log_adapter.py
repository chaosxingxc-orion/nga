"""Seven-column TEST-READS.log adapter for the guarded final-test transaction.

Durable append intent binds the exact log line to its staged result hash. This
does not validate scoring or authorize tests: the caller must hold execution
reservations and reverify producer evidence before publishing any completion.
"""
from contextlib import contextmanager
import datetime
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path

spec=importlib.util.spec_from_file_location('test_guard',Path(__file__).with_name('r3_test_execution_guard.py'))
G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)
COUNTS={'decision-v7':1200,'transfer-v4':656}


class CompletionLog:
    def __init__(self, round_dir, *, model_path, model_sha256, execution_sha256,
                 run_dir, final_sha256):
        self.root=G.safe_path(round_dir)
        self.path=self.root/'TEST-READS.log'
        self.model_path=str(G.safe_path(model_path))
        G.require(not any(c in self.model_path for c in '\t\r\n'),'invalid model path')
        self.model_sha=G.pin(model_sha256)
        self.execution_sha=G.pin(execution_sha256)
        self.run=G.safe_path(run_dir)
        self.final_sha=G.pin(final_sha256)

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True,exist_ok=True)
        G.safe_path(self.path)
        fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'r+',encoding='utf-8',newline='') as f:
            fcntl.flock(f,fcntl.LOCK_EX)
            yield f

    def matching(self, f, suite):
        G.require(suite in COUNTS,'unsupported test suite')
        f.seek(0);raw=f.read()
        G.require(not raw or raw.endswith('\n'),'partial test log tail requires explicit repair')
        found=[]
        for line in raw.splitlines():
            fields=line.split('\t')
            G.require(len(fields)==7,'malformed test log line')
            utc,path,sha,s,split,n,accuracy=fields
            G.pin(sha)
            G.require(s in COUNTS and split=='test','invalid test log partition')
            G.require(n==str(COUNTS[s]),'invalid test log population')
            value=float(accuracy)
            G.require(math.isfinite(value) and 0<=value<=1,'invalid test log accuracy')
            G.require(bool(utc) and Path(path).is_absolute(),'invalid test log identity')
            if sha==self.model_sha and s==suite:
                G.require(path==self.model_path,'test log model path differs')
                found.append(line+'\n')
        G.require(len(found)<=1,'duplicate test log completion')
        return found[0] if found else None

    def intent_path(self,suite):
        G.require(suite in COUNTS,'unsupported test suite')
        path=self.run/('TEST-LOG-INTENT.'+suite+'.json');G.safe_path(path)
        return path

    def staged(self,suite):
        path=self.run/'TEST-STAGED-RESULTS.json';G.safe_path(path)
        doc=json.loads(path.read_text())
        expected={'model_sha256':self.model_sha,'run_dir':str(self.run),
                  'execution_sha256':self.execution_sha,'final_sha256':self.final_sha}
        G.require(doc.get('schema')=='r3-test-staged-results-v1' and doc.get('owner')==expected
                  and doc.get('suites')==list(COUNTS),'staged log identity differs')
        result=doc['results'][suite]
        G.require(type(result.get('n')) is int and result['n']==COUNTS[suite],'staged population differs')
        acc=result['headline_accuracy']
        G.require(type(acc) in (int,float) and math.isfinite(acc) and 0<=acc<=1,'invalid staged accuracy')
        normalized={'suite':suite,'model_sha256':self.model_sha,
                    'execution_sha256':self.execution_sha,'result_sha256':G.digest(result)}
        return normalized,result

    def checked_intent(self,suite):
        path=self.intent_path(suite)
        if not path.exists():return None
        value=json.loads(path.read_text());expected,result=self.staged(suite)
        G.require(value.get('schema')=='r3-test-log-append-intent-v1'
                  and value.get('completion')==expected and value.get('final_sha256')==self.final_sha,
                  'log intent identity differs')
        fields=value.get('line','').rstrip('\n').split('\t')
        G.require(len(fields)==7 and value['line']=='\t'.join(fields)+'\n'
                  and fields[1:]==[self.model_path,self.model_sha,suite,'test',str(result['n']),
                                  '%.6f'%result['headline_accuracy']], 'log intent line differs')
        G.require(bool(fields[0]) and not any(c in fields[0] for c in '\r\n'),'invalid intent timestamp')
        return value

    def read(self,suite):
        with self.locked() as f:
            line=self.matching(f,suite);intent=self.checked_intent(suite)
            if line is None:return None
            G.require(intent is not None and intent['line']==line,'completion lacks matching durable intent')
            return intent['completion']

    def append_line(self,f,line):
        f.seek(0,os.SEEK_END);f.write(line);f.flush();os.fsync(f.fileno())
        directory=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)

    def append(self,suite,completion):
        with self.locked() as f:
            expected,result=self.staged(suite)
            G.require(completion==expected,'completion differs from staged result')
            line=self.matching(f,suite);intent=self.checked_intent(suite)
            if line is not None:
                G.require(intent is not None and intent['line']==line,'foreign completion cannot be adopted')
                return
            if intent is None:
                utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                line='\t'.join([utc,self.model_path,self.model_sha,suite,'test',str(result['n']),
                                '%.6f'%result['headline_accuracy']])+'\n'
                intent={'schema':'r3-test-log-append-intent-v1','completion':expected,
                        'final_sha256':self.final_sha,'line':line}
                G.atomic(self.intent_path(suite),intent)
            self.append_line(f,intent['line'])
