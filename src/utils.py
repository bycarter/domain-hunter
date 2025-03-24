import os
from dotenv import load_dotenv
load_dotenv()

def get_openai_key():
    return os.getenv('OPENAI_API_KEY')

def get_project_root():
    """Return the project root directory path"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
def get_data_dir():
    """Return the data directory path, creating it if needed"""
    data_dir = os.path.join(get_project_root(), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir