"""Optional: PYTHONPATH=/tmp/scholardesk-browser python3 tests/browser_smoke.py"""
import importlib.util,json,tempfile,threading
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
spec=importlib.util.spec_from_file_location('server',Path(__file__).parents[1]/'server.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
paper={'paperId':'test-paper','title':'A Test of Research Discovery','year':2024,'authors':[{'authorId':'author1','name':'Test Researcher'}],'abstract':'A carefully controlled paper used to test the research workspace.','citationCount':42,'influentialCitationCount':3,'venue':'Research Journal','url':'https://www.semanticscholar.org/paper/test-paper','externalIds':{'DOI':'10.1000/test'},'tldr':{'text':'A test summary.'}}
with tempfile.TemporaryDirectory() as temp:
 s.DB=Path(temp)/'test.sqlite3';server=s.ThreadingHTTPServer(('127.0.0.1',8001),s.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   def route(r):
    path=r.request.url.split('/api/')[-1].split('?')[0]
    data={'search':{'data':[paper],'total':1},'paper':paper,'recommend':{'recommendedPapers':[paper]},'links':{'data':[{'citedPaper':paper}]},'import':[paper]}.get(path)
    if data is not None:r.fulfill(json=data)
    else:r.continue_()
   page.route('**/api/**',route);page.goto('http://127.0.0.1:8001');page.locator('#query').fill('research');page.locator('#search-form').evaluate('(form)=>form.requestSubmit()');page.locator('[data-save]').click();expect(page.locator("#library-count")).to_have_text("1")
   page.locator('[data-select]').check();page.locator('[data-view="compare"]').click();page.locator('table').wait_for();assert page.locator('table').inner_text().count('A Test of Research Discovery')==1
   page.locator('[data-view="library"]').click();page.locator('[data-notes]').click();page.locator('#project').fill('My thesis');page.locator('#notes').fill('Evidence verified');page.locator('#notes-form').evaluate('(form)=>form.requestSubmit()');expect(page.locator("#modal")).not_to_be_visible()
   page.locator('[data-status]').select_option('Read');page.wait_for_timeout(200);page.reload();page.locator('[data-view="library"]').click();assert page.locator('[data-status]').input_value()=='Read';assert 'My thesis' in page.locator('#content').inner_text()
   with page.expect_download() as dl:page.locator('#export').click()
   assert dl.value.suggested_filename.endswith('.json')
   page.locator('[data-paper]').click();page.locator('[data-graph]').click();page.locator('svg').wait_for();page.locator('#close-modal').click();page.locator('[data-view="discover"]').click();page.screenshot(path='/tmp/scholardesk-desktop.png',full_page=True)
   page.set_viewport_size({'width':390,'height':844});page.screenshot(path='/tmp/scholardesk-mobile.png',full_page=True);assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
   assert not errors,errors
   print('Browser checks passed: search, save, comparison, notes, persistence, export, graph, mobile overflow; no JavaScript errors.')
   browser.close()
 finally:server.shutdown();server.server_close()
