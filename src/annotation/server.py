"""Loopback-first HTTP API. Raw frames are decoded on demand, no rendered clips."""
import json
import mimetypes
from collections import Counter
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import cv2
from .export import read_frame
WEB = Path(__file__).resolve().parents[2] / 'web' / 'annotation'

def make_server(store, host='127.0.0.1', port=43128):

    @lru_cache(maxsize=48)
    def jpeg(iid, frame, crop):
        item = store.get(iid)
        image = read_frame(item['source'], frame)
        if crop:
            x1, y1, x2, y2 = item['crop']
            image = image[y1:y2, x1:x2]
        ok, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise ValueError('Frame encoding failed')
        return buffer.tobytes()

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def send(self, body, content_type='application/json', status=200):
            if not isinstance(body, bytes):
                body = json.dumps(body, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                parsed = urlparse(self.path)
                q = parse_qs(parsed.query)
                if parsed.path == '/api/items':
                    items = store.items()
                    counts = {str(p): dict(Counter((i['status'] for i in items if i['priority'] == p))) for p in range(3)}
                    self.send(dict(items=items, counts=counts))
                    return
                if parsed.path == '/api/item':
                    self.send(store.get(q['id'][0]))
                    return
                if parsed.path == '/frame':
                    iid = q['id'][0]
                    frame = int(q['frame'][0])
                    crop = q.get('crop', ['0'])[0] == '1'
                    self.send(jpeg(iid, frame, crop), 'image/jpeg')
                    return
                assets = {'/': 'index.html', '/app.js': 'app.js', '/styles.css': 'styles.css'}
                if parsed.path in assets:
                    path = WEB / assets[parsed.path]
                    self.send(path.read_bytes(), mimetypes.guess_type(path)[0] or 'text/plain')
                    return
                self.send({'error': 'not found'}, status=404)
            except (ValueError, KeyError, OSError) as e:
                self.send({'error': str(e)}, status=400)

        def do_POST(self):
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                self.send({'error': 'Cross-origin write refused'}, status=403)
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.send({'error': 'JSON required'}, status=415)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1000000:
                    raise ValueError('Invalid request size')
                payload = json.loads(self.rfile.read(length))
                if self.path != '/api/save':
                    self.send({'error': 'not found'}, status=404)
                    return
                if not isinstance(payload, dict):
                    raise ValueError('Expected JSON object')
                self.send(store.save(payload['id'], payload))
            except (ValueError, KeyError, TypeError) as e:
                self.send({'error': str(e)}, status=400)
    return ThreadingHTTPServer((host, port), Handler)
