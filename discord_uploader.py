from flask import Flask, render_template, request, jsonify
import requests
import os
import json
import mimetypes
from threading import Thread
from datetime import datetime
import traceback

app = Flask(__name__)

# Store upload operations status
upload_status = {}

def get_file_size_mb(size_bytes):
    """Convert file size to megabytes"""
    return round(size_bytes / (1024 * 1024), 2)

def download_and_upload(upload_id, file_url, token, channel_id, options):
    """Download file and upload to Discord with advanced options"""
    try:
        upload_status[upload_id] = {'status': 'downloading', 'progress': 0}
        
        # Check if sending to DM
        is_dm = options.get('is_dm', False)
        user_id = options.get('user_id', '')
        
        # If DM, get or create DM channel
        if is_dm and user_id:
            print(f"[DEBUG] Creating DM channel for user {user_id}")
            dm_url = 'https://discord.com/api/v10/users/@me/channels'
            dm_headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            dm_response = requests.post(
                dm_url,
                headers=dm_headers,
                json={'recipient_id': user_id}
            )
            
            print(f"[DEBUG] DM Response Status: {dm_response.status_code}")
            print(f"[DEBUG] DM Response: {dm_response.text}")
            
            if dm_response.status_code == 200:
                channel_id = dm_response.json()['id']
                print(f"[DEBUG] DM Channel ID: {channel_id}")
            else:
                raise Exception(f"Failed to create DM channel: {dm_response.text}")
        
        # Download file
        print(f"[DEBUG] Downloading from: {file_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(file_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()
        
        print(f"[DEBUG] Download response status: {response.status_code}")
        
        # Get filename
        if options.get('custom_filename'):
            filename = options['custom_filename']
        else:
            filename = file_url.split('/')[-1].split('?')[0]
            if not filename or '.' not in filename:
                filename = f'file_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
        # Ensure file has extension
        if '.' not in filename:
            content_type = response.headers.get('content-type', '')
            ext = mimetypes.guess_extension(content_type)
            if ext:
                filename += ext
        
        print(f"[DEBUG] Filename: {filename}")
        
        # Save file temporarily
        temp_file = f'/tmp/{upload_id}_{filename}'
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        print(f"[DEBUG] Total size: {total_size} bytes ({get_file_size_mb(total_size)} MB)")
        
        upload_status[upload_id] = {
            'status': 'downloading',
            'progress': 0,
            'total_size': get_file_size_mb(total_size) if total_size > 0 else 'Unknown'
        }
        
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = int((downloaded / total_size) * 100)
                        upload_status[upload_id]['progress'] = progress
        
        print(f"[DEBUG] Download completed: {downloaded} bytes")
        
        upload_status[upload_id] = {'status': 'uploading', 'progress': 100}
        
        # Prepare message
        payload = {}
        if options.get('message'):
            payload['content'] = options['message']
        
        # Add Embed if enabled
        if options.get('use_embed'):
            embed = {
                'title': options.get('embed_title', 'Uploaded File'),
                'description': options.get('embed_description', ''),
                'color': int(options.get('embed_color', '5865F2'), 16),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if options.get('embed_footer'):
                embed['footer'] = {'text': options['embed_footer']}
            
            if options.get('embed_thumbnail'):
                embed['thumbnail'] = {'url': options['embed_thumbnail']}
                
            payload['embeds'] = [embed]
        
        # Upload file to Discord
        discord_url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
        headers = {
            'Authorization': token
        }
        
        print(f"[DEBUG] Uploading to Discord channel: {channel_id}")
        print(f"[DEBUG] File size: {os.path.getsize(temp_file)} bytes")
        
        with open(temp_file, 'rb') as f:
            files = {'file': (filename, f)}
            
            # Add payload_json if there's additional content
            if payload:
                discord_response = requests.post(
                    discord_url, 
                    headers=headers, 
                    files=files,
                    data={'payload_json': json.dumps(payload)},
                    timeout=120
                )
            else:
                discord_response = requests.post(
                    discord_url, 
                    headers=headers, 
                    files=files,
                    timeout=120
                )
        
        print(f"[DEBUG] Discord response status: {discord_response.status_code}")
        print(f"[DEBUG] Discord response: {discord_response.text[:500]}")
        
        # Delete temporary file
        try:
            os.remove(temp_file)
            print(f"[DEBUG] Temporary file deleted")
        except Exception as e:
            print(f"[DEBUG] Failed to delete temp file: {e}")
        
        if discord_response.status_code == 200:
            response_data = discord_response.json()
            file_info = response_data.get('attachments', [{}])[0]
            
            upload_status[upload_id] = {
                'status': 'completed',
                'progress': 100,
                'message': 'File uploaded successfully! ✅',
                'file_url': file_info.get('url', ''),
                'file_size': get_file_size_mb(file_info.get('size', 0))
            }
            print(f"[DEBUG] Upload completed successfully!")
        else:
            error_data = discord_response.json() if discord_response.headers.get('content-type', '').startswith('application/json') else {}
            error_msg = error_data.get('message', discord_response.text)
            
            # Check specific error codes
            if discord_response.status_code == 401:
                error_msg = "Invalid token! Please check your User Token."
            elif discord_response.status_code == 403:
                error_msg = "No permission! Check if you can write in this channel."
            elif discord_response.status_code == 404:
                error_msg = "Channel not found! Check your Channel ID."
            elif 'request entity too large' in error_msg.lower():
                error_msg = "File too large! Max size: 25MB (or 50MB/500MB with Nitro)"
            
            upload_status[upload_id] = {
                'status': 'failed',
                'message': f'Discord error ({discord_response.status_code}): {error_msg}'
            }
            print(f"[ERROR] Discord upload failed: {error_msg}")
            
    except requests.exceptions.Timeout:
        error_msg = 'Operation timeout. File may be too large or connection too slow.'
        upload_status[upload_id] = {
            'status': 'failed',
            'message': error_msg
        }
        print(f"[ERROR] {error_msg}")
        
    except requests.exceptions.RequestException as e:
        error_msg = f'Network error: {str(e)}'
        upload_status[upload_id] = {
            'status': 'failed',
            'message': error_msg
        }
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
    except Exception as e:
        error_msg = f'Unexpected error: {str(e)}'
        upload_status[upload_id] = {
            'status': 'failed',
            'message': error_msg
        }
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")

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
        return jsonify({'success': False, 'message': 'URL, token, and channel ID are required'})
    
    # Validate token format
    if not token.startswith(('mfa.', 'MTk', 'ODc', 'OTc', 'Njc')):
        return jsonify({'success': False, 'message': 'Invalid token format! Make sure you copied it correctly.'})
    
    # Create unique operation ID
    upload_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    
    # Extract options
    options = {
        'custom_filename': data.get('custom_filename', '').strip(),
        'message': data.get('message', '').strip(),
        'use_embed': data.get('use_embed', False),
        'embed_title': data.get('embed_title', '').strip(),
        'embed_description': data.get('embed_description', '').strip(),
        'embed_color': data.get('embed_color', '5865F2').strip(),
        'embed_footer': data.get('embed_footer', '').strip(),
        'embed_thumbnail': data.get('embed_thumbnail', '').strip(),
        'is_dm': data.get('is_dm', False),
        'user_id': data.get('user_id', '').strip()
    }
    
    print(f"[INFO] Starting upload {upload_id}")
    print(f"[INFO] File URL: {file_url}")
    print(f"[INFO] Channel ID: {channel_id}")
    
    # Run operation in background
    thread = Thread(target=download_and_upload, args=(upload_id, file_url, token, channel_id, options))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True, 
        'message': 'Upload process started...',
        'upload_id': upload_id
    })

@app.route('/status/<upload_id>')
def get_status(upload_id):
    """Get upload operation status"""
    status = upload_status.get(upload_id, {'status': 'not_found'})
    return jsonify(status)

@app.route('/health')
def health():
    """Health check endpoint for Render"""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)