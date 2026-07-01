import os
from datetime import datetime, timedelta
from google.cloud import bigquery
from google.oauth2 import service_account

CREDENTIALS_PATH = os.path.expanduser("~/.config/gcp/propellic-ai-reader.json")
PROJECT_ID = "propellic-data-lake"

def get_client():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(project=PROJECT_ID, credentials=credentials)

def test_connection():
    try:
        client = get_client()
        client.query("SELECT 1").result()
        print("BigQuery connection successful")
        return True
    except Exception as e:
        print(f"BigQuery connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
