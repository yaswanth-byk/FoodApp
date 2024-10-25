import os
import openai
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from config import OPENAI_API_KEY
import json
import random
from pymongo import MongoClient
from dotenv import load_dotenv
import re



# Ensure the OpenAI API key is available
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API key not found. Make sure it's set in your environment as 'OPENAI_API_KEY'.")

# Initialize the ChatOpenAI model with the API key
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7, openai_api_key=OPENAI_API_KEY)

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')  # Replace with your MongoDB URI if hosted elsewhere
db = client['Foodservices']
fooditems_collection = db['Fooditems']
orders_collection = db['Orders']

# Template for the prompt
prompt_template = """
You are a helpful assistant specialized in providing food recommendations and assisting with food ordering.

Given the user's query: {user_query}

Here are the available food items:
{food_items}

Respond with a list of food recommendations based on the user's query, but strictly use the food items provided above.
"""

# Create a prompt template
prompt = PromptTemplate(input_variables=["user_query", "food_items"], template=prompt_template)

# In-memory storage for order details (this would normally be a database)
order_sessions = {}

def generate_order_id():
    """Function to generate a random Order ID"""
    return f"#{random.randint(10000, 99999)}"

def store_order_to_db(order_details):
    """Function to store the order details to MongoDB"""
    try:
        order_id = generate_order_id()
        order_details['order_id'] = order_id
        # Insert the order into the Orders collection
        orders_collection.insert_one(order_details)
        return order_id
    except Exception as e:
        raise Exception(f"Failed to store order: {str(e)}")
    
def cancel_order_in_db(order_id):
    """Function to cancel an order in MongoDB using the order ID"""
    try:
        print(f"Attempting to cancel order with ID: {order_id}")

        # Check what is being passed to the delete_one
        print(f"Searching for: {{'order_id': {order_id}}}")

        result = orders_collection.delete_one({"order_id": order_id})
        
        print(f"Delete operation result: {result.deleted_count} document(s) deleted.")  # Debugging line
        
        if result.deleted_count > 0:
            return {"success": True, "message": f"Order {order_id} has been cancelled successfully."}
        else:
            return {"success": False, "message": f"No order found with ID {order_id}."}
    except Exception as e:
        return {"success": False, "message": f"Error cancelling order: {str(e)}"}
    
def get_order_details_from_db(order_id):
    """Function to fetch order details from MongoDB using the order ID and fetch image URL from Fooditems collection"""
    try:
        # Search for the order in the Orders collection
        order_details = orders_collection.find_one({'order_id': order_id})

        if order_details:
            # Fetch the image URL from the Fooditems collection based on fooditem_name
            fooditem_name = order_details.get('fooditem_name')
            food_item = fooditems_collection.find_one({'name': fooditem_name}, {'imageUrl': 1})
            image_url = food_item.get('imageUrl', '') if food_item else ''

            # Format the order details as a dictionary (similar to recommendations)
            formatted_order_details = {
                "order_id": order_details.get('order_id'),
                "food_item": order_details.get('fooditem_name'),
                "name": order_details.get('Name'),
                "phone_number": order_details.get('phone_number'),
                "email": order_details.get('email'),
                "quantity": order_details.get('quantity'),
                "delivery_address": order_details.get('delivery_address'),
            }

            return formatted_order_details
        else:
            return {"error": "No order found with the provided Order ID."}
    except Exception as e:
        print(f"Error fetching order details: {str(e)}")  # Debug log
        return {"error": f"Error fetching order details: {str(e)}"}

def get_recommendation_from_db():
    """Function to get food recommendations from MongoDB"""
    try:
        print("Fetching food items from MongoDB...")  # Debug log
        food_items = fooditems_collection.find({}, {'name': 1, 'description': 1, 'cuisine': 1, 'price': 1, 'spiceLevel': 1, 'imageUrl': 1})
        recommendations = []
        for item in food_items:
            recommendations.append({
                "name": item['name'],
                "description": item['description'],
                "cuisine": item['cuisine'],
                "price": item['price'],
                "spiceLevel": item['spiceLevel'],
                "imageUrl": item.get('imageUrl', '')
            })
        print(f"Retrieved Recommendations: {recommendations}")  # Debug log
        return recommendations
    except Exception as e:
        print(f"Error fetching recommendations: {str(e)}")  # Debug log
        return []

