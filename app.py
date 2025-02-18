from flask import Flask, request, redirect
from google_auth_oauthlib.flow import Flow
from google.cloud import storage
import json
import os

# Set Google credentials - Railway will use environment variables
if os.path.exists('telegram-ocr-connection.json'):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'telegram-ocr-connection.json'

app = Flask(__name__)

def get_client_config():
    """Load OAuth client configuration"""
    if os.path.exists('credentials.json'):
        with open('credentials.json', 'r') as f:
            return json.load(f)
    else:
        # Use environment variables in production
        client_config = {
            "web": {
                "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
                "project_id": os.environ.get('GOOGLE_PROJECT_ID'),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
                "redirect_uris": [os.environ.get('REDIRECT_URI')]
            }
        }
        return client_config

@app.route('/')
def home():
    return "Auth server running!"

@app.route('/oauth-callback')
def oauth_callback():
    # Get authorization code and state (user_id)
    auth_code = request.args.get('code')
    user_id = request.args.get('state')
    
    if not auth_code or not user_id:
        return "Missing parameters", 400
    
    try:
        # Exchange code for tokens
        flow = Flow.from_client_config(
            client_config=get_client_config(),
            scopes=["https://www.googleapis.com/auth/spreadsheets", 
                   "https://www.googleapis.com/auth/drive"],
            redirect_uri=request.base_url
        )
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials
        
        # Store credentials
        storage_client = storage.Client()
        bucket = storage_client.bucket(os.environ.get('GCS_BUCKET', 'andre_ocr_bot-bucket'))
        blob = bucket.blob(f"bot_user_tokens/{user_id}/token.json")
        blob.upload_from_string(credentials.to_json())
        
        # Redirect back to Telegram
        bot_username = os.environ.get('BOT_USERNAME', 'YourBotUsername')
        return redirect(f"https://t.me/{bot_username}?start=auth_success_{user_id}")
        
    except Exception as e:
        print(f"Error in OAuth flow: {e}")
        bot_username = os.environ.get('BOT_USERNAME', 'YourBotUsername')
        return redirect(f"https://t.me/{bot_username}?start=auth_error")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)