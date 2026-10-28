"""Private, authenticated per-task transport to the existing trusted MCP session."""
from __future__ import annotations
import inspect
import json
import os
from pathlib import Path
import secrets
import socket
import socketserver
import tempfile
import threading
from .artifacts import redact

FIELDS={
 'query_rtl_memories':['module_name','signals','failure_type','limit'],
 'read_rtl_memory':['revision_id','max_chars'],
 'record_memory_application':['revision_id','decision','reason','target_files','target_signals'],
 'read_module_semantics':['module_name','sections','focus_signals','focus_blocks','max_chars'],
 'query_rtl_kg':['query_type','module_name','signal_name','instance_name'],
 'trace_signal_cause':['module_name','signal_name','time','expected_value','max_candidates'],
 'list_vcd_signals':['pattern','scope','limit'],
 'probe_vcd':['signals','time','time_range','edge','mode','max_rows'],
 'run_check':['mode','signals','time_window'],
 'validate_rtl_changes':['action','candidate_id','reason','expected_effect'],
 'get_debug_status':[]}


def validate_call(run_id,method,params):
    if not run_id or method not in FIELDS or not isinstance(params,dict) or set(params)-set(FIELDS[method]):
        raise ValueError('Tool scope violation')
    if method=='query_rtl_memories' and (not isinstance(params.get('limit',5),int) or not 1<=params.get('limit',5)<=5):
        raise ValueError('Memory query budget')
    if method=='read_rtl_memory' and (not isinstance(params.get('max_chars',8000),int) or not 1<=params.get('max_chars',8000)<=8000):
        raise ValueError('Memory read budget')
    if method=='query_rtl_kg' and params.get('query_type') not in {'module_interface','module_instances','instance_connections','signal_drivers'}:
        raise ValueError('Only fixed KG templates are permitted')
    def bounded(value):
        if isinstance(value,str):
            if len(value)>40000 or '\x00' in value:raise ValueError('Tool argument budget')
        elif isinstance(value,list):
            if len(value)>256:raise ValueError('Tool argument budget')
            for v in value:bounded(v)
        elif value is not None and not isinstance(value,(int,bool)):raise ValueError('Unsupported tool value')
    for key,value in params.items():
        bounded(value)
        if key in {'candidate_id','module_name','signal_name','instance_name'} and value is not None:
            import re
            if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_$.-]{1,256}',value) or '..' in value:
                raise ValueError('Invalid tool identifier')
        if key in {'limit','max_rows','max_candidates'} and (not isinstance(value,int) or not 1<=value<=1000):
            raise ValueError('Tool observation budget')


class ToolBridge:
    def __init__(self,descriptor_path,run_id,*,session_factory=None):
        if session_factory is None:
            from zerorepo.rtl_impl.codex_debug.session import CodexDebugSession
            session_factory=CodexDebugSession.from_descriptor_path
        self.session=session_factory(Path(descriptor_path))
        self.run_id=run_id;self.token=secrets.token_hex(32)
        self.directory=Path(tempfile.mkdtemp(prefix='rtl-tool-',dir='/tmp'))
        os.chmod(self.directory,0o700);self.path=self.directory/'rpc.sock'
        bridge=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(360)
                line=self.rfile.readline(65537)
                try:
                    if len(line)>65536:raise ValueError('Tool request too large')
                    p=json.loads(line)
                    if set(p)!={'token','run_id','method','args','kwargs'} or p['run_id']!=bridge.run_id or not secrets.compare_digest(p['token'],bridge.token):
                        raise ValueError('Tool authentication failed')
                    method=p['method'];args=p['args'];kwargs=p['kwargs']
                    if method not in FIELDS or not isinstance(args,list) or len(args)>len(FIELDS[method]) or not isinstance(kwargs,dict):
                        raise ValueError('Tool scope violation')
                    params=dict(zip(FIELDS[method],args))
                    if set(params)&set(kwargs):raise ValueError('Duplicate tool argument')
                    params.update(kwargs);validate_call(bridge.run_id,method,params)
                    fn=getattr(bridge.session,method)
                    inspect.signature(fn).bind(**params)
                    result=fn(**params)
                except Exception as error:
                    result={'status':'tool_error','error':redact(type(error).__name__+': '+str(error))[:1000]}
                encoded=(json.dumps(result,ensure_ascii=False)+'\n').encode()
                if len(encoded)>1024**2:encoded=b'{"status":"tool_error","error":"Tool response budget"}\n'
                self.wfile.write(encoded)
        class Server(socketserver.ThreadingUnixStreamServer):
            daemon_threads=True
        self.server=Server(str(self.path),Handler);os.chmod(self.path,0o600)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.1},daemon=True)
        self.thread.start()

    def environment(self):
        return {'ZEROREPO_TOOL_BRIDGE':str(self.path),'ZEROREPO_TOOL_BRIDGE_TOKEN':self.token,'ZEROREPO_TOOL_RUN':self.run_id}

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=1)
        self.session.close()
        self.path.unlink(missing_ok=True);self.directory.rmdir()


def bridge_call(method,args,kwargs):
    path=os.environ['ZEROREPO_TOOL_BRIDGE']
    packet={'token':os.environ['ZEROREPO_TOOL_BRIDGE_TOKEN'],'run_id':os.environ['ZEROREPO_TOOL_RUN'],
            'method':method,'args':list(args),'kwargs':kwargs}
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        conn.settimeout(360);conn.connect(path);conn.sendall((json.dumps(packet)+'\n').encode())
        data=conn.makefile('rb').readline(1024**2+1)
        if len(data)>1024**2:raise ValueError('Tool response too large')
        return json.loads(data)