def get_food_recommendation_with_db(user_query, session_id):
    try:
        
        cancel_order_regex = r'^cancel order #(\d+)$'
        cancel_match = re.match(cancel_order_regex, user_query, re.IGNORECASE)

        if cancel_match:
            order_id = f"#{cancel_match.group(1)}"
            # Fetch order details from MongoDB
            order_details = get_order_details_from_db(order_id)

            if order_details:
                # Store the pending cancellation order ID
                order_sessions[session_id] = {'pending_cancel_id': order_id}

                # Ask for confirmation to cancel the order
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": f"Are you sure you want to cancel the order with ID {order_id}? Please confirm by replying with 'yes' or 'no'."
                }, indent=4)
            else:
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": f"Sorry, no order found with Order ID {order_id}. Please check the ID and try again."
                }, indent=4)

        # Check for confirmation response
        if "yes" in user_query.lower() and session_id in order_sessions:
            order_id = order_sessions[session_id]['pending_cancel_id']
            print(order_id)
            cancel_result = cancel_order_in_db(order_id)

            # Clear the pending cancel ID
            del order_sessions[session_id]['pending_cancel_id']

            return json.dumps({
                "user_query": user_query,
                "bot_response": cancel_result['message']
            }, indent=4)

        if "no" in user_query.lower() and session_id in order_sessions:
            # Clear the pending cancel ID
            del order_sessions[session_id]['pending_cancel_id']

            return json.dumps({
                "user_query": user_query,
                "bot_response": "Order cancellation has been aborted."
            }, indent=4)
    
    
        # Respond with a greeting if the user input is a common greeting
        if "fetch order with order id" in user_query.lower():
            # Extract the order ID from the user query
            order_id = user_query.lower().replace("fetch order with order id", "").strip()

            # Fetch order details from MongoDB
            order_details = get_order_details_from_db(order_id)

            if order_details:
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": f"Here are the details for Order ID {order_id}:\n{order_details}"
                }, indent=4)
            else:
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": f"Sorry, no order found with Order ID {order_id}. Please check the ID and try again."
                }, indent=4)
            
        # Respond with a greeting if the user input is a common greeting
        if user_query.strip().lower() in ["hi", "hello", "hey"]:
            return json.dumps({
                "user_query": user_query,
                "bot_response": "Hi! How can I help you today? You can ask me for food recommendations."
            }, indent=4)

        # Check if the user is already in an order session
        if session_id in order_sessions and order_sessions[session_id]['collecting_order']:
            print(f"Session ID {session_id} - Collecting order details...")  # Debug log
            # We're in the process of collecting order details
            order_details = order_sessions[session_id]

            if 'fooditem_name' not in order_details:
                print(f"Session ID {session_id} - Asking for food item name...")  # Debug log
                order_sessions[session_id]['fooditem_name'] = user_query
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": "Great! Let's continue. Please provide your first name."
                }, indent=4)

            if 'Name' not in order_details:
                print(f"Session ID {session_id} - Asking for user name...")  # Debug log
                order_sessions[session_id]['Name'] = user_query
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": "Great! Now, please provide your phone number."
                }, indent=4)

            elif 'phone_number' not in order_details:
                print(f"Session ID {session_id} - Asking for phone number...")  # Debug log
                order_sessions[session_id]['phone_number'] = user_query
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": "Thanks! Now, please provide your email address."
                }, indent=4)

            elif 'email' not in order_details:
                print(f"Session ID {session_id} - Asking for email address...")  # Debug log
                order_sessions[session_id]['email'] = user_query
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": "Please, provide your Credit Card Details"
                }, indent=4)

            elif 'creditcard' not in order_details:
                print(f"Session ID {session_id} - Asking for credit card details...")  # Debug log
                order_sessions[session_id]['creditcard'] = user_query
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": "Great! How many portions or quantity of food would you like to order?"
                }, indent=4)

            elif 'quantity' not in order_details:
                print(f"Session ID {session_id} - Asking for quantity...")  # Debug log
                order_sessions[session_id]['quantity'] = user_query  # Storing the quantity
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": "Almost done! Please provide your delivery address."
                }, indent=4)

            elif 'delivery_address' not in order_details:
                print(f"Session ID {session_id} - Asking for delivery address...")  # Debug log
                # Once delivery address is provided, generate order ID and store in DB
                order_sessions[session_id]['delivery_address'] = user_query
                # Store order to MongoDB
                order_id = store_order_to_db(order_sessions[session_id])
                print(f"Session ID {session_id} - Order placed with ID {order_id}.")  # Debug log
                del order_sessions[session_id]  # Clear the session after storing
                return json.dumps({
                    "user_query": user_query,
                    "bot_response": f"Order placed successfully. Your Order ID is {order_id}. Thank you for ordering with us!"
                }, indent=4)

        # If user is placing an order, start collecting details
        if "place an order for" in user_query.lower() or "order" in user_query.lower():
            print(f"Session ID {session_id} - Starting new order session...")  # Debug log
            order_sessions[session_id] = {'collecting_order': True}
            return json.dumps({
                "user_query": user_query,
                "bot_response": "Please specify the food item you'd like to order."
            }, indent=4)

        # Get food recommendations from MongoDB
        db_recommendations = get_recommendation_from_db()

        # Check if recommendations are fetched
        if not db_recommendations:
            return json.dumps({
                "user_query": user_query,
                "bot_response": "I'm sorry, but there are no specific food recommendations available at the moment."
            }, indent=4)

        # Enhanced filtering logic (this remains as is, filtering food items based on user query)
        filtered_recommendations = []
        query_lower = user_query.lower()

        for item in db_recommendations:
            # Logic to filter food items based on query
            if ('medium' in query_lower and item['spiceLevel'].lower() == 'medium') or \
               ('mild' in query_lower and item['spiceLevel'].lower() == 'mild') or \
               ('spicy' in query_lower and item['spiceLevel'].lower() == 'spicy') or \
               (item['cuisine'].lower() in query_lower) or \
               (item['name'].lower() in query_lower) or \
               ('sauce' in query_lower and 'sauce' in item['name'].lower()) or \
               ('pizza' in query_lower and 'pizza' in item['name'].lower()) or \
               ('price' in query_lower and str(item.get('price', '')).lower() in query_lower):

                filtered_recommendations.append(item)

        # Load environment variables from .env file
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")

        # Initialize the OpenAI client with the API key
        openai_client = openai.Client(api_key=api_key)

        # Check if API key is loaded correctly
        if not api_key:
            raise ValueError("OpenAI API key not found. Ensure it's set correctly in the .env file.")
        else:
            print(f"OpenAI API Key loaded: {api_key}")

        # Format the response with image URLs in a structured way
        recommendations_list = [
            f"{item['name']} - {item['description']}. Price: ${item['price']} (Spice Level: {item['spiceLevel']}) ![Image]({item['imageUrl']})"
            for item in filtered_recommendations
        ]

        # Detect the intent behind the user query
        def detect_intent(user_query):
            query_lower = user_query.lower()
            if "recommend" in query_lower or "suggest" in query_lower:
                return "recommendation"
            elif "ingredient" in query_lower or "contain" in query_lower or "have" in query_lower:
                return "ingredient"
            elif "spicy" in query_lower or "mild" in query_lower or "cuisine" in query_lower:
                return "preferences"
            else:
                return "general"

        intent = detect_intent(user_query)

        if recommendations_list:
                bot_response = "Here are some food recommendations:\n" + "\n".join(recommendations_list)

        elif intent == "recommendation" and recommendations_list:

            bot_response = "Here are some food recommendations:\n" + "\n".join(recommendations_list)

        else:
                try:
                    # Use OpenAI completion to generate a friendly response if no recommendations
                    response = openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": (
                                "You are an intelligent and friendly assistant for a food ordering app. "
                                "Your goal is to understand the user's requests about food recommendations, ingredients, preferences, and dietary needs. "
                                "Use a conversational tone, offer suggestions based on cuisine, dietary preferences, or popular dishes, and engage the user with relevant questions if necessary. "
                                "If the user asks for recommendations, respond with options that reflect their stated or implied tastes and preferences. "
                                "If no food data is available, apologize and suggest alternative help."
                            )},
                            {"role": "user", "content": (
                                "The user has asked for food recommendations, but no specific recommendations are currently available in the database. "
                                "Create a friendly, proactive response to keep the conversation going and help the user find what they’re looking for. "
                                "Ask about preferences, dietary restrictions, or any specific cuisines they enjoy. If the user wants general advice, offer popular choices, and encourage further questions."
                            )}
                        ],
                        max_tokens=100,
                        temperature=0.7
                    )

                    # Extract the response content
                    bot_response = response.choices[0].message.content.strip()

                except Exception as e:
                    # Handle any errors with the OpenAI API call
                    bot_response = "I'm having trouble generating a response right now. Please try again later."
                    error_log = f"OpenAI API Error: {e}"
                    # Optionally, log error details to a log file or monitoring system here

        # Print or return the bot_response
        print(bot_response)

        json_response = {
            "user_query": user_query,
            "bot_response": bot_response
        }

        return json.dumps(json_response, indent=4)

    except Exception as e:
        print(f"Error in processing request: {str(e)}")  # Debug log
        error_response = {
            "error": str(e)
        }
        return json.dumps(error_response, indent=4)