from API import get_api_key, fetch_data_from_api

def main():
    print("Hello from sae-python!")
    WEATHER_API = get_api_key("WEATHERBIT_TOKEN")
    fetch_data_from_api(url="https://api.weatherbit.io/v2.0/current ",
                      params={"city":"Lille","key":WEATHER_API})

if __name__ == "__main__":
    main()
