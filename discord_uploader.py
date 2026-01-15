from flask import Flask, render_template, request, jsonify, Response
import requests
import os
import time
import uuid
from threading import Thread, Lock
import json

app = Flask(__name__)

jobs = {}
jobs_lock = Lock()

class StreamingFile:
    """ملف وهمي يقرأ من الـ stream مباشرة"""
    def __init__(self, response, filename, job_id):
        self.response = response
        self.filename = filename
        self.job_id = job_id
        self.total_read = 0
        self.last_log = time.time()
        
    def read(self, size=-1):
        """قراءة من الـ stream"""
        try:
            chunk = self.response.raw.read(size if size > 0 else 8192)
            if chunk:
                self.total_read += len(chunk)
                
                # تسجيل التقدم كل 10 ثواني
                now = time.time()
                if now - self.last_log > 10:
                    mb = self.total_read / (1024*1024)
                    print(f"[{self.job_id}] 📤 تم رفع: {mb:.1f}MB")
                    with jobs_lock:
                        if self.job_id in jobs:
                            jobs[self.job_id]['progress'] = f'رفع {mb:.0f}MB...'
                            jobs[self.job_id]['last_update'] = now
                    self.last_log = now
            
            return chunk
        except Exception as e:
            print(f"[{self.job_id}] ❌ خطأ في القراءة: {e}")
            return b''

def stream_upload_to_discord(job_id, file_url, token, channel_id, custom_filename=None):
    """رفع streaming مباشر بدون حفظ الملف"""
    try:
        with jobs_lock:
            jobs[job_id]['status'] = 'checking'
            jobs[job_id]['progress'] = 'فحص الملف...'
        
        print(f"[{job_id}] 🔍 فحص: {file_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        
        # فحص الحجم
        head_response = None
        total_size = 0
        try:
            head_response = requests.head(file_url, headers=headers, timeout=30, allow_redirects=True)
            total_size = int(head_response.headers.get('content-length', 0))
        except Exception as e:
            print(f"[{job_id}] ⚠️ تحذير HEAD request: {e}")
            total_size = 0
        
        if total_size > 0:
            size_mb = total_size / (1024*1024)
            print(f"[{job_id}] 📦 حجم: {size_mb:.2f} MB")
            
            # تحقق من الحد الأقصى
            if size_mb > 500:
                with jobs_lock:
                    jobs[job_id]['status'] = 'failed'
                    jobs[job_id]['message'] = f'❌ الملف كبير ({size_mb:.1f}MB). الحد الأقصى 500MB'
                return
            
            with jobs_lock:
                jobs[job_id]['progress'] = f'حجم الملف: {size_mb:.1f}MB'
        
        # الحصول على اسم الملف
        original_filename = file_url.split('/')[-1].split('?')[0]
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
        
        # بدء الـ streaming
        with jobs_lock:
            jobs[job_id]['status'] = 'uploading'
            jobs[job_id]['progress'] = 'بدء الرفع المباشر...'
            jobs[job_id]['last_update'] = time.time()
        
        print(f"[{job_id}] 🚀 بدء streaming upload...")
        
        start_time = time.time()
        
        # فتح stream من الرابط
        file_response = requests.get(
            file_url,
            headers=headers,
            stream=True,
            timeout=None,
            allow_redirects=True
        )
        file_response.raise_for_status()
        
        # إنشاء ملف streaming
        streaming_file = StreamingFile(file_response, filename, job_id)
        
        # رفع مباشر لـ Discord
        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        discord_headers = {'Authorization': token}
        
        # استخدام الطريقة البسيطة مباشرة (أكثر استقراراً)
        print(f"[{job_id}] 📤 استخدام Simple Upload (أكثر استقراراً)")
        
        discord_response = requests.post(
            discord_url,
            headers=discord_headers,
            files={'file': (filename, streaming_file, 'application/octet-stream')},
            timeout=None
        )
        
        upload_time = time.time() - start_time
        uploaded_mb = streaming_file.total_read / (1024*1024)
        
        print(f"[{job_id}] ⏱️ وقت الرفع: {upload_time/60:.1f} دقيقة")
        print(f"[{job_id}] 📊 تم رفع: {uploaded_mb:.1f}MB")
        
        if discord_response.status_code == 200:
            with jobs_lock:
                jobs[job_id]['status'] = 'completed'
                jobs[job_id]['message'] = f'✅ تم رفع "{filename}" ({uploaded_mb:.1f}MB) في {upload_time/60:.1f} دقيقة!'
                jobs[job_id]['progress'] = 'اكتمل!'
                jobs[job_id]['last_update'] = time.time()
            print(f"[{job_id}] 🎉 SUCCESS!")
        else:
            error_data = discord_response.text[:300]
            with jobs_lock:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = f'❌ خطأ Discord ({discord_response.status_code}): {error_data}'
            print(f"[{job_id}] ❌ Discord: {error_data}")
            
    except Exception as e:
        with jobs_lock:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'❌ خطأ: {str(e)[:200]}'
        print(f"[{job_id}] ❌ Error: {e}")
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
                'progress': 'في الانتظار...',
                'message': '',
                'created_at': time.time(),
                'last_update': time.time()
            }
        
        thread = Thread(
            target=stream_upload_to_discord,
            args=(job_id, file_url, token, channel_id, custom_filename)
        )
        thread.daemon = True
        thread.start()
        
        print(f"[{job_id}] 🎬 Job started (STREAMING MODE)")
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'بدء الرفع المباشر! (استخدام ذاكرة منخفض جداً) 🚀'
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
    return jsonify(job_data)

@app.route('/jobs')
def list_jobs():
    with jobs_lock:
        active = sum(1 for j in jobs.values() if j['status'] in ['queued', 'checking', 'uploading'])
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
                        k: {'status': v['status'], 'progress': v['progress']}
                        for k, v in jobs.items()
                        if v['status'] in ['queued', 'checking', 'uploading']
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
        time.sleep(300)  # كل 5 دقائق
        now = time.time()
        with jobs_lock:
            old = [j for j, d in jobs.items() if now - d.get('last_update', d['created_at']) > 3600]
            for j in old:
                del jobs[j]
                print(f"🗑️ Cleaned: {j}")

cleanup_thread = Thread(target=cleanup_old_jobs, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
