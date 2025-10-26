import os
from dotenv import load_dotenv
from google import genai

def run():
    load_dotenv()
    client = genai.Client()

    print("Welcome to the Gemini Chatbot! Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        try:
            resp = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=user_input,  # a plain string is OK
            )
            print(f"Bot: {resp.text or ''}")
        except Exception as e:
            print(f"An error occurred: {e}")

    print("\nChat session ended.")

if __name__ == "__main__":
    run()
