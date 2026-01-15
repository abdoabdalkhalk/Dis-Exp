from flask import Flask, render_template, request, jsonify
import requests
import os
import time
import uuid
from threading import Thread

app = Flask(__name__)

jobs = {}

def download_and_upload(job_id, file_url, token, channel_id, custom_filename=None):
    """تحميل الملف ورفعه إلى Discord - يعمل في الخلفية بالكامل"""
    temp_file = None
    try:
        jobs[job_id]['status'] = 'downloading'
        jobs[job_id]['progress'] = 'بدء التحميل...'
        
        print(f"[{job_id}] 🚀 بدء التحميل من: {file_url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        
        # فحص حجم الملف
        try:
            head_response = requests.head(file_url, headers=headers, timeout=30, allow_redirects=True)
            total_size = int(head_response.headers.get('content-length', 0))
        except:
            total_size = 0
        
        if total_size > 0:
            size_mb = total_size / (1024*1024)
            print(f"[{job_id}] 📦 حجم الملف: {size_mb:.2f} MB")
            jobs[job_id]['progress'] = f'حجم الملف: {size_mb:.1f} MB'
            
            # التحقق من الحد الأقصى
            max_size = 500 * 1024 * 1024
            if total_size > max_size:
                jobs[job_id]['status'] = 'failed'
                jobs[job_id]['message'] = f'❌ الملف كبير جداً ({size_mb:.1f}MB). الحد الأقصى 500MB'
                return
        
        # تحميل الملف بدون timeout
        print(f"[{job_id}] ⬇️ بدء التحميل الفعلي...")
        response = requests.get(
            file_url, 
            headers=headers, 
            stream=True, 
            timeout=None,  # بدون timeout!
            allow_redirects=True
        )
        response.raise_for_status()
        
        # الحصول على اسم الملف
        original_filename = file_url.split('/')[-1].split('?')[0]
        if not original_filename or '.' not in original_filename:
            content_disp = response.headers.get('content-disposition', '')
            if 'filename=' in content_disp:
                original_filename = content_disp.split('filename=')[-1].strip('"\'')
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
        
        print(f"[{job_id}] 📄 اسم الملف: {filename}")
        
        # حفظ الملف
        temp_file = f'/tmp/{job_id}_{filename}'
        
        if total_size == 0:
            total_size = int(response.headers.get('content-length', 0))
        
        downloaded = 0
        start_time = time.time()
        last_log = time.time()
        chunk_size = 8 * 1024 * 1024  # 8MB chunks
        
        with open(temp_file, 'wb', buffering=chunk_size) as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    now = time.time()
                    if now - last_log > 15:  # سجل كل 15 ثانية
                        downloaded_mb = downloaded / (1024*1024)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"[{job_id}] 📊 تقدم: {progress:.1f}% ({downloaded_mb:.1f}MB)")
                            jobs[job_id]['progress'] = f'التحميل: {progress:.0f}%'
                        else:
                            print(f"[{job_id}] 📊 تم تحميل: {downloaded_mb:.1f}MB")
                            jobs[job_id]['progress'] = f'تم تحميل: {downloaded_mb:.0f}MB'
                        last_log = now
            
            f.flush()
            os.fsync(f.fileno())
        
        download_time = time.time() - start_time
        actual_size = os.path.getsize(temp_file)
        
        print(f"[{job_id}] ✅ انتهى التحميل في {download_time/60:.1f} دقيقة")
        print(f"[{job_id}] 📏 الحجم الفعلي: {actual_size/(1024*1024):.2f} MB")
        
        # التحقق من الملف
        if actual_size == 0:
            try:
                os.remove(temp_file)
            except:
                pass
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = '❌ الملف فارغ!'
            return
        
        if total_size > 0 and actual_size < total_size * 0.95:  # أقل من 95% من الحجم المتوقع
            try:
                os.remove(temp_file)
            except:
                pass
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = '❌ التحميل غير مكتمل!'
            return
        
        # الرفع إلى Discord
        jobs[job_id]['status'] = 'uploading'
        jobs[job_id]['progress'] = f'رفع {actual_size/(1024*1024):.0f}MB إلى Discord...'
        print(f"[{job_id}] ⬆️ بدء الرفع إلى Discord...")
        
        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        discord_headers = {'Authorization': token}
        
        upload_start = time.time()
        with open(temp_file, 'rb') as f:
            files = {'file': (filename, f)}
            discord_response = requests.post(
                discord_url, 
                headers=discord_headers, 
                files=files,
                timeout=None  # بدون timeout!
            )
        
        upload_time = time.time() - upload_start
        print(f"[{job_id}] ⏱️ وقت الرفع: {upload_time/60:.1f} دقيقة")
        
        # حذف الملف
        try:
            os.remove(temp_file)
            print(f"[{job_id}] 🗑️ تم حذف الملف المؤقت")
            temp_file = None
        except:
            pass
        
        if discord_response.status_code == 200:
            total_time = time.time() - start_time
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['message'] = f'✅ تم رفع "{filename}" ({actual_size/(1024*1024):.1f}MB) في {total_time/60:.1f} دقيقة!'
            jobs[job_id]['progress'] = 'اكتمل!'
            print(f"[{job_id}] 🎉 SUCCESS!")
        else:
            error_data = discord_response.text[:300]
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'❌ خطأ Discord ({discord_response.status_code}): {error_data}'
            print(f"[{job_id}] ❌ Discord error: {error_data}")
            
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = f'❌ خطأ: {str(e)[:200]}'
        print(f"[{job_id}] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/upload', methods=['POST'])
def upload():
    """بدء عملية الرفع - رد فوري"""
    try:
        data = request.json
        file_url = data.get('file_url')
        token = data.get('token')
        channel_id = data.get('channel_id')
        custom_filename = data.get('custom_filename', '')
        
        if not all([file_url, token, channel_id]):
            return jsonify({'success': False, 'message': 'جميع الحقول مطلوبة'}), 400
        
        # إنشاء Job
        job_id = str(uuid.uuid4())[:8]
        jobs[job_id] = {
            'status': 'queued',
            'progress': 'في الانتظار...',
            'message': '',
            'created_at': time.time()
        }
        
        # تشغيل في الخلفية
        thread = Thread(
            target=download_and_upload, 
            args=(job_id, file_url, token, channel_id, custom_filename)
        )
        thread.daemon = True
        thread.start()
        
        print(f"[{job_id}] 🎬 Job created and started in background")
        
        # رد فوري للمستخدم
        return jsonify({
            'success': True, 
            'job_id': job_id,
            'message': 'تم بدء الرفع! يعمل الآن في الخلفية 🚀'
        }), 200
        
    except Exception as e:
        print(f"❌ Error in /upload: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/status/<job_id>')
def status(job_id):
    """التحقق من حالة Job"""
    if job_id not in jobs:
        return jsonify({'status': 'not_found'}), 404
    
    return jsonify(jobs[job_id])

@app.route('/jobs')
def list_jobs():
    """عرض كل Jobs (للمراقبة)"""
    return jsonify({
        'total': len(jobs),
        'active': sum(1 for j in jobs.values() if j['status'] in ['queued', 'downloading', 'uploading']),
        'jobs': jobs
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)