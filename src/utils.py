import os
from dotenv import load_dotenv
load_dotenv()

def get_openai_key():
    return os.getenv('OPENAI_API_KEY')
