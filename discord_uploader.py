from flask import Flask, render_template, request, jsonify, Response
import requests
import time
import uuid
import os
import re
import json
import tempfile
from threading import Thread, Lock
from urllib.parse import urlparse, unquote

app = Flask(__name__)

jobs: dict = {}
jobs_lock = Lock()

TEMP_DIR = tempfile.gettempdir()
CHUNK = 8 * 1024 * 1024
DL_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Accept-Encoding': 'identity',
}


def sanitize(name: str) -> str:
    name = name.replace('\\', '/').split('/')[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    return name.strip('. ') or 'file.bin'


def get_mime(name: str) -> str:
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    return {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'gif': 'image/gif',  'webp': 'image/webp', 'bmp': 'image/bmp',
        'svg': 'image/svg+xml',
        'mp4': 'video/mp4',  'mov': 'video/quicktime', 'webm': 'video/webm',
        'mp3': 'audio/mpeg', 'wav': 'audio/wav',
        'pdf': 'application/pdf',
        'zip': 'application/zip', 'rar': 'application/x-rar-compressed',
    }.get(ext, 'application/octet-stream')


def resolve_url_meta(file_url: str, fallback_idx: int) -> tuple[str, int | None]:
    parsed = urlparse(file_url)
    filename = sanitize(unquote(parsed.path.split('/')[-1]))

    content_length = None
    try:
        hr = requests.head(file_url, headers=DL_HEADERS, timeout=20, allow_redirects=True)
        cl = hr.headers.get('content-length')
        if cl and cl.isdigit():
            content_length = int(cl)
        if not filename or '.' not in filename:
            cd = hr.headers.get('content-disposition', '')
            if 'filename=' in cd:
                filename = sanitize(cd.split('filename=')[-1].strip('"\''))
    except Exception:
        pass

    if not filename or '.' not in filename:
        filename = f'file_{fallback_idx + 1}.bin'

    return filename, content_length


def set_progress(job_id: str, status: str, progress: str):
    with jobs_lock:
        jobs[job_id]['status']      = status
        jobs[job_id]['progress']    = progress
        jobs[job_id]['last_update'] = time.time()


class ProgressStream:
    def __init__(self, resp, job_id, file_idx, total_files, total_bytes):
        self.resp        = resp
        self.job_id      = job_id
        self.file_idx    = file_idx
        self.total_files = total_files
        self.total_bytes = total_bytes
        self.read_bytes  = 0
        self.last_update = 0.0
        self._iter       = resp.iter_content(chunk_size=CHUNK)
        self._buf        = b''
        self._done       = False

    def read(self, size=-1):
        if self._done and not self._buf:
            return b''
        try:
            while not self._done and (size < 0 or len(self._buf) < size):
                chunk = next(self._iter)
                if chunk:
                    self._buf += chunk
        except StopIteration:
            self._done = True

        if size < 0:
            out, self._buf = self._buf, b''
        else:
            out, self._buf = self._buf[:size], self._buf[size:]

        if out:
            self.read_bytes += len(out)
            self._maybe_update()
        return out

    def _maybe_update(self):
        now = time.time()
        if now - self.last_update < 0.8:
            return
        self.last_update = now
        mb = self.read_bytes / (1024 * 1024)
        if self.total_bytes:
            pct = self.read_bytes / self.total_bytes * 100
            msg = f'File {self.file_idx+1}/{self.total_files}: {mb:.1f} MB ({pct:.0f}%)'
        else:
            msg = f'File {self.file_idx+1}/{self.total_files}: {mb:.1f} MB'
        with jobs_lock:
            jobs[self.job_id]['progress']    = msg
            jobs[self.job_id]['last_update'] = now


def upload_worker(job_id: str, items: list, token: str,
                  channel_id: str, message_content: str = ''):
    local_temps = []
    try:
        total = len(items)
        set_progress(job_id, 'preparing', 'Resolving files...')

        resolved = []
        for i, item in enumerate(items):
            if item['type'] == 'local':
                resolved.append({
                    'kind':     'local',
                    'path':     item['path'],
                    'filename': item['filename'],
                    'size':     os.path.getsize(item['path']),
                })
                local_temps.append(item['path'])

            else:
                raw_url    = item['url']
                custom     = sanitize((item.get('custom_name') or '').strip())
                fname, cl  = resolve_url_meta(raw_url, i)

                if custom:
                    ext   = ('.' + fname.rsplit('.', 1)[-1]) if '.' in fname else ''
                    stem  = custom.rsplit('.', 1)[0] if '.' in custom else custom
                    fname = stem + ext

                resolved.append({
                    'kind':    'url',
                    'url':     raw_url,
                    'filename': fname,
                    'size':    cl,
                })

        set_progress(job_id, 'uploading', f'Streaming {total} file(s) → Discord...')

        discord_url     = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        discord_headers = {'Authorization': token}

        active_streams = []
        active_handles = []
        files_payload  = []

        for idx, r in enumerate(resolved):
            mime = get_mime(r['filename'])
            if r['kind'] == 'local':
                fh = open(r['path'], 'rb')
                active_handles.append(fh)
                files_payload.append(
                    (f'files[{idx}]', (r['filename'], fh, mime))
                )
            else:
                set_progress(job_id, 'uploading',
                             f'Opening stream {idx+1}/{total}: {r["filename"]}')
                resp = requests.get(
                    r['url'], headers=DL_HEADERS,
                    stream=True, timeout=None, allow_redirects=True
                )
                resp.raise_for_status()
                ps = ProgressStream(resp, job_id, idx, total, r['size'])
                active_streams.append(ps)
                files_payload.append(
                    (f'files[{idx}]', (r['filename'], ps, mime))
                )

        data_payload = {}
        if message_content:
            data_payload['content'] = message_content

        discord_resp = requests.post(
            discord_url,
            headers=discord_headers,
            files=files_payload,
            data=data_payload,
            timeout=None
        )

        for fh in active_handles:
            try: fh.close()
            except Exception: pass
        for ps in active_streams:
            try: ps.resp.close()
            except Exception: pass

        if discord_resp.status_code == 200:
            with jobs_lock:
                jobs[job_id]['status']      = 'completed'
                jobs[job_id]['message']     = f'Uploaded {total} file(s) successfully!'
                jobs[job_id]['progress']    = 'Done'
                jobs[job_id]['last_update'] = time.time()
        else:
            with jobs_lock:
                jobs[job_id]['status']      = 'failed'
                jobs[job_id]['message']     = (
                    f'Discord error {discord_resp.status_code}: {discord_resp.text[:300]}'
                )
                jobs[job_id]['last_update'] = time.time()

    except Exception as e:
        import traceback; traceback.print_exc()
        with jobs_lock:
            jobs[job_id]['status']      = 'failed'
            jobs[job_id]['message']     = f'Error: {str(e)[:300]}'
            jobs[job_id]['last_update'] = time.time()

    finally:
        for path in local_temps:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': time.time()})


@app.route('/upload', methods=['POST'])
def upload():
    try:
        token           = request.form.get('token', '').strip()
        channel_id      = request.form.get('channel_id', '').strip()
        message_content = request.form.get('message_content', '').strip()
        items_meta      = json.loads(request.form.get('items', '[]'))

        if not token or not channel_id:
            return jsonify({'success': False, 'message': 'Token and Channel ID are required'}), 400
        if not items_meta:
            return jsonify({'success': False, 'message': 'No files specified'}), 400

        job_id = str(uuid.uuid4())[:8]

        resolved_items = []
        for meta in items_meta:
            if meta['type'] == 'local':
                fobj = request.files.get(f"file_{meta['index']}")
                if not fobj:
                    return jsonify({'success': False,
                                    'message': f'Missing file for index {meta["index"]}'}), 400
                fname     = sanitize(fobj.filename or f'upload_{meta["index"]}.bin')
                tmp_path  = os.path.join(TEMP_DIR, f"{job_id}_local_{meta['index']}_{fname}")
                fobj.save(tmp_path)
                resolved_items.append({'type': 'local', 'path': tmp_path, 'filename': fname})
            else:
                resolved_items.append({
                    'type':        'url',
                    'url':         meta.get('url', ''),
                    'custom_name': meta.get('custom_name', ''),
                })

        with jobs_lock:
            jobs[job_id] = {
                'status':      'queued',
                'progress':    'Queued...',
                'message':     '',
                'created_at':  time.time(),
                'last_update': time.time(),
                'file_count':  len(resolved_items),
            }

        Thread(
            target=upload_worker,
            args=(job_id, resolved_items, token, channel_id, message_content),
            daemon=True
        ).start()

        return jsonify({'success': True, 'job_id': job_id}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/status/<job_id>')
def status(job_id):
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'status': 'not_found'}), 404
        data = jobs[job_id].copy()
    return jsonify(data), 200, {'Cache-Control': 'no-cache'}


