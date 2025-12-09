import requests
import os
from dotenv import load_dotenv

def get_api_key(apikey:str):
    load_dotenv()
    return os.getenv(apikey)

def fetch_data_from_api(url, headers=None, params=None):
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an error for bad responses
        print("Data fetched successfully:")
        print(response.json())
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
