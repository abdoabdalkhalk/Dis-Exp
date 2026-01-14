from flask import Flask, render_template, request, jsonify
import requests
import os
from threading import Thread

app = Flask(__name__)

def download_and_upload(file_url, token, channel_id):
    """تحميل الملف ورفعه إلى Discord"""
    try:
        # تحميل الملف
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(file_url, headers=headers, stream=True)
        response.raise_for_status()
        
        # الحصول على اسم الملف
        filename = file_url.split('/')[-1].split('?')[0]
        if not filename:
            filename = 'file'
        
        # حفظ الملف مؤقتاً
        temp_file = f'/tmp/{filename}'
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        
        # رفع الملف إلى Discord باستخدام توكن الحساب
        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        headers = {
            'Authorization': token  # توكن الحساب مباشرة بدون Bot
        }
        
        with open(temp_file, 'rb') as f:
            files = {'file': (filename, f)}
            discord_response = requests.post(discord_url, headers=headers, files=files)
        
        # حذف الملف المؤقت
        os.remove(temp_file)
        
        if discord_response.status_code == 200:
            return {'success': True, 'message': 'تم رفع الملف بنجاح!'}
        else:
            return {'success': False, 'message': f'خطأ: {discord_response.text}'}
            
    except Exception as e:
        return {'success': False, 'message': f'خطأ: {str(e)}'}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    data = request.json
    file_url = data.get('file_url')
    token = data.get('token')
    channel_id = data.get('channel_id')
    
    if not all([file_url, token, channel_id]):
        return jsonify({'success': False, 'message': 'جميع الحقول مطلوبة'})
    
    # تشغيل العملية في خلفية
    thread = Thread(target=download_and_upload, args=(file_url, token, channel_id))
    thread.start()
    
    return jsonify({'success': True, 'message': 'بدأت عملية الرفع... قد تستغرق بعض الوقت'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
