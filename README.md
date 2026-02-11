# SAE_VCOD - Lille Trip Planner ⚜️

SAE Projet Python en binôme. A comprehensive interactive application to plan your trip to Lille, France. This tool helps you estimate budgets, compare transport options (Train vs. Car), and generate a personalized itinerary.

## Quick Start

Follow these steps to get the application running locally in under 5 minutes.

### Prerequisites

- Python 3.8 or higher
- [SNCF API Key](https://www.sncf.com/en/booking-itinerary/book-tickets) (Optional, for real-time train prices)
- [OpenRouteService API Key](https://openrouteservice.org/) (Optional, for car route calculation)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/trip_lille_planner.git
    cd trip_lille_planner
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment Variables:**
    Create a `.env` file in the root directory and add your API keys:
    ```env
    SNCF_API_KEY=your_sncf_api_key_here
    ORS_API_KEY=your_openrouteservice_api_key_here
    ```

4.  **Run the Application:**
    ```bash
    streamlit run app.py
    ```

## Features

-   **🏠 Interactive Home Dashboard:**
    -   Beautiful Hero section with a dynamic introduction to Lille.
    -   Real-time weather forecast (Past 3 days & Future 2 days).
    -   Macro-view interactive map of the city.

-   **🚆 Smart Transport Comparison:**
    -   **Train Search:** Connects to SNCF data to find trips from major cities (Paris, London, Brussels, etc.).
    -   **Car Route Calculator:** Estimates fuel costs, tolls, and duration using OpenRouteService.
    -   **Cost Comparison:** Visual comparison of Train vs. Car costs for your specific group size.

-   **📅 Automated Itinerary Planner:**
    -   **Budget Control:** Set your budget cap and track estimated costs for meals, hotels, and transport.
    -   **Session-Based Planning:** Automatically generates a morning/afternoon schedule with suggested activities and dining options.
    -   **Master Map:** Visualizes your entire trip itinerary on an interactive map.

-   **📊 Data Visualization:**
    -   Integrated **PyGWalker** for exploring underlying datasets (Weather, Hotels, Restaurants, Historical Sites) with drag-and-drop charts.

-   **🌍 Multi-Language Support:**
    -   Fully localized in **English** and **French**.

## Configuration

You can customize the trip parameters using the Sidebar in the application:

| Setting | Description | Default |
| :--- | :--- | :--- |
| **Language** | Switch between English and Français | English |
| **Start City** | City of departure | Paris |
| **Dates** | Trip start date | Today |
| **Duration** | Number of days (1-7) | 3 |
| **Travelers** | Number of people (1-10) | 2 |
| **Transport** | Mode of arrival (Train/Car) | Train |
| **Hotel Tier** | Star rating preference (1-5) | 3 Stars |

## Project Structure

```
trip_lille_planner/
├── app.py                # Main Streamlit application entry point
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (API Keys)
├── src/                  # Source code modules
│   ├── services.py       # API wrappers (Weather, Train, Route, POI, Wiki)
│   ├── planner.py        # Trip planning logic and budget estimation
│   ├── translations.py   # Localization strings (EN/FR)
│   └── css_custom.py     # Custom CSS styling
├── data/                 # Data storage (CSVs for POIs, cache)
└── README.md             # Project documentation
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the project.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## License

This project is part of an academic assignment (SAE).
