from flask import Flask, render_template, request, jsonify, Response, send_file
import requests
import time
import uuid
from threading import Thread, Lock
import json
import os
import tempfile

app = Flask(__name__)

# تخزين Jobs في الذاكرة (كل مستخدم له session خاص)
jobs = {}
jobs_lock = Lock()

# مجلد temp للملفات
TEMP_DIR = tempfile.gettempdir()
temp_files = {}  # {job_id: file_path}

class ChunkedUploadWrapper:
    """Wrapper يحاكي ملف عادي لكن يقرأ chunks من stream"""
    def __init__(self, response, job_id):
        self.response = response
        self.job_id = job_id
        self.total_read = 0
        self.last_log = time.time()
        self.iterator = response.iter_content(chunk_size=8192)
        self.buffer = b''
        self.finished = False
        
    def read(self, size=-1):
        """قراءة البيانات"""
        if self.finished and not self.buffer:
            return b''
        
        try:
            if size is not None and size > 0:
                while len(self.buffer) < size and not self.finished:
                    try:
                        chunk = next(self.iterator)
                        if chunk:
                            self.buffer += chunk
                    except StopIteration:
                        self.finished = True
                        break
                
                result = self.buffer[:size]
                self.buffer = self.buffer[size:]
                
            else:
                while not self.finished:
                    try:
                        chunk = next(self.iterator)
                        if chunk:
                            self.buffer += chunk
                    except StopIteration:
                        self.finished = True
                        break
                
                result = self.buffer
                self.buffer = b''
            
            if result:
                self.total_read += len(result)
                self._log_progress()
            
            return result
            
        except Exception as e:
            print(f"[{self.job_id}] ❌ خطأ في read: {e}")
            return b''
    
    def _log_progress(self):
        """تسجيل التقدم"""
        now = time.time()
        if now - self.last_log > 5:  # كل 5 ثواني
            mb = self.total_read / (1024*1024)
            print(f"[{self.job_id}] 📤 {mb:.1f}MB")
            with jobs_lock:
                if self.job_id in jobs:
                    jobs[self.job_id]['progress'] = f'{mb:.0f}MB'
                    jobs[self.job_id]['last_update'] = now
            self.last_log = now

def stream_upload_to_discord(job_id, file_url, token, channel_id, custom_filename=None):
    """تحميل الملف إلى temp ثم رفعه للديسكورد"""
    temp_file_path = None
    try:
        with jobs_lock:
            jobs[job_id]['status'] = 'checking'
            jobs[job_id]['progress'] = 'فحص...'
        
        print(f"[{job_id}] 🔍 فحص: {file_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        
        head_response = None
        original_filename = file_url.split('/')[-1].split('?')[0]
        
        try:
            head_response = requests.head(file_url, headers=headers, timeout=30, allow_redirects=True)
        except Exception as e:
            print(f"[{job_id}] ⚠️ تحذير HEAD request: {e}")
        
        if not original_filename or '.' not in original_filename:
            if head_response:
                content_disp = head_response.headers.get('content-disposition', '')
                if 'filename=' in content_disp:
                    original_filename = content_disp.split('filename=')[-1].strip('"\'')
                else:
                    original_filename = 'file.bin'
            else:
                original_filename = 'file.bin'
        
        file_extension = ''
        if '.' in original_filename:
            file_extension = '.' + original_filename.split('.')[-1]
        
        if custom_filename and custom_filename.strip():
            custom_filename = custom_filename.strip()
            if '.' in custom_filename:
                custom_filename = '.'.join(custom_filename.split('.')[:-1])
            filename = custom_filename + file_extension
        else:
            filename = original_filename
        
        print(f"[{job_id}] 📄 اسم: {filename}")
        
        # تحميل الملف إلى temp
        with jobs_lock:
            jobs[job_id]['status'] = 'downloading'
            jobs[job_id]['progress'] = 'تحميل إلى temp...'
            jobs[job_id]['last_update'] = time.time()
        
        print(f"[{job_id}] ⬇️ بدء التحميل إلى temp...")
        
        temp_file_path = os.path.join(TEMP_DIR, f"{job_id}_{filename}")
        
        file_response = requests.get(
            file_url,
            headers=headers,
            stream=True,
            timeout=None,
            allow_redirects=True
        )
        file_response.raise_for_status()
        
        # حفظ الملف في temp
        total_downloaded = 0
        with open(temp_file_path, 'wb') as f:
            for chunk in file_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_downloaded += len(chunk)
                    
                    # تحديث التقدم
                    mb = total_downloaded / (1024*1024)
                    with jobs_lock:
                        jobs[job_id]['progress'] = f'⬇️ {mb:.1f}MB'
                        jobs[job_id]['last_update'] = time.time()
        
        # حفظ مسار الملف
        temp_files[job_id] = temp_file_path
        
        download_url = f'/download/{job_id}'
        
        with jobs_lock:
            jobs[job_id]['status'] = 'temp_ready'
            jobs[job_id]['progress'] = f'✅ تم التحميل - {total_downloaded/(1024*1024):.1f}MB'
            jobs[job_id]['download_url'] = download_url
            jobs[job_id]['filename'] = filename
            jobs[job_id]['last_update'] = time.time()
        
        print(f"[{job_id}] ✅ الملف جاهز في temp: {temp_file_path}")
        print(f"[{job_id}] 🔗 رابط التحميل: {download_url}")
        
        # الآن رفع الملف للديسكورد
        with jobs_lock:
            jobs[job_id]['status'] = 'uploading'
            jobs[job_id]['progress'] = 'رفع للديسكورد...'
            jobs[job_id]['last_update'] = time.time()
        
        print(f"[{job_id}] 📤 بدء الرفع للديسكورد...")
        
        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        discord_headers = {'Authorization': token}
        
        with open(temp_file_path, 'rb') as f:
            discord_response = requests.post(
                discord_url,
                headers=discord_headers,
                files={'file': (filename, f, 'application/octet-stream')},
                timeout=None
            )
        
        if discord_response.status_code == 200:
            with jobs_lock:
                jobs[job_id]['status'] = 'completed'
                jobs[job_id]['message'] = f'✅ تم الرفع للديسكورد!'
                jobs[job_id]['progress'] = '✅'
                jobs[job_id]['last_update'] = time.time()
            print(f"[{job_id}] 🎉 SUCCESS!")
        else:
            error_data = discord_response.text[:200]
            with jobs_lock:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = f'❌ خطأ ({discord_response.status_code})'
            print(f"[{job_id}] ❌ Discord: {error_data}")
            
    except Exception as e:
        with jobs_lock:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'❌ {str(e)[:100]}'
        print(f"[{job_id}] ❌ Error: {e}")
        import traceback
        traceback.print_exc()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': time.time()})

@app.route('/download/<job_id>')
def download_file(job_id):
    """تحميل الملف من temp"""
    if job_id not in temp_files:
        return jsonify({'error': 'الملف غير موجود'}), 404
    
    file_path = temp_files[job_id]
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'الملف غير موجود'}), 404
    
    with jobs_lock:
        filename = jobs.get(job_id, {}).get('filename', 'file')
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename
    )

