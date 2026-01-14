from flask import Flask, render_template, request, jsonify
import requests
import os
import time
import uuid
from threading import Thread

app = Flask(__name__)

# تخزين حالة الـ Jobs في الذاكرة
jobs = {}

def download_and_upload(job_id, file_url, token, channel_id, custom_filename=None):
    """تحميل الملف ورفعه إلى Discord"""
    temp_file = None
    try:
        jobs[job_id]['status'] = 'downloading'
        jobs[job_id]['progress'] = 'بدء التحميل...'
        
        print(f"[{job_id}] بدء التحميل من: {file_url}")
        
        # تحميل الملف مع إعادة المحاولة
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Connection': 'keep-alive'
        }
        
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                print(f"[{job_id}] محاولة التحميل {attempt + 1}/{max_retries}")
                response = requests.get(
                    file_url, 
                    headers=headers, 
                    stream=True, 
                    timeout=600,
                    allow_redirects=True
                )
                response.raise_for_status()
                print(f"[{job_id}] نجحت المحاولة {attempt + 1}")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[{job_id}] محاولة {attempt + 1} فشلت: {e}, إعادة المحاولة...")
                    time.sleep(2)
                else:
                    raise
        
        # الحصول على اسم الملف والامتداد
        original_filename = file_url.split('/')[-1].split('?')[0]
        if not original_filename or '.' not in original_filename:
            original_filename = 'file.bin'
        
        # استخراج الامتداد
        file_extension = ''
        if '.' in original_filename:
            file_extension = '.' + original_filename.split('.')[-1]
        
        # تطبيق الاسم المخصص مع الحفاظ على الامتداد
        if custom_filename and custom_filename.strip():
            custom_filename = custom_filename.strip()
            # إزالة الامتداد من الاسم المخصص إن وُجد
            if '.' in custom_filename:
                custom_filename = '.'.join(custom_filename.split('.')[:-1])
            filename = custom_filename + file_extension
        else:
            filename = original_filename
        
        print(f"[{job_id}] اسم الملف: {filename} (الامتداد: {file_extension})")
        
        # حفظ الملف مؤقتاً
        temp_file = f'/tmp/{job_id}_{filename}'
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        size_mb = total_size / (1024*1024) if total_size > 0 else 0
        print(f"[{job_id}] حجم الملف المتوقع: {size_mb:.2f} MB ({total_size} bytes)")
        jobs[job_id]['progress'] = f'حجم الملف: {size_mb:.1f} MB'
        
        start_time = time.time()
        last_update = time.time()
        last_log = time.time()
        
        # استخدام buffer أكبر للكتابة
        print(f"[{job_id}] بدء الكتابة إلى: {temp_file}")
        with open(temp_file, 'wb', buffering=8192*1024) as f:  # 8MB buffer
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
                    
                    # سجل في الكونسول كل 5 ثواني
                    if time.time() - last_log > 5:
                        print(f"[{job_id}] تم تحميل: {downloaded}/{total_size} bytes ({downloaded/(1024*1024):.1f}MB)")
                        last_log = time.time()
            
            # التأكد من كتابة كل البيانات على القرص
            f.flush()
            os.fsync(f.fileno())
        
        download_time = time.time() - start_time
        
        # التأكد من اكتمال الكتابة
        actual_size = os.path.getsize(temp_file)
        print(f"[{job_id}] انتهى التحميل في {download_time:.1f} ثانية")
        print(f"[{job_id}] الحجم المتوقع: {total_size} bytes, الحجم الفعلي: {actual_size} bytes")
        
        # التحقق من اكتمال التحميل
        if total_size > 0 and actual_size != total_size:
            try:
                os.remove(temp_file)
            except:
                pass
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'فشل التحميل الكامل! تم تحميل {actual_size/(1024*1024):.1f}MB من {total_size/(1024*1024):.1f}MB'
            print(f"[{job_id}] ERROR: File size mismatch!")
            return
        
        # التحقق من حجم الملف
        file_size = os.path.getsize(temp_file)
        max_size = 500 * 1024 * 1024  # 500MB for Nitro
        
        print(f"[{job_id}] حجم الملف النهائي: {file_size/(1024*1024):.2f} MB")
        
        if file_size == 0:
            try:
                os.remove(temp_file)
            except:
                pass
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = 'الملف المحمل فارغ! تحقق من صحة الرابط'
            print(f"[{job_id}] ERROR: Downloaded file is empty!")
            return
        
        if file_size > max_size:
            try:
                os.remove(temp_file)
            except:
                pass
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'الملف كبير جداً ({file_size/(1024*1024):.1f}MB). الحد الأقصى 500MB'
            return
        
        jobs[job_id]['status'] = 'uploading'
        jobs[job_id]['progress'] = f'بدء الرفع إلى Discord... ({file_size/(1024*1024):.1f}MB)'
        print(f"[{job_id}] بدء الرفع إلى Discord...")
        
        # رفع الملف إلى Discord
        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        discord_headers = {'Authorization': token}
        
        upload_start = time.time()
        with open(temp_file, 'rb') as f:
            files = {'file': (filename, f)}
            print(f"[{job_id}] إرسال الملف إلى Discord API...")
            discord_response = requests.post(
                discord_url, 
                headers=discord_headers, 
                files=files,
                timeout=900  # 15 دقيقة للملفات الكبيرة
            )
        
        upload_time = time.time() - upload_start
        print(f"[{job_id}] انتهى الرفع في {upload_time:.1f} ثانية")
        print(f"[{job_id}] Discord response status: {discord_response.status_code}")
        
        # حذف الملف المؤقت
        try:
            os.remove(temp_file)
            print(f"[{job_id}] تم حذف الملف المؤقت")
            temp_file = None
        except Exception as e:
            print(f"[{job_id}] فشل حذف الملف: {e}")
        
        if discord_response.status_code == 200:
            total_time = time.time() - start_time
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['message'] = f'✅ تم رفع "{filename}" ({file_size/(1024*1024):.1f}MB) بنجاح في {total_time:.1f}ث!'
            jobs[job_id]['progress'] = 'اكتمل!'
            print(f"[{job_id}] SUCCESS!")
        else:
            error_data = discord_response.text[:500]
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['message'] = f'خطأ من Discord ({discord_response.status_code}): {error_data}'
            print(f"[{job_id}] Discord error: {error_data}")
            
    except requests.Timeout:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = 'انتهت المهلة - الملف كبير جداً أو الاتصال بطيء'
        print(f"[{job_id}] Timeout error")
    except requests.RequestException as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = f'خطأ في الاتصال: {str(e)[:200]}'
        print(f"[{job_id}] Request error: {e}")
    except Exception as e:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['message'] = f'خطأ غير متوقع: {str(e)[:200]}'
        print(f"[{job_id}] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # التأكد من حذف الملف المؤقت في حالة الخطأ
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                print(f"[{job_id}] تم حذف الملف المؤقت (cleanup)")
            except:
                pass

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
        custom_filename = data.get('custom_filename', '')
        
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
        thread = Thread(target=download_and_upload, args=(job_id, file_url, token, channel_id, custom_filename))
        thread.daemon = True
        thread.start()
        
        print(f"[{job_id}] Job created and started (custom name: '{custom_filename}' or default)")
        
        # رد فوري للمستخدم
        return jsonify({
            'success': True, 
            'job_id': job_id,
            'message': 'بدأت عملية الرفع - تابع الحالة'
        })
        
    except Exception as e:
        print(f"Error in /upload: {e}")
        import traceback
        traceback.print_exc()
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
