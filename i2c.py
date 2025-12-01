import base64
import json

# Read an existing image file
with open('6-Reasons-To-Explore-Amusement-Parks.webp', 'rb') as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

result = {
    "base_64_image": encoded_string
}

print(json.dumps(result, indent=2))