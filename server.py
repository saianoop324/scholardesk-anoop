"""Local research workspace. Python 3.11+, no third-party dependencies."""
import base64, binascii, hmac, json, os, sqlite3, threading, time, urllib.parse, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent
for line in (ROOT / '.env').read_text().splitlines() if (ROOT / '.env').exists() else []:
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('\"\''))
DB = Path(os.getenv('DATABASE_PATH', str(ROOT / 'research.sqlite3')))

def cloud_host():
    return os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip().lower()

def validate_hosting():
    if os.getenv('RENDER') or cloud_host():
        if not cloud_host():
            raise ValueError('RENDER_EXTERNAL_HOSTNAME is required on Render.')
        if len(os.getenv('APP_PASSWORD', '')) < 16:
            raise ValueError('Set APP_PASSWORD to a unique password of at least 16 characters on Render.')
FIELDS = 'title,authors,year,venue,abstract,citationCount,influentialCitationCount,openAccessPdf,url,externalIds,publicationDate'
lock = threading.Lock()
last_request = 0
cache = {}

@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS library (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
            yield db
    finally:
        db.close()

def upstream(path, params=None, body=None):
    global last_request
    url = 'https://api.semanticscholar.org/' + path
    if params: url += '?' + urllib.parse.urlencode(params)
    key = url + json.dumps(body, sort_keys=True)
    with lock:
        if key in cache and time.monotonic() - cache[key][0] < 600:
            return cache[key][1]
        for attempt in range(3):
            time.sleep(max(0, 1.05 - (time.monotonic() - last_request)))
            headers = {'Accept': 'application/json', 'User-Agent': 'ScholarDesk/1.0'}
            if os.getenv('SEMANTIC_SCHOLAR_API_KEY'): headers['x-api-key'] = os.environ['SEMANTIC_SCHOLAR_API_KEY']
            if body is not None: headers['Content-Type'] = 'application/json'
            request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
            last_request = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=30) as response: result = json.load(response)
                if len(cache) > 300: cache.clear()
                cache[key] = (time.monotonic(), result)
                return result
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 2:
                    time.sleep(min(10, 2 ** (attempt + 1)))
                    continue
                messages = {401:'API key was rejected. Check your .env file and restart.',403:'Access denied by Semantic Scholar. Check your key and endpoint access.',404:'This research record was not found.',429:'Semantic Scholar is busy or rate limited. Please try again shortly.'}
                raise ValueError(messages.get(e.code, f'Semantic Scholar returned HTTP {e.code}. Try a simpler query.')) from e
            except (urllib.error.URLError, TimeoutError) as e:
                raise ValueError('Could not reach Semantic Scholar. Check your connection and try again.') from e

