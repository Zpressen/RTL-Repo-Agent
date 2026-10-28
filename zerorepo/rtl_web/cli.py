from __future__ import annotations
import argparse
import json
from pathlib import Path
from .settings import Settings
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Deep Valley Chip RTL demo bridge")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["preflight", "import-case", "export-static", "prepare-cases", "serve", "export-seed", "import-seed", 'review-memory', 'validate-stories', 'import-stories']:
        p = sub.add_parser(name)
        p.add_argument("--config")
        from .cases import CASES

        p.add_argument("--case", default="e203", choices=list(CASES))
        if name in {'review-memory','validate-stories','import-stories'}:
            p.add_argument('--source',type=Path,required=True)
            p.add_argument('--dry-run',action='store_true')
            if name=='import-stories':p.add_argument('--activate',action='store_true')
        if name == "preflight":
            p.add_argument("--json", action="store_true")
            p.add_argument('--fail-if-unready',action='store_true')
            p.add_argument('--candidate',action='store_true')
        if name == 'export-seed':
            p.add_argument('--out',type=Path,required=True)
        if name == 'import-seed':
            p.add_argument('--source',type=Path,required=True)
            p.add_argument('--dry-run',action='store_true')
        if name == "import-case":
            p.add_argument("--source", type=Path)
            p.add_argument("--bundle-id")
        if name in {"export-static", "prepare-cases"}:
            p.add_argument("--bundle-id")
            p.add_argument("--out", type=Path, required=True)
        if name == "serve":
            p.add_argument("--host", default="127.0.0.1")
            p.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = Settings(args.config,create_data=args.command not in {'export-seed','import-seed'}).for_case(args.case)
    if args.command in {'review-memory','validate-stories','import-stories'}:
        from .schemas import DemoError
        try:
            if args.command=='review-memory':
                from .stories import review_memory
                result=review_memory(settings,args.source,args.dry_run)
            else:
                from .stories import import_story
                result=import_story(settings,args.source,args.dry_run or args.command=='validate-stories',getattr(args,'activate',False))
            print(json.dumps(result,ensure_ascii=False))
        except (ValueError,OSError,KeyError,DemoError) as error:
            print(json.dumps({'error':'story_input_invalid','type':type(error).__name__}))
            raise SystemExit(3)
        return
    if args.command in {'export-seed','import-seed'}:
        from .seed import export_seed, import_seed
        from .schemas import DemoError
        try:
            result=(export_seed(settings,args.out) if args.command=='export-seed'
                    else import_seed(settings,args.source,args.dry_run))
            print(json.dumps(result,ensure_ascii=False))
        except (ValueError,DemoError,OSError,KeyError) as error:
            # No traceback/config body: errors can refer to private source files.
            print(json.dumps({'error':'seed_invalid','type':type(error).__name__}))
            raise SystemExit(3)
        return
    store = Store(settings.data)
    if args.command == "preflight":
        result=settings.preflight(probe_runtime=True,candidate=args.candidate)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if args.fail_if_unready and not all(c['available'] for c in result['capabilities'].values()):
            raise SystemExit(4)
        return
    if args.command == "import-case":
        from .import_case import import_case

        b = import_case(settings, store, args.source, args.bundle_id)
        print(
            json.dumps(
                {
                    "bundle_id": b["bundle_id"],
                    "validations": len(b["validations"]),
                    "modules": len(b["modules"]),
                }
            )
        )
        return
    if args.command == "export-static":
        from .import_case import export_static

        b = export_static(
            settings, store, args.bundle_id or settings.bundle_id, args.out
        )
        print(
            json.dumps(
                {
                    "bundle_id": b["bundle_id"],
                    "out": str(args.out.resolve()),
                    "raw_private_files_exported": False,
                }
            )
        )
        return
    if args.command == "prepare-cases":
        from .cases import CASES
        from .import_case import import_case, export_static
        from .artifacts import atomic_json

        catalog = []
        for cid, c in CASES.items():
            selected = settings.for_case(cid)
            b = import_case(selected, store)
            export_static(selected, store, b["bundle_id"], args.out / cid)
            catalog.append(
                {
                    "case_id": cid,
                    "title": c["title"],
                    "subtitle": c["subtitle"],
                    "available": True,
                    "manifest_url": f"/cases/{cid}/manifest.json",
                }
            )
        atomic_json(args.out / "index.json", {"cases": catalog})
        print(
            json.dumps(
                {
                    "cases": [c["case_id"] for c in catalog],
                    "out": str(args.out.resolve()),
                }
            )
        )
        return
    if args.command == "serve":
        if args.host not in {"127.0.0.1", "localhost", "::1"}:
            parser.error("Development access may bind only to loopback")
        if not settings.development and not settings.gateway_key:
            parser.error("Production requires RTL_DEMO_GATEWAY_KEY")
        import faulthandler, signal

        faulthandler.register(signal.SIGUSR2, all_threads=True)
        import uvicorn
        from .api import create_app

        uvicorn.run(
            create_app(settings),
            host=args.host,
            port=args.port,
            workers=1,
            access_log=False,
            timeout_graceful_shutdown=8,
        )


if __name__ == "__main__":
    main()
