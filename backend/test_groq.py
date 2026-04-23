import os
from groq import Groq

print('Testing Groq import...')
api_key = os.getenv('GROQ_API_KEY', 'test-key')
print(f'API Key: {api_key[:10]}...')

try:
    print('Creating Groq client...')
    client = Groq(api_key=api_key)
    print('SUCCESS: Client created')
    print(f'Client type: {type(client)}')
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