@app.route('/jobs')
def list_jobs():
    with jobs_lock:
        active = sum(1 for j in jobs.values()
                     if j['status'] in ('queued', 'preparing', 'uploading'))
        snap = {k: v.copy() for k, v in jobs.items()}
    return jsonify({'total': len(snap), 'active': active,
                    'jobs': snap, 'timestamp': time.time()})


@app.route('/keep-alive')
def keep_alive():
    def generate():
        try:
            for _ in range(300):
                with jobs_lock:
                    active = {
                        k: {'status': v['status'], 'progress': v['progress'],
                            'message': v.get('message', '')}
                        for k, v in jobs.items()
                        if v['status'] in ('queued', 'preparing', 'uploading')
                    }
                yield f"data: {json.dumps({'ts': time.time(), 'active_jobs': len(active), 'jobs': active})}\n\n"
                if not active:
                    break
                time.sleep(15)
        except GeneratorExit:
            pass

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache',
                             'X-Accel-Buffering': 'no',
                             'Connection': 'keep-alive'})


def _cleanup_loop():
    while True:
        time.sleep(300)
        cutoff = time.time() - 3600
        with jobs_lock:
            old = [jid for jid, d in jobs.items()
                   if d.get('last_update', d['created_at']) < cutoff]
            for jid in old:
                del jobs[jid]


Thread(target=_cleanup_loop, daemon=True).start()

app = app
