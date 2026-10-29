import os, json, sqlite3, time, hmac, hashlib, urllib.parse, secrets
from pathlib import Path
from collections import defaultdict, deque
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import httpx

BASE = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv('DB_PATH', str(BASE / 'data' / 'academy.sqlite3'))
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
DEV_MODE = os.getenv('DEV_MODE', 'false').lower() == 'true'
RUNNER_URL = os.getenv('RUNNER_URL', 'https://emkc.org/api/v2/piston/execute')
CURRICULUM = json.loads((BASE / 'curriculum' / 'curriculum.json').read_text(encoding='utf-8'))
app = FastAPI(title='C# Academy API', version='1.0.0')
app.mount('/static', StaticFiles(directory=BASE / 'web'), name='static')

rate_buckets = defaultdict(deque)
def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE IF NOT EXISTS progress (user_id TEXT NOT NULL, lesson_id INTEGER NOT NULL, completed INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, lesson_id))')
    conn.execute('CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, lesson_id INTEGER NOT NULL, code TEXT NOT NULL, output TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    return conn

def get_user(init_data: str | None):
    if not init_data:
        if DEV_MODE: return 'dev-user'
        raise HTTPException(401, 'Открой приложение через Telegram-бота.')
    if not BOT_TOKEN:
        raise HTTPException(503, 'BOT_TOKEN не настроен на сервере.')
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop('hash', None)
        if not received_hash: raise ValueError('hash missing')
        data_check = '\n'.join(f'{k}={v}' for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated, received_hash): raise ValueError('hash mismatch')
        auth_date = int(parsed.get('auth_date', '0'))
        if abs(time.time() - auth_date) > 86400: raise ValueError('expired initData')
        user = json.loads(parsed['user'])
        return str(user['id'])
    except Exception:
        raise HTTPException(401, 'Не удалось проверить вход Telegram. Закрой и заново открой приложение.')

def user_from_header(x_telegram_init_data: str | None):
    return get_user(x_telegram_init_data)

@app.get('/')
def home():
    return FileResponse(BASE / 'web' / 'index.html')

@app.get('/health')
def health(): return {'ok': True, 'lessons': len(CURRICULUM)}

@app.get('/api/curriculum')
def curriculum():
    return [{'id':x['id'],'stage':x['stage'],'stage_name':x['stage_name'],'title':x['title'],'explanation':x['explanation'],'example_code':x['example_code'],'practice_tasks':x.get('practice_tasks',[x['task']]),'hint':x['hint']} for x in CURRICULUM]

@app.get('/api/progress')
def progress(x_telegram_init_data: str | None = Header(default=None)):
    uid=user_from_header(x_telegram_init_data)
    conn=db(); rows=conn.execute('SELECT lesson_id,completed,score,updated_at FROM progress WHERE user_id=?',(uid,)).fetchall(); conn.close()
    items={str(r['lesson_id']):{'completed':bool(r['completed']),'score':r['score'],'updated_at':r['updated_at']} for r in rows}
    return {'completed':sum(1 for r in rows if r['completed']),'total':len(CURRICULUM),'items':items}

class CompleteBody(BaseModel):
    lesson_id: int
    score: int = Field(default=0, ge=0, le=100)

@app.post('/api/complete')
def complete(body: CompleteBody, x_telegram_init_data: str | None = Header(default=None)):
    uid=user_from_header(x_telegram_init_data)
    if not 1 <= body.lesson_id <= len(CURRICULUM): raise HTTPException(404,'Урок не найден')
    conn=db(); conn.execute('INSERT INTO progress(user_id,lesson_id,completed,score,updated_at) VALUES(?,?,1,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id,lesson_id) DO UPDATE SET completed=1,score=MAX(score,excluded.score),updated_at=CURRENT_TIMESTAMP',(uid,body.lesson_id,body.score)); conn.commit(); conn.close()
    return {'ok':True}

class RunBody(BaseModel):
    lesson_id: int
    code: str = Field(min_length=1, max_length=12000)
    stdin: str = Field(default='', max_length=4000)

@app.post('/api/run')
async def run_code(body: RunBody, request: Request, x_telegram_init_data: str | None = Header(default=None)):
    uid=user_from_header(x_telegram_init_data)
    now=time.time(); bucket=rate_buckets[uid]
    while bucket and now-bucket[0] > 60: bucket.popleft()
    if len(bucket)>=10: raise HTTPException(429,'Слишком много запусков. Подожди минуту.')
    bucket.append(now)
    if not 1 <= body.lesson_id <= len(CURRICULUM): raise HTTPException(404,'Урок не найден')
    # This service forwards code to a separate runner; it never executes submitted code on this server.
    payload={'language':'csharp','version':'6.0.0','files':[{'name':'Main.cs','content':body.code}],'stdin':body.stdin,'args':[],'compile_timeout':10000,'run_timeout':5000,'compile_memory_limit':128000000,'run_memory_limit':128000000}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp=await client.post(RUNNER_URL,json=payload)
        resp.raise_for_status(); data=resp.json()
        compile_out=data.get('compile',{}) or {}; run_out=data.get('run',{}) or {}
        output=''.join([compile_out.get('output',''),run_out.get('output','')])
        if not output: output=run_out.get('stderr') or compile_out.get('stderr') or 'Код выполнен, вывода нет.'
        conn=db(); conn.execute('INSERT INTO attempts(user_id,lesson_id,code,output) VALUES(?,?,?,?)',(uid,body.lesson_id,body.code,output[:12000])); conn.commit(); conn.close()
        return {'ok':True,'output':output[:12000],'stderr':run_out.get('stderr',''),'compile_error':bool(compile_out.get('code',0)),'runner_status':run_out.get('code')}
    except httpx.HTTPError:
        raise HTTPException(502,'Сервис запуска кода временно недоступен. Попробуй позже или проверь RUNNER_URL.')

@app.get('/api/review')
def review(x_telegram_init_data: str | None = Header(default=None)):
    uid=user_from_header(x_telegram_init_data); conn=db()
    rows=conn.execute('SELECT lesson_id,completed,score,updated_at FROM progress WHERE user_id=? AND completed=1 ORDER BY updated_at ASC',(uid,)).fetchall(); conn.close()
    # A simple spaced-repetition queue: weak/old lessons first.
    out=[]
    for r in rows:
        out.append({'lesson_id':r['lesson_id'],'title':CURRICULUM[r['lesson_id']-1]['title'],'score':r['score'],'updated_at':r['updated_at']})
    return {'items':sorted(out,key=lambda x:(x['score'],x['updated_at']))[:10]}
