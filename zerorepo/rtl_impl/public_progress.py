"""Concise display reports, separate from prompts and private reasoning."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
import json
import re
from uuid import uuid4

_step = ContextVar('rtl_public_step', default=None)

OPERATIONS = {
    'TopResolutionOutput': '确认顶层模块及规格出处',
    'ResponsibilityLedgerOutput': '提取功能职责、状态归属和模块依赖',
    'Stage2DecompositionCandidate': '拟定模块拆分候选与接口边界',
    'Stage2RankingDecisionOutput': '比较架构候选的职责覆盖和实现复杂度',
    'Stage2AdjudicationDecisionOutput': '核对候选分歧并确定架构方案',
    'Stage2PairwiseDecisionOutput': '比较两组架构的耦合关系与拆分代价',
    '_FactRoundPayload': '提取需求事实及原文依据',
    '_TopInterfaceRoundPayload': '确认顶层端口、位宽与时钟复位',
}
STEPS = {
    'stage1': ('spec', '解析需求约束与来源'),
    'stage2': ('architecture', '确定模块职责和层次关系'),
    'stage3': ('architecture', '设计模块端口、状态与内部骨架'),
    'stage4': ('architecture', '拆分局部实现任务并关联规格'),
    'stage5': ('rtl', '生成模块实现片段'),
    'stage6': ('rtl', '合并模块代码并保留接口'),
}
PUBLIC_INSTRUCTION = '''
For the live workbench, return one JSON object. Its FIRST field MUST be
"_public_start": {"summary":"简短的当前任务分析，点明本次处理的具体模块/接口或约束",
"plan":["本次调用将完成的具体工作，最多3项"]}. Write this small public report
before the artifact fields so it can be displayed while the artifact is generating.
Include a final "_public_progress" object describing the result of this call.
Keep all required artifact/patch fields unchanged, at the same top level.
Use concise Chinese: {"summary":"1-2 sentences describing the result and its
evidence", "plan":["up to 3 concrete next actions"], "findings":["up to 3 observed
facts or unresolved items"], "decisions":["up to 3 brief design choices with their
practical reason"]}. This is a public status report, not a private reasoning trace.
Preserve supplied/frozen testbenches. Do not propose rewriting or creating tests
unless the task explicitly requests supported test preparation. Report next actions
as proposals, not as completed tool operations. Use only capabilities of this task.
Do not include chain-of-thought, scratch work, credentials, private absolute paths,
or claim compilation/simulation passed without an actual tool result. Clearly
mark proposals and unknowns. Do not add this field to raw HDL output.
'''


@contextmanager
def public_step(stage, *, module='', output='', attempt=1, json_output=True):
    phase, label = STEPS.get(stage.split('_')[0], ('spec', '处理当前设计材料'))
    label = OPERATIONS.get(output, label)
    if module: label += ' · ' + str(module)[:100]
    if attempt > 1: label += f'（第{attempt}次修正）'
    token = _step.set(dict(stage=phase, label=label, substage=stage, action_id='action-'+uuid4().hex,
                           module=module, json_output=json_output))
    try: yield
    finally: _step.reset(token)


def current_step():
    return _step.get()


def request_progress_callback(emit, step, options):
    """Publish only counters and known wait states; never stream raw content."""
    def progress(snapshot):
        status=snapshot.get('status')
        elapsed=max(0,float(snapshot.get('elapsed_seconds',0)))
        if status not in {'running','retrying'} or elapsed<1:
            return
        phase=snapshot.get('waiting_phase')
        count=max(0,int(snapshot.get('effective_content_chars',0)))
        remaining=max(0,int(snapshot.get('remaining_seconds',0)))
        attempt=max(1,int(snapshot.get('attempt',1)))
        if status=='retrying':
            summary='本次请求未收到有效正文，正在按请求策略重试；共用原请求时间预算。'
        elif count:
            summary=f'正在接收模型输出，已收到{count}个有效字符；本次请求剩余{remaining}秒。'
        elif phase=='reasoning':
            reasoning=max(0,int(snapshot.get('reasoning_chars',0)))
            summary=f'模型正在推理，已收到{reasoning}个推理字符，尚未返回正文；本次请求剩余{remaining}秒。'
        else:
            wait='等待模型服务建立响应' if phase=='awaiting_headers' else '模型连接已建立，等待有效正文'
            summary=f'{wait}；已等待{int(elapsed)}秒，首段输出上限{int(options.first_content_timeout_seconds)}秒；本次请求剩余{remaining}秒。'
        emit('model.progress',stage=step['stage'],action_id=step['action_id'],substage=step['substage'],
             purpose_summary=step['label'],result_summary=f'第{attempt}次请求 · '+summary,
             elapsed_ms=round(elapsed*1000),status='running',reason_code='request_retrying' if status=='retrying' else 'request_reasoning' if phase=='reasoning' and not count else 'request_waiting' if not count else 'request_streaming')
    return progress


def request_failure_summary(exc):
    from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError, LLMRequestError, LLMResponseTruncatedError
    if isinstance(exc,LLMRequestTimeoutError):
        reason=exc.diagnostics.get('timeout_reason')
        return {
            'first_content_timeout':'等待模型首段有效输出超时，当前请求已结束。',
            'content_idle_timeout':'模型输出中断，超过连续无有效正文的等待上限，当前请求已结束。',
            'reasoning_timeout':'模型持续推理，但未在推理阶段时限内返回正文，当前请求已结束。',
            'reasoning_idle_timeout':'模型推理流中断，超过连续无有效推理的等待上限，当前请求已结束。',
            'total_timeout':'已达到单次模型请求的总时限，当前请求已结束。',
        }.get(reason,'模型请求超时，当前请求已结束。')+' 本轮未完成，已保留已有材料；不代表整轮任务预算已耗尽。'
    if isinstance(exc,LLMResponseTruncatedError):
        return '模型输出达到长度上限，结果不完整；已停止并保留已有材料。'
    if isinstance(exc,LLMRequestError):
        return '模型服务请求失败，已停止并保留已有材料。'
    return None


def split_public_result(raw):
    """Strip the reserved display field before any artifact/patch validation."""
    payload = raw
    if isinstance(raw, str):
        value = raw.strip()
        if value.startswith('```'):
            value = re.sub(r'^```(?:json)?\s*|\s*```$', '', value)
        from .json_output import escape_invalid_json_backslashes
        try: payload = json.loads(escape_invalid_json_backslashes(value))
        except (ValueError, TypeError): return raw, None, None
    if not isinstance(payload, dict): return raw, None, None
    cleaned = dict(payload)
    start = cleaned.pop('_public_start', None)
    progress = cleaned.pop('_public_progress', None)
    if start is None and progress is None: return raw, None, cleaned
    public = {}
    if isinstance(progress, dict):
        if isinstance(progress.get('summary'), str): public['summary'] = progress['summary'][:600]
        for key in ('plan', 'findings', 'decisions'):
            if isinstance(progress.get(key), list):
                public[key] = [item[:300] for item in progress[key][:3] if isinstance(item, str) and item.strip()]
    return (json.dumps(cleaned, ensure_ascii=False) if isinstance(raw, str) else cleaned), public or None, cleaned


def live_report_callback(emit, step):
    """Accept only a completed FIRST public field, never raw streamed prose."""
    reported = False
    def content(text):
        nonlocal reported
        if reported:return
        match=re.match(r'^\s*(?:```json\s*)?\{\s*"_public_start"\s*:\s*',text)
        if not match:return
        try:report,_=json.JSONDecoder().raw_decode(text[match.end():])
        except (ValueError,TypeError):return
        if not isinstance(report,dict):return
        public={}
        if isinstance(report.get('summary'),str):public['summary']=report['summary'][:600]
        if isinstance(report.get('plan'),list):public['plan']=[v[:300] for v in report['plan'][:3] if isinstance(v,str)]
        if not public:return
        reported=True
        emit('progress.reported',stage=step['stage'],action_id=step['action_id'],substage=step['substage'],
             source_kind='agent_public_summary',purpose_summary=step['label'],public_progress=public)
    return content


def artifact_result(payload):
    """Only public artifact facts; arbitrary response prose is never displayed."""
    if not isinstance(payload, dict): return '模型已返回结果，正在进行格式和约束检查。'
    facts = []
    for key, label in [('modules', '模块'), ('responsibilities', '功能职责'), ('facts', '需求事实'),
                       ('ports', '端口'), ('spec_blocks', '规格片段'), ('subtasks', '实现任务'), ('patches', '局部补丁')]:
        items = payload.get(key)
        if isinstance(items, list):
            text = f'{len(items)}项{label}'
            if key == 'modules':
                names = [v.get('module') or v.get('module_name') for v in items if isinstance(v, dict)]
                names = [n for n in names if isinstance(n, str) and re.fullmatch(r'[A-Za-z_][\w$]{0,100}', n)]
                if names: text += '：' + '、'.join(names[:6])
            facts.append(text)
    if isinstance(payload.get('module'), str) and re.fullmatch(r'[A-Za-z_][\w$]{0,100}', payload['module']):
        facts.append('目标模块 ' + payload['module'])
    return ('已返回' + '；'.join(facts) + '。结果尚待结构与约束检查。') if facts else '模型已返回当前步骤的结构化结果，正在检查约束一致性。'
