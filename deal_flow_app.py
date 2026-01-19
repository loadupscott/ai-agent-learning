import os
import json
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient
from firecrawl import Firecrawl
from fpdf import FPDF

# Set page config to 'Wide Mode' with a title '💰 Company Analysis'
st.set_page_config(page_title="💰 Company Analysis", page_icon="💰", layout="wide")

# Load API keys from .env
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
firecrawl_app = Firecrawl(api_key=FIRECRAWL_API_KEY)


# Copy logic from analyst.py - Workflow Functions

def get_company_info(company_name):
    """Use Tavily to search for company website and return URL + comprehensive summary."""
    # Search for official website
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
    
    # Gather additional context: recent news and market information
    news_query = f'{company_name} recent news 2024 2025'
    news_response = tavily_client.search(
        query=news_query,
        max_results=5
    )
    
    # Build comprehensive summary
    summary = "=== COMPANY WEBSITE SEARCH ===\n"
    for i, result in enumerate(results[:3], 1):
        summary += f"Result {i}:\n"
        summary += f"Title: {result.get('title', 'N/A')}\n"
        summary += f"URL: {result.get('url', 'N/A')}\n"
        summary += f"Content: {result.get('content', 'N/A')[:400]}...\n\n"
    
    summary += "\n=== RECENT NEWS & MARKET CONTEXT ===\n"
    news_results = news_response.get('results', [])
    for i, result in enumerate(news_results[:5], 1):
        summary += f"News {i}:\n"
        summary += f"Title: {result.get('title', 'N/A')}\n"
        summary += f"URL: {result.get('url', 'N/A')}\n"
        summary += f"Content: {result.get('content', 'N/A')[:400]}...\n\n"
    
    return top_url, summary


def analyze_website(url):
    """Use Firecrawl to scrape the URL (markdown format). Return first 5,000 characters."""
    try:
        scrape_result = firecrawl_app.scrape(url, formats=['markdown'])
        markdown_content = scrape_result.markdown if hasattr(scrape_result, 'markdown') else str(scrape_result)
        
        # Return the first 5,000 characters (to save tokens)
        return markdown_content[:5000]
    except Exception as e:
        st.error(f"Error scraping website: {e}")
        return ""


