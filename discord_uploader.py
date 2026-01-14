from flask import Flask, render_template, request, jsonify
import requests
import os
import time

app = Flask(__name__)

def download_and_upload(file_url, token, channel_id):
    """تحميل الملف ورفعه إلى Discord"""
    try:
        print(f"[INFO] بدء التحميل من: {file_url}")
        
        # تحميل الملف
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(file_url, headers=headers, stream=True, timeout=600)
        response.raise_for_status()
        
        # الحصول على اسم الملف
        filename = file_url.split('/')[-1].split('?')[0]
        if not filename or '.' not in filename:
            filename = 'file.bin'
        
        # حفظ الملف مؤقتاً
        temp_file = f'/tmp/{filename}'
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        print(f"[INFO] حجم الملف: {total_size / (1024*1024):.2f} MB")
        
        start_time = time.time()
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"[INFO] التحميل: {progress:.1f}%")
        
        download_time = time.time() - start_time
        print(f"[INFO] انتهى التحميل في {download_time:.1f} ثانية")
        
        # التحقق من حجم الملف
        file_size = os.path.getsize(temp_file)
        max_size = 500 * 1024 * 1024  # 500MB for Nitro
        
        if file_size > max_size:
            os.remove(temp_file)
            return {
                'success': False, 
                'message': f'الملف كبير جداً ({file_size/(1024*1024):.1f}MB). الحد الأقصى 500MB'
            }
        
        print(f"[INFO] بدء الرفع إلى Discord...")
        
        # رفع الملف إلى Discord
        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        headers = {
            'Authorization': token
        }
        
        upload_start = time.time()
        with open(temp_file, 'rb') as f:
            files = {'file': (filename, f)}
            discord_response = requests.post(
                discord_url, 
                headers=headers, 
                files=files,
                timeout=600  # 10 دقائق timeout
            )
        
        upload_time = time.time() - upload_start
        print(f"[INFO] انتهى الرفع في {upload_time:.1f} ثانية")
        
        # حذف الملف المؤقت
        try:
            os.remove(temp_file)
            print(f"[INFO] تم حذف الملف المؤقت")
        except:
            pass
        
        if discord_response.status_code == 200:
            total_time = time.time() - start_time
            return {
                'success': True, 
                'message': f'✅ تم رفع الملف بنجاح! ({total_time:.1f} ثانية)'
            }
        else:
            error_msg = discord_response.text
            print(f"[ERROR] فشل الرفع: {error_msg}")
            return {
                'success': False, 
                'message': f'خطأ من Discord: {discord_response.status_code} - {error_msg[:200]}'
            }
            
    except requests.Timeout:
        return {'success': False, 'message': 'انتهت المهلة - الملف كبير جداً أو الاتصال بطيء'}
    except requests.RequestException as e:
        return {'success': False, 'message': f'خطأ في الاتصال: {str(e)}'}
    except Exception as e:
        print(f"[ERROR] خطأ غير متوقع: {str(e)}")
        return {'success': False, 'message': f'خطأ: {str(e)}'}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """للتحقق من أن السيرفر يعمل"""
    return jsonify({'status': 'ok', 'message': 'السيرفر يعمل بشكل صحيح'})

@app.route('/upload', methods=['POST'])
def upload():
    data = request.json
    file_url = data.get('file_url')
    token = data.get('token')
    channel_id = data.get('channel_id')
    
    if not all([file_url, token, channel_id]):
        return jsonify({'success': False, 'message': 'جميع الحقول مطلوبة'})
    
    # تنفيذ العملية مباشرة (بدون Thread)
    result = download_and_upload(file_url, token, channel_id)
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
