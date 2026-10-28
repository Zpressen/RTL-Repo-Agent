from __future__ import annotations
import asyncio
import json
import os
import signal
from .artifacts import Artifacts, redact
from .import_case import public
from .schemas import ChatDecision, DemoError, now
from .settings import Settings
from .store import Store

def validate_context(store: Store, sid: str, context: dict) -> dict:
    ctx = {**context}
    from .cases import case_config

    selected = ctx.get("case_id", "e203")
    case_config(selected)
    if store.session(sid).get("case_id", "e203") != selected:
        raise DemoError(
            "case_mismatch", "会话与所选任务不一致，请切换任务后重试。", 422
        )
    ctx["case_id"] = selected
    if ctx.get("version_id"):
        v = store.get("version", ctx["version_id"], sid)
        if ctx.get("run_id") and ctx["run_id"] != v["run_id"]:
            raise DemoError("context_mismatch", "版本与所选运行不一致。", 422)
        ctx["run_id"] = v["run_id"]
    if ctx.get("validation_id"):
        val = store.get("validation", ctx["validation_id"], sid)
        if ctx.get("version_id") and ctx["version_id"] != val["version_id"]:
            raise DemoError("context_mismatch", "报告与所选版本不一致。", 422)
        ctx.update(version_id=val["version_id"], run_id=val["run_id"])
    if ctx.get("run_id"):
        run = store.get("run", ctx["run_id"], sid)
        if run.get("case_id", "e203") != selected:
            raise DemoError("case_mismatch", "所选版本或报告属于其他任务。", 422)
    if ctx.get("module_id") and ctx.get("version_id"):
        if ctx["module_id"] not in {
            m["module_id"]
            for m in store.get("version", ctx["version_id"], sid)["modules"]
        }:
            raise DemoError("unknown_module", "该版本不包含所选模块。", 422)
    from .stories import validate_story_context
    return validate_story_context(store, ctx)


def submit_operation(
    settings: Settings, store: Store, sid: str, idem: str, kind: str, context: dict
):
    if kind not in {"verify", "generate_and_verify", "fix"}:
        raise DemoError("unsupported_operation", "不支持该操作。", 422)
    ctx = validate_context(store, sid, context)
    settings = settings.for_case(ctx["case_id"])
    if kind in {"verify", "fix"} and not ctx.get("version_id"):
        raise DemoError("target_required", "请先选择要验证的RTL版本。", 422)
    if kind == "fix":
        if not ctx.get("validation_id"):
            raise DemoError("target_required", "请先选择失败验证记录。", 422)
        val = store.get("validation", ctx["validation_id"], sid)
        if val["verdict"] != "fail" or not val["simulation_completed"]:
            raise DemoError(
                "failed_target_required", "请在验证页选择一次失败的系统仿真记录。", 422
            )
    # Idempotent retries remain valid even after a dependency has gone away.
    with store.connect() as c:
        prior = c.execute(
            "SELECT 1 FROM operations WHERE session_id=? AND idem=?", (sid, idem)
        ).fetchone()
    if not prior:
        settings.require(kind)
    return store.accept_operation(sid, idem, {"kind": kind, "context_ref": ctx})


def evidence(settings: Settings, store: Store, message: dict) -> dict:
    sid = message["session_id"]
    ctx = message["context_ref"]
    art = Artifacts(settings.data, store)
    bundle = store.get(
        "bundle", settings.for_case(ctx.get("case_id", "e203")).bundle_id
    )
    from .recorded_history import expanded_bundle
    bundle = expanded_bundle(store, bundle)
    result = {
        "context_ref": ctx,
        "case": {
            "title": bundle["title"],
            "summary": bundle["summary"],
            "modules": bundle["modules"],
        },
        "available_artifacts": [],
    }
    selected = [bundle["spec_artifact_id"], bundle["planner_artifact_id"]]
    current_run = store.get('run', ctx['run_id'], sid) if ctx.get('run_id') else None
    historical = not current_run or current_run.get('origin') == 'historical'
    result['record_origin'] = 'historical' if historical else 'live'
    if not historical:
        result['case']['modules'] = current_run.get('modules', [])
        result['case']['summary'] = '当前实时运行；规划与结果仅以本次已保存记录为准。'
        selected = [bundle['spec_artifact_id']]
    result['page'] = ctx.get('view', 'workspace')
    if ctx.get('view', 'workspace') != 'workspace' or ctx.get('story_id'):
        from .stories import story_view
        view = story_view(store, ctx.get('case_id','e203'), ctx.get('story_id'))
        result['page'] = ctx.get('view','workspace')
        if result['page'] == 'experience':
            result['evolution_narrative'] = {'presentation':'mechanism_concept',
                'steps':['观测执行','评估反馈','沉淀记忆','调整策略','再次验证'],
                'direction':'RI 改进当前设计，RSI 方向探索改进后续任务的方法',
                'status':'演进愿景；场景推演不代表已实现能力或已测量收益'}
        result['story_readiness'] = {'optimization':view['optimization'], 'experience':view['experience']['state']}
        if ctx.get('memory_revision_id'):
            memory = next((m for m in view['experience']['memories'] if m['revision_id']==ctx['memory_revision_id']),None)
            result['selected_memory'] = memory
            uses = [u for u in view['experience']['uses'] if u['revision_id']==ctx['memory_revision_id'] and (not ctx.get('memory_use_id') or u['use_id']==ctx['memory_use_id'])]
            result['memory_uses'] = [{**u, 'events':u['events'][-20:]} for u in uses[:5]]
            result['memory_summary_limits'] = {'uses_shown':min(len(uses),5), 'uses_total':len(uses), 'events_per_use':20}
            result['memory_lifecycle'] = [e for e in view['experience']['lifecycle_events'] if e['revision_id']==ctx['memory_revision_id'] or e.get('replacement_revision_id')==ctx['memory_revision_id']][-10:]
            result['memory_benefit'] = '收益待验证；对照仅按其条件和样本范围解释'
            if memory:
                for ref in memory['evidence_refs'][:8]:
                    if ref['kind']=='artifact':selected.append(ref['id'])
                    if ref['kind']=='validation':selected.append(store.get('validation',ref['id'],sid)['report_artifact_id'])
    if ctx.get("version_id"):
        version = store.get("version", ctx["version_id"], sid)
        modules = version["modules"]
        if ctx.get("module_id"):
            modules = [m for m in modules if m["module_id"] == ctx["module_id"]]
        selected.extend(m["artifact_id"] for m in modules[:3])
        result["version"] = {
            k: version[k] for k in ["version_id", "tree_sha256", "run_id"]
        }
    if ctx.get("validation_id"):
        val = store.get("validation", ctx["validation_id"], sid)
        result["validation"] = public(val)
        selected.append(val["report_artifact_id"])
        attempt = next((a for r in bundle.get('debug_history', {}).get('runs', []) for a in r['attempts']
                        if a['validation_id'] == val['validation_id']), None)
        if attempt:
            result['recorded_repair'] = {k: attempt[k] for k in ['candidate_version_id', 'baseline_version_id', 'before_validation_id', 'validation_id', 'decision']}
            result['recorded_repair']['diagnosis'] = attempt.get('diagnosis')
            result['recorded_repair']['changes'] = attempt['debug']['files']
            result['recorded_repair']['scope'] = '历史记录；没有执行本次修复，诊断假设不等于已确认根因'
    remaining = 64000
    if historical and bundle.get('debug_history'):
        runs = bundle['debug_history']['runs']
        attempts = [a for r in runs for a in r['attempts']]
        same_baseline = [a for a in attempts if a['baseline_version_id'] == ctx.get('version_id')]
        final = next((v for v in runs[-1]['validations'] if v['validation_id'] == runs[-1]['final_validation_id']), None)
        result['historical_debug_context'] = {
            'candidate_count': len(attempts),
            'final_validation': public(final) if final else None,
            'hypotheses_for_selected_baseline': [
                {'candidate_version_id': a['candidate_version_id'], 'diagnosis': a.get('diagnosis'), 'decision': a['decision']}
                for a in same_baseline[:4]],
            'scope': '只有当前选中版本的报告代表当前结果；最终归档结果及其他候选必须分别说明。根因假设不等于已证实原因。'}
    for ident in list(dict.fromkeys(selected))[:10]:
        if remaining <= 0: break
        item = store.get("artifact", ident, sid)
        if item["exposure"] != "display":
            continue
        content = art.file(item).read_text()
        excerpt = redact(content)[:min(18000, remaining)]
        remaining -= len(excerpt)
        result["available_artifacts"].append(
            {
                "artifact_id": ident,
                "kind": item["kind"],
                "content": excerpt,
            }
        )
    return result


