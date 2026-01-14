from flask import Flask, render_template, request, jsonify
import requests
import os
import time
import uuid
from threading import Thread

app = Flask(__name__)

# تخزين حالة الـ Jobs في الذاكرة
jobs = {}

def download_and_upload(job_id, file_url, token, channel_id):
    """تحميل الملف ورفعه إلى Discord"""
    try:
        jobs[job_id]['status'] = 'downloading'
        jobs[job_id]['progress'] = 'بدء التحميل...'
        
        print(f"[{job_id}] بدء التحميل من: {file_url}")
        
        # تحميل الملف
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(file_url, headers=headers, stream=True, timeout=600)
        response.raise_for_status()
        
        # الحصول على اسم الملف
        filename = file_url.split('/')[-1].split('?')[0]
        if not filename or '.' not in filename:
            filename = 'file.bin'
        
        # حفظ الملف مؤقتاً
        temp_file = f'/tmp/{job_id}_{filename}'
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        size_mb = total_size / (1024*1024)
        print(f"[{job_id}] حجم الملف: {size_mb:.2f} MB")
        jobs[job_id]['progress'] = f'حجم الملف: {size_mb:.1f} MB'
        
        start_time = time.time()
        last_update = time.time()
        
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # تحديث التقدم كل ثانية
                    if total_size > 0 and time.time() - last_update > 1:
                        progress = (downloaded / total_size) * 100
                        speed = downloaded / (time.time() - start_time) / (1024*1024)
                        jobs[job_id]['progress'] = f'التحميل: {progress:.1f}% ({speed:.1f} MB/s)'
                        last_update = time.time()
        
        download_time = time.time() - start_time
        print(f"[{job_id}] انتهى التحميل في {download_time:.1f} ثانية")
        
        # التحقق من حجم الملف
        file_size = os.path.getsize(temp_file)
        max_size = 500 * 1024 * 1024  # 500MB for Nitro
        
        if file_size > max_size:
            os.remove(temp_file)
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'الملف كبير جداً ({file_size/(1024*1024):.1f}MB). الحد الأقصى 500MB'
            return
        
        jobs[job_id]['status'] = 'uploading'
        jobs[job_id]['progress'] = 'بدء الرفع إلى Discord...'
        print(f"[{job_id}] بدء الرفع إلى Discord...")
        
        # رفع الملف إلى Discord
        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        headers = {'Authorization': token}
        
        upload_start = time.time()
        with open(temp_file, 'rb') as f:
            files = {'file': (filename, f)}
            discord_response = requests.post(
                discord_url, 
                headers=headers, 
                files=files,
                timeout=600
            )
        
        upload_time = time.time() - upload_start
        print(f"[{job_id}] انتهى الرفع في {upload_time:.1f} ثانية")
        
        # حذف الملف المؤقت
        try:
            os.remove(temp_file)
            print(f"[{job_id}] تم حذف الملف المؤقت")
        except Exception as e:
            print(f"[{job_id}] فشل حذف الملف: {e}")
        
        if discord_response.status_code == 200:
            total_time = time.time() - start_time
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['message'] = f'✅ تم رفع الملف بنجاح في {total_time:.1f} ثانية!'
            jobs[job_id]['progress'] = 'اكتمل!'
        else:
            error_data = discord_response.text[:500]
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'خطأ من Discord ({discord_response.status_code}): {error_data}'
            print(f"[{job_id}] Discord error: {error_data}")
            
    except requests.Timeout:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = 'انتهت المهلة - الملف كبير جداً أو الاتصال بطيء'
        print(f"[{job_id}] Timeout")
    except requests.RequestException as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = f'خطأ في الاتصال: {str(e)[:200]}'
        print(f"[{job_id}] Request error: {e}")
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = f'خطأ غير متوقع: {str(e)[:200]}'
        print(f"[{job_id}] Unexpected error: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """للتحقق من أن السيرفر يعمل"""
    return jsonify({'status': 'ok', 'message': 'Server is running'})

@app.route('/upload', methods=['POST'])
def upload():
    """بدء عملية الرفع"""
    try:
        data = request.json
        file_url = data.get('file_url')
        token = data.get('token')
        channel_id = data.get('channel_id')
        
        if not all([file_url, token, channel_id]):
            return jsonify({'success': False, 'message': 'جميع الحقول مطلوبة'}), 400
        
        # إنشاء Job ID
        job_id = str(uuid.uuid4())[:8]
        jobs[job_id] = {
            'status': 'queued',
            'progress': 'في الانتظار...',
            'message': '',
            'created_at': time.time()
        }
        
        # تشغيل في الخلفية
        thread = Thread(target=download_and_upload, args=(job_id, file_url, token, channel_id))
        thread.daemon = True
        thread.start()
        
        print(f"[{job_id}] Job created and started")
        
        # رد فوري للمستخدم
        return jsonify({
            'success': True, 
            'job_id': job_id,
            'message': 'بدأت عملية الرفع - تابع الحالة'
        })
        
    except Exception as e:
        print(f"Error in /upload: {e}")
        return jsonify({'success': False, 'message': f'خطأ في السيرفر: {str(e)}'}), 500

@app.route('/status/<job_id>')
def status(job_id):
    """التحقق من حالة الرفع"""
    if job_id not in jobs:
        return jsonify({'error': 'Job not found', 'status': 'not_found'}), 404
    
    job_data = jobs[job_id]
    
    # حذف الـ Jobs القديمة (أكثر من ساعة)
    if time.time() - job_data.get('created_at', 0) > 3600:
        if job_data['status'] in ['completed', 'failed']:
            del jobs[job_id]
            return jsonify({'error': 'Job expired', 'status': 'expired'}), 410
    
    return jsonify(job_data)

@app.route('/jobs')
def list_jobs():
    """عرض كل الـ Jobs (للتصحيح)"""
    return jsonify({
        'total': len(jobs),
        'jobs': {k: v for k, v in jobs.items()}
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
