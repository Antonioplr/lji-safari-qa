"""Serves the live site on 127.0.0.1:8080 and adds a tiny error recorder to HTML pages, so Safari's early
errors (thrown before WebDriver attaches) are captured in window.__qaErrors."""
import http.server, urllib.request, sys
ORIGIN = sys.argv[1] if len(sys.argv) > 1 else 'https://web-production-fee40.up.railway.app'
REC = (b"<script>window.__qaErrors=[];addEventListener('error',function(e){__qaErrors.push('error: '+(e.message||e.type)+' @ '"
       b"+(e.filename||(e.target&&(e.target.src||e.target.href))||'')+':'+(e.lineno||''))},true);addEventListener('unhandledrejection',"
       b"function(e){__qaErrors.push('rejection: '+String(e.reason&&e.reason.stack||e.reason))});</script>")
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            req = urllib.request.Request(ORIGIN + self.path, headers={'User-Agent': self.headers.get('User-Agent', 'qa'), 'Accept': self.headers.get('Accept', '*/*')})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read(); ctype = r.headers.get('Content-Type', 'application/octet-stream'); code = r.status
        except urllib.error.HTTPError as e:
            body = e.read(); ctype = e.headers.get('Content-Type', 'text/plain'); code = e.code
        if 'text/html' in ctype:
            body = body.replace(b'<head>', b'<head>' + REC, 1)
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(('127.0.0.1', 8080), H).serve_forever()