async def model_decision(settings: Settings, payload: dict) -> ChatDecision:
    if settings.bounded_chat:
        import resource
        from .budgets import bounded_chat_memory_ready
        maximum=384*1024**2
        current=resource.getrlimit(resource.RLIMIT_AS)[1]
        if current<0 or current>maximum:
            raise DemoError('resource_unavailable','对话服务须使用受限启动器。',503)
        if not bounded_chat_memory_ready():
            raise DemoError('resource_unavailable','当前内存余量不足，请稍后发送。',503)
    task_root=None
    command=[settings.python,'-m','zerorepo.rtl_web.chat_runtime','--config',str(settings.config_path)]
    process_env=settings.tool_env()
    if not settings.development:
        from .jobs import prepare_chat_job
        from .sandbox import job_command, minimal_environment
        task_root,config=prepare_chat_job(settings)
        command=job_command(settings,task_root/'job.json',[
            settings.python,'-m','zerorepo.rtl_web.chat_runtime','--config',str(config)])
        process_env=minimal_environment(process_env)
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,cwd=settings.repo,env=process_env,start_new_session=True)
    except BaseException:
        if task_root:
            import shutil
            shutil.rmtree(task_root)
        raise
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(json.dumps(payload, ensure_ascii=False).encode()),
            settings.chat_timeout,
        )
        if proc.returncode != 0:
            diagnostic=redact(err.decode(errors="replace"))
            (settings.data / "chat-error.log").write_text(
                diagnostic[:4000]
            )
            import re
            if re.search(r'^RTL_DEMO_CHAT_ERROR=LLMRequestError:.*\bHTTP 403\s*$',diagnostic,re.MULTILINE):
                raise DemoError('model_access_denied','模型上游返回 HTTP 403，当前请求被拒绝；请检查模型服务的访问规则。',503)
            raise DemoError("model_unavailable", "模型服务暂不可用，请稍后重试。", 503)
        lines = [
            line.split("=", 1)[1]
            for line in out.decode(errors="replace").splitlines()
            if line.startswith("RTL_DEMO_CHAT_RESULT=")
        ]
        if not lines:
            raise DemoError(
                "model_response_invalid", "模型未返回有效回复，请重试。", 503
            )
        data = json.loads(lines[-1])
        receipt = data.pop('_model_receipt', None)
        decision = ChatDecision.model_validate(data)
        if isinstance(receipt, dict):
            decision._model_receipt = {k: v for k, v in receipt.items()
                                       if (k == 'model' and isinstance(v, str) and len(v) < 200)
                                       or (k in {'elapsed_ms', 'input_tokens', 'output_tokens', 'total_tokens'}
                                           and isinstance(v, int) and not isinstance(v, bool) and v >= 0)}
        return decision
    except asyncio.TimeoutError:
        raise DemoError("model_timeout", "模型回答超时，请稍后重试。", 503)
    finally:
        if proc.returncode is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await proc.wait()
        if task_root:
            import shutil
            shutil.rmtree(task_root)


async def respond(settings: Settings, store: Store, message: dict, provider=None):
    settings = settings.for_case(message["context_ref"].get("case_id", "e203"))
    try:
        from .chat_analysis import normalize, unsupported_reply
        text = normalize(message['text'])
        notice = unsupported_reply(text)
        if notice is not None:
            store.update_message(message['message_id'], state='answered', answer=notice.text,
                                 evidence_refs=[], decision='answer', answer_source='unsupported_notice', finished_at=now())
            return
        if text == '分析并修复失败版本':
            text = '分析当前失败原因与历史修复记录；只分析，不执行代码修改。'
        proof = evidence(settings, store, message)
        history = [m for m in store.session(message['session_id'])['messages']
                   if m['sequence'] < message['sequence']]
        if provider:
            decision = await provider({'text': text, 'evidence': proof, 'history': history})
            if not isinstance(decision, ChatDecision):
                decision = ChatDecision.model_validate(decision)
        else:
            settings.require('chat')
            decision = await model_decision(settings, {'text': text, 'evidence': proof, 'history': history})
        allowed = {a['artifact_id'] for a in proof['available_artifacts']}
        refs = [
            x.model_dump(exclude_none=True)
            for x in decision.evidence_refs
            if x.artifact_id in allowed
        ]
        answer = redact(decision.text)
        op = None
        if decision.kind in {"verify", "generate_and_verify", "fix"}:
            if settings.runtime.get('chat_execution_enabled') is not True:
                decision = ChatDecision(kind='answer', text='当前演示仅支持对话分析，不支持现场生成、重新验证或实际修复。请使用“分析失败原因与修复记录”查看归档证据。')
                answer = decision.text
        if decision.kind in {"verify", "generate_and_verify", "fix"}:
            op, _ = submit_operation(
                settings,
                store,
                message["session_id"],
                "message-" + message["message_id"],
                decision.kind,
                message["context_ref"],
            )
            answer = (
                "已提交"
                + {
                    "verify": "系统验证",
                    "generate_and_verify": "RTL生成与验证",
                    "fix": "失败版本分析与修复",
                }[decision.kind]
                + "，结果以实际执行记录为准。"
            )
        store.update_message(
            message["message_id"],
            state="clarification" if decision.kind == "clarify" else "answered",
            answer=answer,
            evidence_refs=refs,
            operation_id=op["operation_id"] if op else None,
            decision=decision.kind,
            answer_source='model', finished_at=now(),
            model_receipt=decision._model_receipt,
        )
    except DemoError as error:
        store.update_message(
            message["message_id"],
            state="clarification" if error.status == 422 else "failed",
            answer=error.message,
            error_code=error.code,
            finished_at=now(),
        )
    except asyncio.CancelledError:
        store.update_message(
            message["message_id"],
            state="interrupted",
            answer="对话中断，请重新发送问题。",
        )
        raise
    except Exception:
        store.update_message(
            message["message_id"],
            state="failed",
            answer="暂时无法生成回答，请重试。",
            error_code="chat_error",
        )
