"""CodeBuddy transport for the same packet evidence and delivery gates.

The trusted server selects the installed CLI, not the packet or tool caller.
No credentials, provider settings or host permissions are rewritten.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import shutil


def command():
    configured = os.environ.get('LUOMU_REVIEW_CODEBUDDY_CLI')
    path = Path(configured).resolve(strict=True) if configured else None
    if path is None:
        found = shutil.which('codebuddy') or shutil.which('codebuddy-code')
        if not found:
            raise ValueError('CODEBUDDY_CLI_UNAVAILABLE: configure the installed CLI on the server')
        path = Path(found).resolve(strict=True)
    if not path.is_file():
        raise ValueError('CODEBUDDY_CLI_UNAVAILABLE')
    if path.suffix.lower() in {'.cmd', '.ps1'}:
        path = path.parent/'node_modules/@tencent-ai/codebuddy-code/bin/codebuddy'
        if not path.is_file():
            raise ValueError('CODEBUDDY_NATIVE_ENTRY_UNAVAILABLE: no shell fallback')
    if path.suffix.lower() == '.exe':
        return [str(path)]
    node = shutil.which('node')
    if not node:
        raise ValueError('CODEBUDDY_NODE_UNAVAILABLE')
    return [node, str(path)]


def launch(home, model, output, instruction, prompt, schema, server_name, server_script,
           packet_path, lock_path, python):
    if not isinstance(model, str) or not model.strip() or model.startswith('-'):
        raise ValueError('CODEBUDDY_MODEL_REQUIRED: pass the current main-session model explicitly')
    config = output/'codebuddy-mcp.json'
    config.write_text(json.dumps({'mcpServers': {server_name: {
        'type': 'stdio', 'command': python,
        'args': [str(server_script), '--packet', str(packet_path), '--lock', str(lock_path), '--output', str(output)],
        'defer_loading': False,
    }}}, ensure_ascii=False), encoding='utf8')
    # Only the dedicated read-only tools are pre-authorized. No permission bypass.
    safe_name=re.sub(r'[^A-Za-z0-9_]','_',server_name)
    allowed = ['mcp__'+safe_name+'__'+name for name in ('review_inventory','review_read','review_view')]
    # Validate with the shared controller after completion. Supplying a native
    # StructuredOutput tool can conflict with a host's empty built-in tool set.
    prompt += '\nReturn exactly one JSON object matching this schema, without Markdown:\n'+schema.read_text(encoding='utf8')
    args = command()+['--print','--output-format','stream-json','--verbose',
        '--no-session-persistence','--strict-mcp-config','--mcp-config',str(config),
        '--tools','','--allowedTools',','.join(allowed),
        '--model',model,'--max-turns','40','--system-prompt',instruction,'--',prompt]
    env = dict(os.environ, CODEBUDDY_CONFIG_DIR=str(home), PYTHONUTF8='1',
               CODEBUDDY_SKIP_BUILTIN_MARKETPLACE='1')
    return args, env


def normalize(rows, lock, final, expected_model=None):
    """Bind native tool-use/result pairs, keeping the raw stream as an artifact."""
    normalized=[];calls={};sessions=[];result=None;structured_calls=set();model_values=[]
    prefix='mcp__'+re.sub(r'[^A-Za-z0-9_]','_',lock['mcp_server_name'])+'__'
    for row in rows:
        kind=row.get('type')
        if kind=='system' and row.get('subtype')=='init':
            sid=row.get('session_id')
            if not isinstance(sid,str) or not sid:raise ValueError('CODEBUDDY_SESSION_MISSING')
            if expected_model is not None and row.get('model')!=expected_model:
                raise ValueError('CODEBUDDY_MODEL_MISMATCH')
            # CodeBuddy repeats init after asynchronous MCP discovery.
            if sid not in sessions:
                sessions.append(sid)
                normalized.append({'type':'thread.started','thread_id':sid})
        if row.get('parent_tool_use_id'):
            raise ValueError('UNEXPECTED_NESTED_DELEGATION')
        if row.get('session_id') is not None and sessions and row['session_id']!=sessions[0]:
            raise ValueError('CODEBUDDY_EVENT_SESSION_MISMATCH')
        if kind in {'assistant','user'}:
            blocks=row.get('message',{}).get('content',[])
            if not isinstance(blocks,list):continue
            for block in blocks:
                if block.get('type')=='tool_use':
                    name=block.get('name','');cid=block.get('id')
                    if name=='StructuredOutput':
                        if not isinstance(cid,str) or not cid or cid in structured_calls or cid in calls:
                            raise ValueError('CODEBUDDY_TOOL_ID_REUSED')
                        structured_calls.add(cid)
                        model_values.append(block.get('input'))
                        continue
                    if not isinstance(name,str) or not name.startswith(prefix):
                        raise ValueError('UNEXPECTED_DELEGATION_OR_TOOL: '+str(name))
                    if not isinstance(cid,str) or not cid or cid in calls or cid in structured_calls:
                        raise ValueError('CODEBUDDY_TOOL_ID_REUSED')
                    calls[cid]={'type':'mcp_tool_call','id':cid,'server':lock['mcp_server_name'],
                                'tool':name[len(prefix):],'arguments':block.get('input',{})}
                    normalized.append({'type':'item.started','item':dict(calls[cid])})
                elif block.get('type')=='tool_result':
                    cid=block.get('tool_use_id')
                    if cid in structured_calls:
                        # StructuredOutput is a host schema validator, not evidence.
                        continue
                    if cid not in calls:raise ValueError('CODEBUDDY_ORPHAN_TOOL_RESULT')
                    item=calls[cid]
                    if item.get('status'):raise ValueError('CODEBUDDY_DUPLICATE_TOOL_RESULT')
                    content=block.get('content',[])
                    if isinstance(content,str):content=[{'type':'text','text':content}]
                    # Anthropic image blocks and MCP image blocks carry the same bytes.
                    converted=[]
                    for value in content:
                        if value.get('type')=='text':
                            try:wrapped=json.loads(value.get('text',''))
                            except (ValueError,TypeError):wrapped=None
                            # CodeBuddy serializes MCP content arrays into a text block.
                            if isinstance(wrapped,list) and all(isinstance(v,dict) and v.get('type') in {'text','image'} for v in wrapped):
                                for part in wrapped:
                                    if part.get('type')=='image' and isinstance(part.get('image'),str):
                                        match=re.fullmatch(r'data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\r\n]+)',part['image'])
                                        if not match:raise ValueError('CODEBUDDY_IMAGE_ENCODING_INVALID')
                                        converted.append({'type':'image','mimeType':match[1],'data':match[2]})
                                    else:converted.append(part)
                                continue
                        if value.get('type')=='image' and 'source' in value:
                            source=value['source']
                            converted.append({'type':'image','mimeType':source.get('media_type'),'data':source.get('data')})
                        else:converted.append(value)
                    item.update(status='completed',error=block.get('is_error',False),
                                result={'isError':block.get('is_error',False),'content':converted})
                    normalized.append({'type':'item.completed','item':dict(item)})
                elif kind=='assistant' and block.get('type')=='text':
                    normalized.append({'type':'item.completed','item':{'type':'agent_message','text':block.get('text','')}})
                    try:model_values.append(json.loads(block.get('text','')))
                    except (ValueError,TypeError):pass
        if kind=='result':
            if result is not None:raise ValueError('CODEBUDDY_MULTIPLE_FINAL_RESULTS')
            result=row
    if len(sessions)!=1 or result is None or result.get('session_id')!=sessions[0]:
        raise ValueError('CODEBUDDY_FINAL_SESSION_MISMATCH')
    if result.get('is_error') or result.get('subtype')!='success' or result.get('permission_denials'):
        raise ValueError('CODEBUDDY_INCOMPLETE_OR_REFUSED: inspect native stream; no permission retry')
    if any(item.get('status')!='completed' for item in calls.values()):
        raise ValueError('CODEBUDDY_TOOL_NOT_COMPLETED')
    value=result.get('structured_output')
    if value is None:
        value=json.loads(result.get('result',''))
    if not isinstance(value,dict):raise ValueError('CODEBUDDY_STRUCTURED_RESULT_MISSING')
    if value not in model_values:raise ValueError('CODEBUDDY_FINAL_NOT_BOUND_TO_MODEL_EVENT')
    # Structured output is native result data; bind it to this same session's end.
    normalized.append({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value,ensure_ascii=False)}})
    normalized.append({'type':'turn.completed'})
    final.write_text(json.dumps(value,ensure_ascii=False),encoding='utf8')
    return normalized
