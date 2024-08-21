import os
import json
import requests
from flask import Flask, request, jsonify
from openai import AzureOpenAI

app = Flask(__name__)  # Create a new Flask web application

# Set environment variables
os.environ["AZURE_OPENAI_ENDPOINT"] = "https://az-openai-aj.openai.azure.com/"
os.environ["AZURE_OPENAI_API_KEY"] = "5bbaa7ab51834010a31d919d9676b6c7"
os.environ["OPENWEATHERMAP_API_KEY"] = "1dd9e8f6c2c4aa1e9f2bd669da94b02a"

# Initialize Azure OpenAI client
# This sets up a connection to the Azure OpenAI service using the environment variables (keys and settings)
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview"
)

# Specify the model name to use (in this case, "GPT-35-Turbo-16k")
deployment_name = "gpt-35-turbo-16k"

def get_weather(latitude, longitude):
    # This function fetches the current weather for a specific location using latitude and longitude

    api_key = os.getenv("OPENWEATHERMAP_API_KEY")  # Get the secret key for the weather service
    base_url = "https://api.openweathermap.org/data/3.0/onecall?"  # Base URL of the weather API

    # Create the full URL by adding the location and the API key
    complete_url = f"{base_url}lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
    
    # Send a request to the weather API and get the response
    response = requests.get(complete_url)
    weather_data = response.json()  # Convert the response into a readable format (JSON)

    # Check if the weather data was retrieved successfully
    if "current" not in weather_data:
        return "Error fetching weather data."

    # Extract the current weather description and temperature from the data
    weather_condition = weather_data["current"]["weather"][0]["description"]
    temperature = weather_data["current"]["temp"]
    
    # Return the weather data as a JSON object
    return json.dumps({
        "latitude": latitude,
        "longitude": longitude,
        "weather_condition": weather_condition,
        "temperature": temperature
    })

@app.route('/api/weather', methods=['POST'])
def assistant():
    # This function handles requests to the "/api/weather" route

    data = request.json  # Get the incoming JSON data from the user's request
    conversation = data.get("conversation", [])  # Extract the conversation history from the request
    messages = [{"role": msg["role"], "content": msg["content"]} for msg in conversation]  # Prepare messages for the AI

    # Define the tool (function) that the AI can use to get weather information
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",  # The name of the tool/function
                "description": "Get the weather condition using latitude and longitude. If any argument is missing in the user message, assume it as 'null' and not zero (0) or don't return missing argument value yourself",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {"type": "number", "description": "The latitude of the location"},  # Latitude input
                        "longitude": {"type": "number", "description": "The longitude of the location"},  # Longitude input
                    },
                    "required": ["latitude", "longitude"],  # Both latitude and longitude are required
                },
            }
        }
    ]

    try:
        # Send the conversation and tools to the AI model to get a response
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",  # Automatically allows the model to decide if and when to use the provided function(s)
            # You can customize the behavior using the following options:
            # - "auto" (default): The model decides automatically which functions to call.
            # - "required": The model is forced to call one or more functions.
            # - {"type": "function", "function": {"name": "my_function"}}: Force the model to call a specific function.
            # - "none": Disables function calling, and the model only generates user-facing messages.
        )
    except Exception as e:
        # If something goes wrong, return an error message
        return jsonify({"error": str(e)}), 500

    # Get the first response from the AI model
    response_message = response.choices[0].message
    messages.append(response_message)  # Add the AI's response to the conversation history
    print(response_message)  # Print the response for debugging purposes

    # Default message in case the AI doesn't call any function
    assistant_message_content = "No function calls were made by the model."

    # Check if the AI decided to use any tools (functions)
    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            if tool_call.function.name == "get_weather":  # Check if the AI called the weather function
                function_args = json.loads(tool_call.function.arguments)  # Get the arguments used (latitude, longitude)

                # Check if the necessary arguments are missing
                latitude = function_args.get("latitude")
                longitude = function_args.get("longitude")

                if latitude is None:
                    # If latitude is missing, ask the user for it
                    assistant_message_content = "Could you please provide the latitude?"
                elif longitude is None or longitude == 0:
                    # If longitude is missing, ask the user for it
                    assistant_message_content = "Could you please provide the longitude?"
                else:
                    # If all required arguments are provided, get the weather data
                    weather_response = get_weather(
                        latitude=latitude,
                        longitude=longitude
                    )
                    assistant_message_content = weather_response  # Set the weather data as the response
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "get_weather",
                        "content": weather_response,
                    })
                    # Second API call: Get the final response from the AI model with the weather data included
                    final_response = client.chat.completions.create(
                        model=deployment_name,
                        messages=messages,
                    )
                    assistant_message_content = final_response.choices[0].message.content
    else:
        # If no tools were used, just return the content of the AI's response
        assistant_message_content = response_message.content

    # Add the final assistant message to the conversation history
    conversation.append({"role": "assistant", "content": assistant_message_content})

    # Return the updated conversation history as a JSON response
    return jsonify({"conversation": conversation})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)  # Run the Flask app on localhost, port 5000, with debug mode on
