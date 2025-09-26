# live_underwriting_agent_ollama.py

import autogen
import requests
import json
import os
from typing import Dict, Any, Annotated

# 🆕 SECURE STEP 1: Import and load the .env file
from dotenv import load_dotenv
load_dotenv() # This loads variables from the .env file into os.environ

# =========================================================================
# 1. ENVIRONMENT & LLM CONFIGURATION
# =========================================================================

# ⚠️ Set your OpenWeatherMap API Key here or via an environment variable
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
#WEATHER_API_KEY = "test" # <--- REPLACE THIS
WEATHER_BASE_URL = "http://api.openweathermap.org/data/2.5/weather"


# ⚠️ OLLAMA CONFIGURATION
# This tells AutoGen to connect to your local Ollama server
# A placeholder `api_key` is necessary for AutoGen's client wrapper
config_list_ollama = [
    {
        "model": "llama3.2:latest",  # Ensure this is the correct model name
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama", 
        "price": [0, 0],  # [prompt_price, completion_price] per 1K tokens
    }
]

# =========================================================================
# 2. LIVE API TOOL DEFINITION
# =========================================================================

def get_current_weather_risk(
    city_name: Annotated[str, "The name of the city (e.g., 'Miami')."],
    country_code: Annotated[str, "The two-letter country code (e.g., 'US', 'GB')."] = 'US'
) -> str:
    """
    Fetches current weather data for a city to assess immediate geographical risk.
    The data is returned in Fahrenheit for simplicity.
    """
    if WEATHER_API_KEY == "YOUR_OPENWEATHERMAP_API_KEY":
        # Check to ensure user replaced the placeholder key
        return json.dumps({"status": "ERROR", "message": "Please update WEATHER_API_KEY with your valid key."})

    params = {
        'q': f"{city_name},{country_code}",
        'appid': WEATHER_API_KEY,
        'units': 'imperial'
    }

    try:
        response = requests.get(WEATHER_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get('cod') == 200:
            main_info = data.get('main', {})
            weather_desc = data.get('weather', [{}])[0].get('description', 'clear sky')

            risk_data = {
                "city": city_name,
                "temperature_f": main_info.get('temp'),
                "humidity_percent": main_info.get('humidity'),
                "wind_speed_mph": data.get('wind', {}).get('speed'),
                "weather_description": weather_desc,
                "risk_note": "Wind or severe precipitation may indicate high immediate property risk."
            }
            return json.dumps(risk_data)
        else:
            return json.dumps({"status": "City Not Found", "message": f"Could not find weather data for {city_name}."})

    except requests.exceptions.RequestException as e:
        return json.dumps({"status": "API Error", "message": f"Failed to connect to weather API: {e}"})

# =========================================================================
# 3. AGENT CONFIGURATION
# =========================================================================

# The User Proxy Agent (The tool executor)
executor_agent = autogen.UserProxyAgent(
    name="Tool_Executor",
    human_input_mode="NEVER",
    is_termination_msg=lambda x: x.get("content", "").find("TERMINATE") != -1,
    code_execution_config={"use_docker": False}
)

# The Underwriting Agent (The planner and caller)
underwriting_agent = autogen.AssistantAgent(
    name="Underwriting_Agent",
    system_message="You are a property Underwriter. You MUST use the 'get_current_weather_risk' tool to check the weather for the property location before making an insurance decision (APPROVE, DECLINE, REFER). If severe weather is reported (e.g., wind speed is over 20 mph or description is 'heavy rain', 'thunderstorm', or 'snow'), you must DECLINE. Otherwise, APPROVE. State your final decision clearly and respond with a 'TERMINATE'.",
    llm_config={
        "config_list": config_list_ollama,
        # Functions are registered via `register_function`, not defined here
    },
)

# Register the function with both agents
autogen.register_function(
    get_current_weather_risk,
    caller=underwriting_agent,
    executor=executor_agent,
    description="Gets current weather data for a city to assess immediate geographical risk.",
)


# =========================================================================
# 4. CHAT INITIATION
# =========================================================================

initial_prompt = "Process a new property insurance application for a house located in **London, GB**."

print("--- Starting Agentic Underwriting Workflow with LIVE API ---")
chat_result = executor_agent.initiate_chat(
    underwriting_agent,
    message=initial_prompt,
)