def generate_swot(company_name, search_summary, website_content):
    """Generate sophisticated investment analysis using gpt-4o for deeper insights."""
    prompt = f"""You are a senior partner at a top-tier venture capital firm with 20+ years of experience evaluating companies. 
You are preparing an investment memo for {company_name} that will be presented to sophisticated investors, LPs, and board members.

Your analysis must be:
- Deeply analytical with specific evidence and reasoning
- Nuanced, avoiding generic statements
- Focused on strategic implications and competitive positioning
- Forward-looking with clear risk assessment
- Professional and investment-grade quality

Based on the following information, provide a comprehensive investment analysis.

SEARCH CONTEXT & MARKET DATA:
{search_summary}

WEBSITE CONTENT:
{website_content[:4000]}

Return valid JSON with the following structure:
{{
    "executive_summary": "A 3-4 sentence executive summary that captures the investment thesis, key value drivers, and primary risks",
    "strengths": [
        "Each strength should be specific, evidence-based, and explain WHY it matters strategically. Include competitive advantages, unique capabilities, market position, etc."
    ],
    "weaknesses": [
        "Each weakness should be specific and explain the strategic implications. Include operational gaps, market vulnerabilities, resource constraints, etc."
    ],
    "opportunities": [
        "Each opportunity should be specific, addressable, and explain the potential impact. Include market trends, expansion possibilities, strategic moves, etc."
    ],
    "threats": [
        "Each threat should be specific and explain the potential impact on the business. Include competitive threats, market shifts, regulatory risks, etc."
    ],
    "market_analysis": "2-3 sentences on the company's market position, competitive landscape, and market dynamics",
    "strategic_recommendations": [
        "2-3 specific strategic recommendations for the company based on your analysis"
    ],
    "investment_considerations": "2-3 sentences on key factors an investor should consider (valuation, timing, risk profile, etc.)"
}}

Be specific, analytical, and sophisticated. Avoid generic statements. Use the provided context to ground your analysis in facts."""

    response = openai_client.chat.completions.create(
        model="gpt-4o",  # Use gpt-4o for more sophisticated analysis
        messages=[
            {"role": "system", "content": "You are a senior VC partner with deep expertise in company analysis and investment evaluation. Your analysis is always thorough, evidence-based, and strategic."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.7  # Slightly higher for more nuanced analysis
    )
    
    json_response = response.choices[0].message.content
    return json.loads(json_response)


def sanitize_text(text):
    """Remove or replace Unicode characters that FPDF can't handle."""
    if not text:
        return ""
    text = str(text)
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
    try:
        return result.encode('latin-1', errors='replace').decode('latin-1')
    except:
        return ''.join(c if ord(c) < 256 else '?' for c in result)


def save_pdf(company_name, swot_data):
    """Use FPDF to create a clean PDF with SWOT analysis."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    effective_width = pdf.w - 2 * pdf.l_margin
    
    # Title
    pdf.set_font("Arial", "B", 20)
    pdf.cell(effective_width, 10, sanitize_text(f"Investment Memo: {company_name}"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    
    # Sections
    pdf.set_font("Arial", "B", 14)
    
    # Executive Summary
    pdf.cell(effective_width, 10, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    pdf.set_x(pdf.l_margin)
    executive_summary = swot_data.get('executive_summary', swot_data.get('summary', 'No summary available.'))
    pdf.multi_cell(effective_width, 6, sanitize_text(executive_summary))
    pdf.ln(5)
    
    # Market Analysis
    market_analysis = swot_data.get('market_analysis', '')
    if market_analysis:
        pdf.set_font("Arial", "B", 14)
        pdf.set_x(pdf.l_margin)
        pdf.cell(effective_width, 10, "Market Analysis", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Arial", "", 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_width, 6, sanitize_text(market_analysis))
        pdf.ln(5)
    
    # Strengths
    pdf.set_font("Arial", "B", 14)
    pdf.set_x(pdf.l_margin)
    pdf.cell(effective_width, 10, "Strengths", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    for strength in swot_data.get('strengths', []):
        pdf.set_x(pdf.l_margin)
        sanitized_strength = sanitize_text(f"- {strength}")
        if sanitized_strength.strip():
            pdf.multi_cell(effective_width, 6, sanitized_strength)
    pdf.ln(5)
    
    # Weaknesses
    pdf.set_font("Arial", "B", 14)
    pdf.set_x(pdf.l_margin)
    pdf.cell(effective_width, 10, "Weaknesses", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    for weakness in swot_data.get('weaknesses', []):
        pdf.set_x(pdf.l_margin)
        sanitized_weakness = sanitize_text(f"- {weakness}")
        if sanitized_weakness.strip():
            pdf.multi_cell(effective_width, 6, sanitized_weakness)
    pdf.ln(5)
    
    # Opportunities
    pdf.set_font("Arial", "B", 14)
    pdf.set_x(pdf.l_margin)
    pdf.cell(effective_width, 10, "Opportunities", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    for opportunity in swot_data.get('opportunities', []):
        pdf.set_x(pdf.l_margin)
        sanitized_opportunity = sanitize_text(f"- {opportunity}")
        if sanitized_opportunity.strip():
            pdf.multi_cell(effective_width, 6, sanitized_opportunity)
    pdf.ln(5)
    
    # Threats
    pdf.set_font("Arial", "B", 14)
    pdf.set_x(pdf.l_margin)
    pdf.cell(effective_width, 10, "Threats", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 11)
    for threat in swot_data.get('threats', []):
        pdf.set_x(pdf.l_margin)
        sanitized_threat = sanitize_text(f"- {threat}")
        if sanitized_threat.strip():
            pdf.multi_cell(effective_width, 6, sanitized_threat)
    pdf.ln(5)
    
    # Strategic Recommendations
    strategic_recs = swot_data.get('strategic_recommendations', [])
    if strategic_recs:
        pdf.set_font("Arial", "B", 14)
        pdf.set_x(pdf.l_margin)
        pdf.cell(effective_width, 10, "Strategic Recommendations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Arial", "", 11)
        for rec in strategic_recs:
            pdf.set_x(pdf.l_margin)
            sanitized_rec = sanitize_text(f"- {rec}")
            if sanitized_rec.strip():
                pdf.multi_cell(effective_width, 6, sanitized_rec)
        pdf.ln(5)
    
    # Investment Considerations
    investment_considerations = swot_data.get('investment_considerations', '')
    if investment_considerations:
        pdf.set_font("Arial", "B", 14)
        pdf.set_x(pdf.l_margin)
        pdf.cell(effective_width, 10, "Investment Considerations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Arial", "", 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_width, 6, sanitize_text(investment_considerations))
    
    filename = f"{company_name}_Memo.pdf"
    pdf.output(filename)
    return filename


# The Sidebar
st.sidebar.header('💰 Company Analysis')
company_name = st.sidebar.text_input('Company Name', placeholder='Enter company name...')
generate_button = st.sidebar.button('Generate Memo', type='primary')


# The Main Area (Logic)
if generate_button:
    if not company_name:
        st.error('⚠️ Please enter a company name')
    else:
        # Show progress with status spinner
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Get company info
            status_text.text('🔍 Searching for company information...')
            progress_bar.progress(25)
            url, search_summary = get_company_info(company_name)
            
            if not url:
                st.error(f'❌ Could not find website for {company_name}')
            else:
                # Step 2: Analyze website
                status_text.text('🕷️ Scraping company website...')
                progress_bar.progress(50)
                website_content = analyze_website(url)
                
                # Step 3: Generate Analysis
                status_text.text('🧠 Analyzing data and generating company analysis...')
                progress_bar.progress(75)
                swot_data = generate_swot(company_name, search_summary, website_content)
                
                progress_bar.progress(100)
                status_text.text('✅ Analysis complete!')
                progress_bar.empty()
                status_text.empty()
                
                # Display the Executive Summary at the top in a colored box
                executive_summary = swot_data.get('executive_summary', swot_data.get('summary', 'No summary available.'))
                st.info(f"**📋 Executive Summary:** {executive_summary}")
                
                st.markdown("---")
                
                # Display Market Analysis if available
                market_analysis = swot_data.get('market_analysis', '')
                if market_analysis:
                    st.markdown("### 📊 Market Analysis")
                    st.markdown(market_analysis)
                    st.markdown("---")
                
                # Display the SWOT analysis in 4 clear columns using st.columns(4)
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("### ✅ Strengths")
                    strengths = swot_data.get('strengths', [])
                    if strengths:
                        for strength in strengths:
                            st.markdown(f"• {strength}")
                    else:
                        st.markdown("*No strengths listed*")
                
                with col2:
                    st.markdown("### ⚠️ Weaknesses")
                    weaknesses = swot_data.get('weaknesses', [])
                    if weaknesses:
                        for weakness in weaknesses:
                            st.markdown(f"• {weakness}")
                    else:
                        st.markdown("*No weaknesses listed*")
                
                with col3:
                    st.markdown("### 🚀 Opportunities")
                    opportunities = swot_data.get('opportunities', [])
                    if opportunities:
                        for opportunity in opportunities:
                            st.markdown(f"• {opportunity}")
                    else:
                        st.markdown("*No opportunities listed*")
                
                with col4:
                    st.markdown("### 🛡️ Threats")
                    threats = swot_data.get('threats', [])
                    if threats:
                        for threat in threats:
                            st.markdown(f"• {threat}")
                    else:
                        st.markdown("*No threats listed*")
                
                st.markdown("---")
                
                # Display Strategic Recommendations if available
                strategic_recs = swot_data.get('strategic_recommendations', [])
                if strategic_recs:
                    st.markdown("### 💡 Strategic Recommendations")
                    for rec in strategic_recs:
                        st.markdown(f"• {rec}")
                    st.markdown("---")
                
                # Display Investment Considerations if available
                investment_considerations = swot_data.get('investment_considerations', '')
                if investment_considerations:
                    st.markdown("### 💰 Investment Considerations")
                    st.markdown(investment_considerations)
                    st.markdown("---")
                
                # Generate the PDF in the background
                with st.spinner('📄 Generating PDF...'):
                    pdf_filename = save_pdf(company_name, swot_data)
                    
                    # Read the PDF file
                    with open(pdf_filename, 'rb') as pdf_file:
                        pdf_bytes = pdf_file.read()
                
                # Show a large 'Download PDF' button using st.download_button
                st.download_button(
                    label='📥 Download Investment Memo PDF',
                    data=pdf_bytes,
                    file_name=pdf_filename,
                    mime='application/pdf',
                    use_container_width=True
                )
                
        except Exception as e:
            st.error(f'❌ Error: {str(e)}')
            progress_bar.empty()
            status_text.empty()

else:
    # Initial state - show welcome message
    st.title('💰 Company Analysis')
    st.markdown("""
    ### Welcome to the Company Analysis Memo Generator! 📊
    
    **Instructions:**
    1. Enter a company name in the sidebar
    2. Click "Generate Memo" to create a comprehensive company analysis
    3. Review the analysis and download the PDF memo
    
    Get started by entering a company name in the sidebar! 👈
    """)
