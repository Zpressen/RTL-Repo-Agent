"""Display concrete, validated design fields; never infer private thought traces."""
from __future__ import annotations
import json


def artifact_report(payload):
    if hasattr(payload,'model_dump'):payload=payload.model_dump(mode='json')
    if not isinstance(payload,dict):return None
    findings=[];plan=[]
    def add(value):
        if isinstance(value,str) and value.strip():findings.append(value[:300])
    module=payload.get('module') or payload.get('top_module')
    ledger=payload.get('fact_ledger')
    if isinstance(ledger,dict):
        facts=ledger.get('facts',[]);unknown=ledger.get('ambiguous_items',[])
        add(f'已提取{len(facts)}项规格事实，{len(unknown)}项未决内容。')
        selected=sorted(facts,key=lambda f: str(f.get('category','')) in {'module_identity','interface'})[:2]
        for fact in selected:
            if not isinstance(fact,dict):continue
            obj=fact.get('object',{})
            if not isinstance(obj,dict):continue
            detail=next((obj[k] for k in ('description','rule','behavior','meaning','value') if isinstance(obj.get(k),(str,int))),None)
            if detail is None:
                detail='；'.join(f'{key}={value}' for key,value in obj.items() if isinstance(value,(str,int,bool)))
            if detail:add(str(fact.get('subject',''))+'：'+str(detail))
    contracts=payload.get('interface_contracts',[])
    if isinstance(payload.get('interface_contract'),dict):contracts=[payload['interface_contract']]
    for contract in contracts[:1]:
        ports=contract.get('ports',[])
        add(f'{contract.get("module",module or "")} 接口共{len(ports)}个端口：'+', '.join(f'{p.get("direction","")} {p.get("name","")}[{p.get("width","")}]' for p in ports[:8]))
        if contract.get('clock'):add('时钟：'+str(contract['clock']))
        if contract.get('reset'):add('复位：'+str(contract['reset'])+' '+str(contract.get('reset_polarity','')))
    modules=payload.get('modules',[])
    if modules:
        add('模块方案：'+'、'.join(m.get('module',m.get('module_name','')) for m in modules if isinstance(m,dict)))
        for m in modules[:3]:
            if isinstance(m,dict):add(str(m.get('module',m.get('module_name','')))+'：'+str(m.get('role','')))
    for responsibility in payload.get('responsibilities',[])[:3]:
        if isinstance(responsibility,dict):add(responsibility.get('description'))
    for subtask in payload.get('subtasks',[])[:3]:
        if isinstance(subtask,dict):plan.append(f'{subtask.get("id","")} · {subtask.get("description",subtask.get("target",""))}'[:300])
    if isinstance(payload.get('code'),str):
        add(f'{module or "模块"} / {payload.get("subtask_id", "代码片段")}：已生成{len(payload["code"].splitlines())}行实现。')
        contract=payload.get('contract')
        if isinstance(contract,dict):
            if contract.get('writes'):add('写入信号：'+'、'.join(str(v) for v in contract['writes'][:8]))
            if contract.get('reads'):add('读取信号：'+'、'.join(str(v) for v in contract['reads'][:8]))
    if not findings and not plan:return None
    summary=findings[0] if findings else f'{module or "当前模块"}：{len(plan)}项局部实现任务。'
    return dict(summary=summary,findings=findings[1:4],plan=plan[:3])
