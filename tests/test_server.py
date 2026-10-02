import importlib.util, json, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('server',Path(__file__).parents[1]/'server.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();s.DB=Path(cls.temp.name)/'test.sqlite3'
        cls.server=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler)
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
    def request(self,path,body=None,method=None,headers=None):
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers=headers or {'Content-Type':'application/json'})
        with urllib.request.urlopen(req) as r:return json.load(r)
    def test_library_persistence_update_delete(self):
        p={'paperId':'abc','title':'Sample','notes':'original'}
        self.assertEqual(self.request('/api/library',p)[0]['notes'],'original')
        self.request('/api/library',{**p,'notes':'updated'})
        self.assertEqual(self.request('/api/library')[0]['notes'],'updated')
        self.assertEqual(self.request('/api/library?id=abc',method='DELETE'),[])
    def test_search_encodes_filters(self):
        with patch.object(s,'upstream',return_value={'data':[]}) as mock:
            self.request('/api/search?query=climate&year=2020-&offset=20&unexpected=x')
            args=mock.call_args.args
            self.assertEqual(args[0],'graph/v1/paper/search');self.assertEqual(args[1]['offset'],'20');self.assertNotIn('unexpected',args[1])
    def test_recommendations(self):
        with patch.object(s,'upstream',return_value={'recommendedPapers':[]}) as mock:
            self.request('/api/recommend',{'positivePaperIds':['a'],'negativePaperIds':['b']})
            self.assertEqual(mock.call_args.args[2],{'positivePaperIds':['a'],'negativePaperIds':['b']})
    def test_foreign_origin_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/library',{'paperId':'x'},headers={'Content-Type':'application/json','Origin':'https://example.com'})
        self.assertEqual(cm.exception.code,403)
    def test_secrets_not_served(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/.env')
        self.assertEqual(cm.exception.code,404)
    def test_invalid_import(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/import',{'ids':[]})
        self.assertEqual(cm.exception.code,400)
    def test_saved_search(self):
        d=self.request('/api/searches',{'query':'biology','seen':['a']})
        self.assertEqual(d[0]['query'],'biology')
        self.assertEqual(self.request('/api/searches?id='+str(d[0]['id']),method='DELETE'),[])
    def test_render_auth_and_https(self):
        import base64
        env={'RENDER':'true','RENDER_EXTERNAL_HOSTNAME':'scholardesk.onrender.com','APP_PASSWORD':'a-test-password-with-24-chars','APP_USERNAME':'scholar'}
        with patch.dict(s.os.environ,env):
            s.validate_hosting()
            headers={'Host':'scholardesk.onrender.com','Content-Type':'application/json','Origin':'https://scholardesk.onrender.com'}
            with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/library',headers=headers)
            self.assertEqual(cm.exception.code,401)
            self.assertIn('Basic',cm.exception.headers['WWW-Authenticate'])
            self.assertEqual(self.request('/healthz'),{'status':'ok'})
            headers['Authorization']='Basic '+base64.b64encode(b'scholar:a-test-password-with-24-chars').decode()
            self.assertTrue(self.request('/api/status',headers=headers)['hosted'])
            self.request('/api/library',{'paperId':'cloud','title':'Cloud test'},headers=headers)
            self.request('/api/library?id=cloud',method='DELETE',headers=headers)
            headers['Origin']='https://evil.example'
            with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/library',{'paperId':'bad'},headers=headers)
            self.assertEqual(cm.exception.code,403)
    def test_render_requires_password(self):
        with patch.dict(s.os.environ,{'RENDER':'true','RENDER_EXTERNAL_HOSTNAME':'demo.onrender.com','APP_PASSWORD':''}):
            with self.assertRaises(ValueError):s.validate_hosting()
            with self.assertRaises(urllib.error.HTTPError) as cm:self.request('/api/status')
            self.assertEqual(cm.exception.code,503)
    def test_static(self):
        with urllib.request.urlopen(self.url) as r:self.assertIn(b'ScholarDesk',r.read())
if __name__=='__main__': unittest.main()