def paper_id(value):
    if not value or len(value) > 300: raise ValueError('Enter a valid paper identifier.')
    return urllib.parse.quote(value, safe='')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send(self, data, status=200, content_type='application/json'):
        payload = json.dumps(data).encode() if content_type == 'application/json' else data
        self.send_response(status)
        if status == 401:
            self.send_header('WWW-Authenticate', 'Basic realm="ScholarDesk", charset="UTF-8"')
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(payload)
    def do_GET(self): self.route()
    def do_POST(self): self.route()
    def do_DELETE(self): self.route()
    def route(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == '/healthz' and self.command == 'GET':
                return self.send({'status':'ok'})
            host = self.headers.get('Host','').lower()
            hostname = urllib.parse.urlsplit('http://' + host).hostname
            allowed = {'localhost','127.0.0.1'}
            if cloud_host(): allowed.add(cloud_host())
            if hostname not in allowed:
                return self.send({'error':'Host rejected.'},403)
            password = os.getenv('APP_PASSWORD', '')
            if (os.getenv('RENDER') or cloud_host()) and len(password) < 16:
                return self.send({'error':'Hosting password is not configured.'},503)
            if password:
                credentials = ''
                try:
                    scheme, token = self.headers.get('Authorization','').split(' ',1)
                    if scheme.lower() == 'basic':
                        credentials = base64.b64decode(token, validate=True).decode('utf-8')
                except (ValueError, UnicodeError, binascii.Error): pass
                expected = os.getenv('APP_USERNAME','scholar') + ':' + password
                if not hmac.compare_digest(credentials.encode(), expected.encode()):
                    return self.send({'error':'Sign in with your ScholarDesk username and password.'},401)
            if self.command != 'GET':
                origin = self.headers.get('Origin')
                expected_origin = ('https://' + cloud_host()) if cloud_host() else ('http://' + host)
                if origin and origin != expected_origin: return self.send({'error':'Origin rejected.'},403)
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json': return self.send({'error':'JSON required.'},415)
            q = {k:v[0] for k,v in urllib.parse.parse_qs(parsed.query).items()}
            body = {}
            if self.command == 'POST':
                length = int(self.headers.get('Content-Length',0))
                if length < 0 or length > 2_000_000: return self.send({'error':'Request too large.'},413)
                body = json.loads(self.rfile.read(length) or '{}')
            if path == '/api/status': return self.send({'keyConfigured':bool(os.getenv('SEMANTIC_SCHOLAR_API_KEY')), 'hosted':bool(cloud_host())})
            if path == '/api/library':
                with connect() as db:
                    if self.command == 'POST':
                        if not isinstance(body.get('paperId'),str): raise ValueError('Paper ID required.')
                        db.execute('INSERT OR REPLACE INTO library VALUES (?,?)',(body['paperId'],json.dumps(body)))
                    elif self.command == 'DELETE': db.execute('DELETE FROM library WHERE id=?',(q.get('id'),))
                    data = [json.loads(row[0]) for row in db.execute('SELECT data FROM library ORDER BY rowid DESC')]
                return self.send(data)
            if path == '/api/searches':
                with connect() as db:
                    if self.command == 'POST': db.execute('INSERT INTO searches(data) VALUES (?)',(json.dumps(body),))
                    elif self.command == 'DELETE': db.execute('DELETE FROM searches WHERE id=?',(q.get('id'),))
                    data = [dict(json.loads(row[1]),id=row[0]) for row in db.execute('SELECT id,data FROM searches')]
                return self.send(data)
            if path == '/api/search':
                params = {k:v for k,v in q.items() if k in ('query','year','fieldsOfStudy','venue','minCitationCount','openAccessPdf','publicationTypes','offset')}
                if not params.get('query','').strip(): raise ValueError('Enter a search term.')
                params.update(fields=FIELDS,limit=20)
                return self.send(upstream('graph/v1/paper/search',params))
            if path == '/api/paper': return self.send(upstream('graph/v1/paper/'+paper_id(q.get('id')),{'fields':FIELDS+',tldr,publicationTypes,referenceCount'}))
            if path == '/api/links':
                kind = q.get('kind','references')
                if kind not in ('references','citations'): raise ValueError('Invalid relationship.')
                return self.send(upstream('graph/v1/paper/'+paper_id(q.get('id'))+'/'+kind,{'fields':FIELDS+',contexts,intents,isInfluential','limit':40,'offset':q.get('offset',0)}))
            if path == '/api/recommend':
                positive = body.get('positivePaperIds',[]) if self.command == 'POST' else [q.get('id')]
                if not positive or len(positive)>100: raise ValueError('Select between 1 and 100 seed papers.')
                return self.send(upstream('recommendations/v1/papers',{'fields':FIELDS,'limit':30},{'positivePaperIds':positive,'negativePaperIds':body.get('negativePaperIds',[])}))
            if path == '/api/authors': return self.send(upstream('graph/v1/author/search',{'query':q.get('query',''),'fields':'name,affiliations,paperCount,citationCount,hIndex','limit':20}))
            if path == '/api/author': return self.send(upstream('graph/v1/author/'+paper_id(q.get('id')),{'fields':'name,affiliations,paperCount,citationCount,hIndex,url'}))
            if path == '/api/author-papers': return self.send(upstream('graph/v1/author/'+paper_id(q.get('id'))+'/papers',{'fields':FIELDS,'limit':40,'offset':q.get('offset',0)}))
            if path == '/api/import':
                ids = body.get('ids',[])
                if not isinstance(ids,list) or not 1<=len(ids)<=100: raise ValueError('Import 1–100 identifiers at a time.')
                return self.send(upstream('graph/v1/paper/batch',{'fields':FIELDS},{'ids':ids}))
            if path == '/api/datasets': return self.send(upstream('datasets/v1/release/latest'))
            if path.startswith('/api/'): return self.send({'error':'Unknown endpoint.'},404)
            files = {'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
            if path not in files: return self.send({'error':'Not found'},404)
            name,mime = files[path]
            self.send((ROOT/'static'/name).read_bytes(),content_type=mime)
        except (BrokenPipeError, ConnectionResetError): pass
        except (ValueError, TypeError, KeyError) as e: self.send({'error':str(e)},400)
        except Exception: self.send({'error':'An unexpected server error occurred.'},500)

if __name__ == '__main__':
    validate_hosting()
    port = int(os.getenv('PORT','8000'))
    bind = '0.0.0.0' if cloud_host() else '127.0.0.1'
    server = ThreadingHTTPServer((bind,port),Handler)
    address = 'https://' + cloud_host() if cloud_host() else f'http://localhost:{port}'
    print(f'ScholarDesk is ready at {address}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