@app.route('/upload', methods=['POST'])
def upload():
    """بدء عملية الرفع"""
    try:
        data = request.json
        file_url = data.get('file_url')
        token = data.get('token')
        channel_id = data.get('channel_id')
        custom_filename = data.get('custom_filename', '')
        
        if not all([file_url, token, channel_id]):
            return jsonify({'success': False, 'message': 'جميع الحقول مطلوبة'}), 400
        
        job_id = str(uuid.uuid4())[:8]
        with jobs_lock:
            jobs[job_id] = {
                'status': 'queued',
                'progress': 'انتظار...',
                'message': '',
                'created_at': time.time(),
                'last_update': time.time(),
                'download_url': None,
                'filename': None
            }
        
        thread = Thread(
            target=stream_upload_to_discord,
            args=(job_id, file_url, token, channel_id, custom_filename)
        )
        thread.daemon = True
        thread.start()
        
        print(f"[{job_id}] 🎬 Job started (TEMP MODE)")
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'بدأ التحميل 🚀'
        }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/status/<job_id>')
def status(job_id):
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'status': 'not_found'}), 404
        job_data = jobs[job_id].copy()
    
    return jsonify(job_data), 200, {
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    }

@app.route('/jobs')
def list_jobs():
    with jobs_lock:
        active = sum(1 for j in jobs.values() if j['status'] in ['queued', 'checking', 'downloading', 'uploading'])
        jobs_copy = {k: v.copy() for k, v in jobs.items()}
    return jsonify({
        'total': len(jobs_copy),
        'active': active,
        'jobs': jobs_copy,
        'timestamp': time.time()
    })

@app.route('/keep-alive')
def keep_alive():
    def generate():
        try:
            for i in range(300):
                with jobs_lock:
                    active_jobs = {
                        k: {
                            'status': v['status'], 
                            'progress': v['progress'],
                            'download_url': v.get('download_url'),
                            'filename': v.get('filename')
                        }
                        for k, v in jobs.items()
                        if v['status'] in ['queued', 'checking', 'downloading', 'temp_ready', 'uploading']
                    }
                
                data = {
                    'timestamp': time.time(),
                    'active_jobs': len(active_jobs),
                    'jobs': active_jobs
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                
                if not active_jobs:
                    break
                
                time.sleep(20)
        except GeneratorExit:
            pass
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

def cleanup_old_jobs():
    """تنظيف الـ jobs القديمة"""
    while True:
        time.sleep(300)
        now = time.time()
        with jobs_lock:
            old = [j for j, d in jobs.items() if now - d.get('last_update', d['created_at']) > 3600]
            for j in old:
                # حذف الملف من temp
                if j in temp_files:
                    try:
                        if os.path.exists(temp_files[j]):
                            os.remove(temp_files[j])
                        del temp_files[j]
                    except:
                        pass
                del jobs[j]
                print(f"🗑️ Cleaned: {j}")

cleanup_thread = Thread(target=cleanup_old_jobs, daemon=True)
cleanup_thread.start()

# للتوافق مع Vercel
app = app
