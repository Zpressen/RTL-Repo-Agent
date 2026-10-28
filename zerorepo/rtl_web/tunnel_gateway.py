"""Loopback gateway for SSH preview or the HTTPS Caddy ingress.

This mode does not enable development bypasses or claim production readiness.
An explicit private setting can omit the website password inside the SSH
tunnel; only the server injects the internal gateway header. A public
deployment continues to require HTTPS.
"""
from __future__ import annotations
import argparse
import base64
import binascii
import hashlib
import hmac
import json
from pathlib import Path
import os
import resource
import stat
import threading

from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.routing import Mount
from .settings import Settings


class RequestCapacity:
    """Bound active work, with separate slots for long-lived event streams.

    Uvicorn's connection limit also counts idle Caddy keep-alive connections.
    Applying that limit globally lets event streams/idle sockets reject every
    page and health request before the application can serve them.
    """

    def __init__(self, app, requests=16, streams=16):
        self.app = app
        self.limits = {"request": requests, "stream": streams}
        self.active = {"request": 0, "stream": 0}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        lane = "stream" if path.startswith("/api/sessions/") and path.endswith("/events") else "request"
        # No await between checking and claiming: these counters belong to
        # the single ASGI event loop, not the synchronous endpoint threads.
        if self.active[lane] >= self.limits[lane]:
            response = JSONResponse(
                {"error": {"code": "gateway_busy", "message": "连接较多，请稍后重试。"}},
                429, headers={"Retry-After": "3", "Cache-Control": "no-store"},
            )
            return await response(scope, receive, send)
        self.active[lane] += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.active[lane] -= 1


class TunnelGateway:
    def __init__(self,settings,design,auth):
        if settings.development or not settings.gateway_key:
            raise ValueError('Explicit gateway configuration required')
        public_origins={'https://design.deepvalleychip.cn','https://agent.deepvalleychip.cn'}
        if settings.access_mode=='public' and (len(settings.origins)!=1 or not settings.origins<=public_origins):
            raise ValueError('Public gateway requires the deployed HTTPS origin')
        path=Path(auth)
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode)&0o077:
            raise ValueError('Private gateway authentication file required')
        data=json.loads(path.read_text())
        self.password_required=data.get('password_required',True)
        if not isinstance(self.password_required,bool):raise ValueError('Invalid password setting')
        self.username=data['username'];self.salt=data['salt'].encode();self.expected=data['password_hash']
        self.iterations=int(data['iterations'])
        if not 100000<=self.iterations<=1000000 or len(self.expected)!=64:raise ValueError('Invalid authentication parameters')
        self.key=settings.gateway_key.encode()
        self.auth_cache=set()
        from .api import create_app
        self.api=create_app(settings)
        root=Path(design).resolve()
        if not (root/'index.html').is_file():raise ValueError('Complete design bundle required')
        self.static=Starlette(routes=[Mount('/',app=StaticFiles(directory=root,html=True,follow_symlink=False))])

    def authenticated(self,headers):
        if not self.password_required:return True
        token=dict(headers).get(b'authorization',b'')
        if len(token)>1024 or not token.startswith(b'Basic '):return False
        fingerprint=hashlib.sha256(token).digest()
        if fingerprint in self.auth_cache:return True
        try:
            decoded=base64.b64decode(token[6:],validate=True).decode('utf-8')
            username,password=decoded.split(':',1)
        except (ValueError,UnicodeError,binascii.Error):return False
        hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),self.salt,self.iterations).hex()
        valid=hmac.compare_digest(username,self.username) and hmac.compare_digest(hashed,self.expected)
        if valid:self.auth_cache.add(fingerprint)
        return valid

    async def __call__(self,scope,receive,send):
        if scope['type']=='lifespan':
            import anyio.to_thread
            anyio.to_thread.current_default_thread_limiter().total_tokens=4
            return await self.api(scope,receive,send)
        if scope['type']!='http':return
        if not self.authenticated(scope.get('headers',[])):
            response=JSONResponse({'error':{'code':'login_required','message':'请登录SSH演示工作台。'}},401,
                headers={'WWW-Authenticate':'Basic realm="RTL Agent SSH preview"','Cache-Control':'no-store'})
            return await response(scope,receive,send)
        path=scope.get('path','/')
        if path=='/api' or path.startswith('/api/'):
            copied={**scope,'headers':[(k,v) for k,v in scope['headers'] if k.lower() not in {b'authorization',b'x-demo-gateway-key'}]+[(b'x-demo-gateway-key',self.key)]}
            return await self.api(copied,receive,send)
        if any(part.startswith('.') for part in path.split('/') if part):
            return await JSONResponse({'error':{'code':'not_found'}},404)(scope,receive,send)
        # A release changes the entry document and history manifests at the
        # same URLs. Revalidate static responses, including 304s, so reloads
        # cannot silently keep an older workspace with retained hashed assets.
        async def send_static(message):
            if message['type']=='http.response.start':
                headers=[(k,v) for k,v in message.get('headers',[]) if k.lower()!=b'cache-control']
                message={**message,'headers':headers+[(b'cache-control',b'no-cache, max-age=0, must-revalidate')]}
            await send(message)
        await self.static(scope,receive,send_static)


def create_gateway(settings,design,auth):return RequestCapacity(TunnelGateway(settings,design,auth))


def main():
    import faulthandler
    faulthandler.enable()
    p=argparse.ArgumentParser(description='RTL gateway, loopback only; public HTTPS terminates at Caddy')
    p.add_argument('--config',required=True);p.add_argument('--design',required=True);p.add_argument('--auth',required=True)
    p.add_argument('--port',type=int,default=18080)
    args=p.parse_args()
    # The API and the single chat SDK interpreter each inherit this hard
    # address-space limit. Namespace helpers are separate small processes;
    # this is not an aggregate cgroup limit for native RTL execution.
    limit=384*1024**2
    resource.setrlimit(resource.RLIMIT_AS,(limit,limit));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    threading.stack_size(256*1024)
    for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
    import uvicorn
    app=create_gateway(Settings(args.config),args.design,args.auth)
    uvicorn.run(app,host='127.0.0.1',port=args.port,workers=1,access_log=False,timeout_keep_alive=5,timeout_graceful_shutdown=8)


if __name__=='__main__':main()
