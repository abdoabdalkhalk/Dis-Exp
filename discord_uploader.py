from flask import Flask, render_template, request, jsonify, Response, send_file
import requests
import time
import uuid
from threading import Thread, Lock
import json
import os
import tempfile

app = Flask(__name__)

jobs = {}
jobs_lock = Lock()

TEMP_DIR = tempfile.gettempdir()
temp_files = {}  # {job_id: [file_paths]}


def sanitize_filename(name):
    """Strip any path separators and illegal characters from a filename"""
    import re
    # Take only the last component if slashes sneak in
    name = name.replace('\\', '/').split('/')[-1]
    # Remove characters that are illegal in filenames
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = name.strip('. ')
    return name or 'file.bin'


def stream_upload_to_discord(job_id, file_urls, token, channel_id, custom_filenames=None, message_content=''):
    """Download files to temp then upload them all to Discord in one message"""
    temp_file_paths = []
    try:
        with jobs_lock:
            jobs[job_id]['status'] = 'checking'
            jobs[job_id]['progress'] = 'Checking files...'

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }

        from urllib.parse import urlparse, unquote
        filenames = []
        for i, file_url in enumerate(file_urls):
            parsed = urlparse(file_url)
            original_filename = sanitize_filename(unquote(parsed.path.split('/')[-1]))

            try:
                head_response = requests.head(file_url, headers=headers, timeout=30, allow_redirects=True)
                if not original_filename or '.' not in original_filename:
                    content_disp = head_response.headers.get('content-disposition', '')
                    if 'filename=' in content_disp:
                        original_filename = sanitize_filename(content_disp.split('filename=')[-1].strip('"\''))
                    else:
                        original_filename = f'file_{i+1}.bin'
            except Exception:
                if not original_filename or '.' not in original_filename:
                    original_filename = f'file_{i+1}.bin'

            file_extension = ('.' + original_filename.rsplit('.', 1)[-1]) if '.' in original_filename else ''

            custom_name = ''
            if custom_filenames and i < len(custom_filenames):
                custom_name = sanitize_filename((custom_filenames[i] or '').strip())

            if custom_name:
                if '.' in custom_name:
                    custom_name = custom_name.rsplit('.', 1)[0]
                filename = custom_name + file_extension
            else:
                filename = original_filename

            filenames.append(filename)

        # Download all files to temp
        with jobs_lock:
            jobs[job_id]['status'] = 'downloading'
            jobs[job_id]['progress'] = f'Downloading 0/{len(file_urls)}...'
            jobs[job_id]['last_update'] = time.time()

        for i, (file_url, filename) in enumerate(zip(file_urls, filenames)):
            with jobs_lock:
                jobs[job_id]['progress'] = f'Downloading file {i+1}/{len(file_urls)}...'

            temp_file_path = os.path.join(TEMP_DIR, f"{job_id}_{i}_{filename}")

            file_response = requests.get(
                file_url, headers=headers, stream=True, timeout=None, allow_redirects=True
            )
            file_response.raise_for_status()

            total_downloaded = 0
            with open(temp_file_path, 'wb') as f:
                for chunk in file_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_downloaded += len(chunk)
                        mb = total_downloaded / (1024 * 1024)
                        with jobs_lock:
                            jobs[job_id]['progress'] = f'File {i+1}/{len(file_urls)}: {mb:.1f}MB'
                            jobs[job_id]['last_update'] = time.time()

            temp_file_paths.append((temp_file_path, filename))

        temp_files[job_id] = temp_file_paths

        with jobs_lock:
            jobs[job_id]['status'] = 'uploading'
            jobs[job_id]['progress'] = f'Uploading {len(temp_file_paths)} file(s) to Discord...'
            jobs[job_id]['last_update'] = time.time()

        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        discord_headers = {'Authorization': token}

        files_payload = []
        file_handles = []
        for idx, (path, fname) in enumerate(temp_file_paths):
            fh = open(path, 'rb')
            file_handles.append(fh)
            files_payload.append((f'files[{idx}]', (fname, fh, 'application/octet-stream')))

        data_payload = {}
        if message_content:
            data_payload['content'] = message_content

        discord_response = requests.post(
            discord_url,
            headers=discord_headers,
            files=files_payload,
            data=data_payload,
            timeout=None
        )

        for fh in file_handles:
            fh.close()

        if discord_response.status_code == 200:
            with jobs_lock:
                jobs[job_id]['status'] = 'completed'
                jobs[job_id]['message'] = f'Successfully uploaded {len(temp_file_paths)} file(s)!'
                jobs[job_id]['progress'] = 'Done'
                jobs[job_id]['last_update'] = time.time()
        else:
            error_data = discord_response.text[:200]
            with jobs_lock:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = f'Discord error ({discord_response.status_code}): {error_data}'

    except Exception as e:
        with jobs_lock:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'Error: {str(e)[:200]}'
        import traceback
        traceback.print_exc()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': time.time()})


@app.route('/upload', methods=['POST'])
def upload():
    try:
        data = request.json
        file_urls = data.get('file_urls', [])
        token = data.get('token')
        channel_id = data.get('channel_id')
        custom_filenames = data.get('custom_filenames', [])
        message_content = data.get('message_content', '')

        if not file_urls or not token or not channel_id:
            return jsonify({'success': False, 'message': 'All fields are required'}), 400

        job_id = str(uuid.uuid4())[:8]
        with jobs_lock:
            jobs[job_id] = {
                'status': 'queued',
                'progress': 'Queued...',
                'message': '',
                'created_at': time.time(),
                'last_update': time.time(),
                'file_count': len(file_urls)
            }

        thread = Thread(
            target=stream_upload_to_discord,
            args=(job_id, file_urls, token, channel_id, custom_filenames, message_content)
        )
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'job_id': job_id, 'message': 'Upload started'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/status/<job_id>')
def status(job_id):
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'status': 'not_found'}), 404
        job_data = jobs[job_id].copy()
    return jsonify(job_data), 200, {'Cache-Control': 'no-cache'}


@app.route('/jobs')
def list_jobs():
    with jobs_lock:
        active = sum(1 for j in jobs.values() if j['status'] in ['queued', 'checking', 'downloading', 'uploading'])
        jobs_copy = {k: v.copy() for k, v in jobs.items()}
    return jsonify({'total': len(jobs_copy), 'active': active, 'jobs': jobs_copy, 'timestamp': time.time()})


@app.route('/keep-alive')
def keep_alive():
    def generate():
        try:
            for _ in range(300):
                with jobs_lock:
                    active_jobs = {
                        k: {'status': v['status'], 'progress': v['progress'], 'message': v.get('message', '')}
                        for k, v in jobs.items()
                        if v['status'] in ['queued', 'checking', 'downloading', 'uploading']
                    }
                yield f"data: {json.dumps({'timestamp': time.time(), 'active_jobs': len(active_jobs), 'jobs': active_jobs})}\n\n"
                if not active_jobs:
                    break
                time.sleep(20)
        except GeneratorExit:
            pass

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})


def cleanup_old_jobs():
    while True:
        time.sleep(300)
        now = time.time()
        with jobs_lock:
            old = [j for j, d in jobs.items() if now - d.get('last_update', d['created_at']) > 3600]
            for j in old:
                if j in temp_files:
                    for path, _ in temp_files[j]:
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                        except Exception:
                            pass
                    del temp_files[j]
                del jobs[j]


cleanup_thread = Thread(target=cleanup_old_jobs, daemon=True)
cleanup_thread.start()

app = app
