import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient
from firecrawl import Firecrawl
from fpdf import FPDF

# Load keys for OpenAI, Tavily, and Firecrawl
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
firecrawl_app = Firecrawl(api_key=FIRECRAWL_API_KEY)


# The Workflow Functions

# 1. get_company_info(company_name)
def get_company_info(company_name):
    """Use Tavily to search for company website and return URL + summary."""
    query = f'{company_name} official website home page'
    search_response = tavily_client.search(
        query=query,
        max_results=3
    )
    
    # Extract the top URL
    results = search_response.get('results', [])
    if not results:
        return None, "No search results found"
    
    top_url = results[0].get('url', '')
    
    # Return a summary of the top 3 search results (news/context)
    summary = ""
    for i, result in enumerate(results[:3], 1):
        summary += f"Result {i}:\n"
        summary += f"Title: {result.get('title', 'N/A')}\n"
        summary += f"URL: {result.get('url', 'N/A')}\n"
        summary += f"Content: {result.get('content', 'N/A')[:300]}...\n\n"
    
    return top_url, summary


# 2. analyze_website(url)
def analyze_website(url):
    """Use Firecrawl to scrape the URL (markdown format). Return first 5,000 characters."""
    try:
        scrape_result = firecrawl_app.scrape(url, formats=['markdown'])
        markdown_content = scrape_result.markdown if hasattr(scrape_result, 'markdown') else str(scrape_result)
        
        # Return the first 5,000 characters (to save tokens)
        return markdown_content[:5000]
    except Exception as e:
        print(f"Error scraping website: {e}")
        return ""


# 3. generate_swot(company_name, search_summary, website_content)
def generate_swot(company_name, search_summary, website_content):
    """Send all data to gpt-4o-mini to generate SWOT analysis in JSON format."""
    prompt = f"""Act as a VC Investor. Write a detailed SWOT analysis for {company_name}.

Return valid JSON with keys: 'strengths', 'weaknesses', 'opportunities', 'threats' (each a list of strings) and 'summary' (a 2-sentence overview).

Search Context:
{search_summary}

Website Content:
{website_content[:3000]}

Return ONLY valid JSON with no additional text."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    json_response = response.choices[0].message.content
    return json.loads(json_response)


# Helper function to sanitize text for PDF (remove unsupported Unicode)
def sanitize_text(text):
    """Remove or replace Unicode characters that FPDF can't handle."""
    if not text:
        return ""
    # Convert to string if not already
    text = str(text)
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2022': '-',  # bullet point
        '\u2013': '-',  # en dash
        '\u2014': '-',  # em dash
        '\u2018': "'",  # left single quote
        '\u2019': "'",  # right single quote
        '\u201C': '"',  # left double quote
        '\u201D': '"',  # right double quote
        '\u2026': '...',  # ellipsis
    }
    result = text
    for unicode_char, replacement in replacements.items():
        result = result.replace(unicode_char, replacement)
    # Remove any remaining non-ASCII characters that can't be encoded
    try:
        return result.encode('latin-1', errors='replace').decode('latin-1')
    except:
        # Fallback: just replace problematic chars
        return ''.join(c if ord(c) < 256 else '?' for c in result)


# 4. save_pdf(company_name, swot_data)
def save_pdf(company_name, swot_data):
    """Use FPDF to create a clean PDF with SWOT analysis."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Get page width (A4 width minus margins)
    effective_width = pdf.w - 2 * pdf.l_margin
    
    # Title: 'Investment Memo: {company_name}'
    pdf.set_font("Arial", "B", 20)
    pdf.cell(effective_width, 10, sanitize_text(f"Investment Memo: {company_name}"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    
    # Sections: Summary, Strengths, Weaknesses, Opportunities, Threats
    pdf.set_font("Arial", "B", 14)
    
    # Summary
    pdf.cell(effective_width, 10, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    pdf.set_x(pdf.l_margin)  # Ensure we start at left margin
    summary = swot_data.get('summary', 'No summary available.')
    pdf.multi_cell(effective_width, 6, sanitize_text(summary))
    pdf.ln(5)
    
    # Strengths
    pdf.set_font("Arial", "B", 14)
    pdf.set_x(pdf.l_margin)  # Reset to left margin
    pdf.cell(effective_width, 10, "Strengths", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    for strength in swot_data.get('strengths', []):
        # Use dash instead of bullet point to avoid encoding issues
        pdf.set_x(pdf.l_margin)  # Reset to left margin for each item
        sanitized_strength = sanitize_text(f"- {strength}")
        if sanitized_strength.strip():  # Only add if not empty
            pdf.multi_cell(effective_width, 6, sanitized_strength)
    pdf.ln(5)
    
    # Weaknesses
    pdf.set_font("Arial", "B", 14)
    pdf.set_x(pdf.l_margin)  # Reset to left margin
    pdf.cell(effective_width, 10, "Weaknesses", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    for weakness in swot_data.get('weaknesses', []):
        pdf.set_x(pdf.l_margin)  # Reset to left margin for each item
        sanitized_weakness = sanitize_text(f"- {weakness}")
        if sanitized_weakness.strip():
            pdf.multi_cell(effective_width, 6, sanitized_weakness)
    pdf.ln(5)
    
    # Opportunities
    pdf.set_font("Arial", "B", 14)
    pdf.set_x(pdf.l_margin)  # Reset to left margin
    pdf.cell(effective_width, 10, "Opportunities", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    for opportunity in swot_data.get('opportunities', []):
        pdf.set_x(pdf.l_margin)  # Reset to left margin for each item
        sanitized_opportunity = sanitize_text(f"- {opportunity}")
        if sanitized_opportunity.strip():
            pdf.multi_cell(effective_width, 6, sanitized_opportunity)
    pdf.ln(5)
    
    # Threats
    pdf.set_font("Arial", "B", 14)
    pdf.set_x(pdf.l_margin)  # Reset to left margin
    pdf.cell(effective_width, 10, "Threats", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    for threat in swot_data.get('threats', []):
        pdf.set_x(pdf.l_margin)  # Reset to left margin for each item
        sanitized_threat = sanitize_text(f"- {threat}")
        if sanitized_threat.strip():
            pdf.multi_cell(effective_width, 6, sanitized_threat)
    
    # Save as '{company_name}_Memo.pdf'
    filename = f"{company_name}_Memo.pdf"
    pdf.output(filename)
    return filename


# The Main Execution
if __name__ == "__main__":
    # Define company = 'Shopify'
    company = 'Shopify'
    
    # Print '🔍 Searching for Shopify...'
    print(f'🔍 Searching for {company}...')
    
    # Run Step 1
    url, search_summary = get_company_info(company)
    if not url:
        print(f"Error: Could not find website for {company}")
        exit(1)
    print(f"Found website: {url}")
    
    # Print '🕷️ Scraping website...'
    print('🕷️ Scraping website...')
    
    # Run Step 2
    website_content = analyze_website(url)
    print(f"Scraped {len(website_content)} characters")
    
    # Print '🧠 Analyzing data...'
    print('🧠 Analyzing data...')
    
    # Run Step 3
    swot_data = generate_swot(company, search_summary, website_content)
    print("SWOT analysis generated")
    
    # Print '📄 Generating PDF...'
    print('📄 Generating PDF...')
    
    # Run Step 4
    filename = save_pdf(company, swot_data)
    
    # Print '✅ Done! Check your folder.'
    print(f'✅ Done! Check your folder. File saved as: {filename}')
