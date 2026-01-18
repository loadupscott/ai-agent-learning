import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from firecrawl import Firecrawl

# Load OPENAI_API_KEY and FIRECRAWL_API_KEY from .env
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
app = Firecrawl(api_key=FIRECRAWL_API_KEY)

# Define a variable url (set it to 'https://vibecodeapp.com' or any startup website you like)
url = 'https://vibecodeapp.com'

# Step 1 (Scrape): Use app.scrape(url, formats=['markdown']) to get the page content
print(f"Step 1: Scraping {url}...")

# Error Handling: Wrap the scrape in a try/except block in case the URL is blocked
try:
    scrape_result = app.scrape(url, formats=['markdown'])
    
    # Extract markdown content from the result object
    markdown_content = scrape_result.markdown if hasattr(scrape_result, 'markdown') else str(scrape_result)
    
    # Print 'Scraping complete. Content length: [length] characters'
    content_length = len(markdown_content)
    print(f"Scraping complete. Content length: {content_length} characters")
    
except Exception as e:
    print(f"Error scraping URL: {e}")
    print("Exiting due to scraping failure.")
    exit(1)

# Step 2 (Analyze): Send the markdown content to gpt-4o-mini
print("\nStep 2: Analyzing content with GPT-4o-mini...")

prompt = """You are a Market Research Expert. Analyze this landing page content. Extract the following in strict JSON format:

"company_name"
"value_proposition" (1 sentence)
"pricing_model" (Summary of their plans)
"target_audience"

Return ONLY valid JSON with no additional text."""

response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": f"{prompt}\n\nLanding page content:\n{markdown_content}"}
    ],
    response_format={"type": "json_object"}  # Ensure JSON response
)

# Extract and parse JSON
json_response = response.choices[0].message.content

# Print the JSON output clearly
print("\n" + "="*60)
print("Strategic Insights (JSON):")
print("="*60)
try:
    # Try to parse and pretty-print JSON
    parsed_json = json.loads(json_response)
    print(json.dumps(parsed_json, indent=2))
except json.JSONDecodeError:
    # If parsing fails, print raw response
    print(json_response)
print("="*60 + "\n")
