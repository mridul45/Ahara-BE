import os
import django

# Bootstrap Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")  
# ↑ replace with your actual settings path if different
django.setup()

from django.conf import settings
from google import genai

# Create Gemini client
client = genai.Client(api_key=settings.GEMINI_API_KEY)

print("Available Gemini Models:\n")

for m in client.models.list():
    data = m.model_dump()  # Pydantic-safe way to inspect model fields
    
    name = data.get("name")
    display_name = data.get("display_name")
    description = data.get("description")
    supported_actions = data.get("supported_actions")

    print(f"Name            : {name}")
    print(f"Display Name    : {display_name}")
    print(f"Description     : {description}")
    print(f"Supported Actions: {supported_actions}")
    print("-" * 80)
