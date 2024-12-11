import argparse
import requests

def get_available_models(base_url, api_key):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(f'{base_url}/models', headers=headers)
    
    if response.status_code == 200:
        models = response.json().get('data', [])
        model_names = [model['id'] for model in models]
        return model_names
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return []

def main():
    parser = argparse.ArgumentParser(description='Fetch available models from OpenAI API.')
    parser.add_argument('--baseurl', required=True, help='The base URL for the OpenAI API including /v1')
    parser.add_argument('--apikey', required=True, help='The API key for authentication')
    
    args = parser.parse_args()
    
    base_url = args.baseurl
    api_key = args.apikey
    
    models = get_available_models(base_url, api_key)
    
    if models:
        print(' '.join(models))
    else:
        print('No models available or there was an error fetching the models.')

if __name__ == '__main__':
    main()
