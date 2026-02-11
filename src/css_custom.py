"""
Custom CSS for the application.
"""

CUSTOM_CSS = """
<style>
    /* Global Theme */
    .stApp { background-color: #0a192f; color: #e6f1ff; }
    h1, h2, h3, h4, h5, h6 { color: #ccd6f6 !important; font-family: 'Segoe UI', sans-serif; }
    p, div, label, span { color: #8892b0; }

    /* Metrics & Cards */
    .metric-card {
        background: #112240; border: 1px solid #233554;
        border-radius: 8px; padding: 15px; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3); margin-bottom: 10px;
    }
    .metric-card h3 { margin: 0; font-size: 0.9em; color: #64ffda; text-transform: uppercase; letter-spacing: 1px; }
    .metric-card .value { font-size: 1.5em; font-weight: bold; color: #e6f1ff; margin-top: 5px; }

    /* Weather Horizontal Bar */
    .weather-row { display: flex; gap: 10px; justify-content: space-between; margin-bottom: 20px; overflow-x: auto; }
    .weather-card {
        background: #112240; border: 1px solid #233554; border-radius: 8px;
        padding: 10px; min-width: 100px; text-align: center; flex: 1;
    }
    .weather-card .wdate { font-size: 0.8em; color: #64ffda; margin-bottom: 4px; }
    .weather-card .temp { font-size: 1.1em; font-weight: bold; color: #e6f1ff; }
    .weather-card .desc { font-size: 0.8em; color: #8892b0; text-transform: capitalize; }
    .indoor-alert {
        background: rgba(255, 99, 71, 0.2); border: 1px solid tomato; color: tomato;
        padding: 8px; border-radius: 5px; margin-bottom: 10px; text-align: center;
    }

    /* Move / Route Tables */
    .route-card {
        background: #112240; border-left: 4px solid #64ffda; padding: 15px;
        margin-bottom: 15px; border-radius: 0 8px 8px 0;
    }
    .route-card h4 { margin: 0; color: #e6f1ff; }
    .route-price { font-size: 1.2rem; color: #FFBF00; font-weight: bold; margin: 5px 0; }
    .route-detail { font-size: 0.9rem; margin: 2px 0; }

    /* Comparison Badge */
    .vs-badge {
        background: #FFBF00; color: #0a192f; font-weight: bold;
        border-radius: 50%; width: 40px; height: 40px;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 0 10px rgba(255,191,0,0.5);
    }
    .compare-card {
        background: rgba(17,34,64,0.5); border: 1px solid #233554;
        border-radius: 12px; padding: 20px; text-align: center;
    }
    .compare-card .price { font-size: 2em; color: #64ffda; font-weight: bold; }

    /* Planner */
    .day-card {
        background: #112240; border-top: 3px solid #64ffda;
        padding: 15px; margin-bottom: 20px; border-radius: 0 0 8px 8px;
    }
    .map-container { border: 2px solid #233554; border-radius: 8px; overflow: hidden; margin-top: 10px; }
</style>
"""
