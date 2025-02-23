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
                # Fixed: Use REDIRECT_URL instead of REDIRECT_URI to match your env variables
                "redirect_uris": [os.environ.get('REDIRECT_URL')]
            }
        }
        return client_config

@app.route('/')
def home():
    return "Auth server running!"

@app.route('/oauth-callback')
def oauth_callback():
    # Get authorization code and state (user_id)
    print(f"Callback received with args: {request.args}")
    print(f"Headers: {dict(request.headers)}")
    
    auth_code = request.args.get('code')
    user_id = request.args.get('state')
    
    if not auth_code or not user_id:
        print("Missing auth_code or user_id")
        return "Missing required parameters", 400
    
    try:
        # Get client config
        client_config = get_client_config()
        
        # Get the redirect URL from environment
        redirect_url = os.environ.get('REDIRECT_URL')
        if not redirect_url:
            print("Missing REDIRECT_URL environment variable")
            return "Server configuration error", 500

        # Set up the OAuth flow
        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=["https://www.googleapis.com/auth/spreadsheets", 
                   "https://www.googleapis.com/auth/drive"]
        )
        
        # Set the redirect URI for this specific request
        flow.redirect_uri = redirect_url
        
        try:
            # Exchange code for credentials
            flow.fetch_token(code=auth_code)
            credentials = flow.credentials
            
            # Store credentials in GCS
            bucket_name = os.environ.get('GCS_BUCKET', 'andre_ocr_bot-bucket')
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            
            # Save token
            token_path = f"bot_user_tokens/{user_id}/token.json"
            blob = bucket.blob(token_path)
            blob.upload_from_string(credentials.to_json())
            print(f"Successfully saved token to {token_path}")
            
            # Redirect back to Telegram bot
            bot_username = os.environ.get('BOT_USERNAME', '@AndreanoBot')
            return redirect(f"https://t.me/{bot_username}?start=auth_success")
            
        except Exception as e:
            print(f"Error in token exchange: {str(e)}")
            raise
            
    except Exception as e:
        print(f"Error in OAuth flow: {str(e)}")
        bot_username = os.environ.get('BOT_USERNAME', '@AndreanoBot')
        return redirect(f"https://t.me/{bot_username}?start=auth_error")
    
    
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)