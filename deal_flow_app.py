import os
import json
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient
from firecrawl import Firecrawl
from fpdf import FPDF
import yfinance as yf

# Set page config to 'Wide Mode' with a title '💰 Scott's Company Analysis'
st.set_page_config(page_title="💰 Scott's Company Analysis", page_icon="💰", layout="wide")

# Load API keys from .env
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
firecrawl_app = Firecrawl(api_key=FIRECRAWL_API_KEY)


# Helper Functions for Stock Data

def get_ticker_symbol(company_name):
    """Use GPT to determine if company is publicly traded and return ticker symbol with exchange suffix."""
    prompt = f"""Determine if "{company_name}" is a publicly traded company.

If it IS publicly traded, return the stock ticker symbol with the appropriate Yahoo Finance suffix for the PRIMARY exchange where it trades:
- US stocks (NYSE, NASDAQ): just the ticker (e.g., "AAPL", "MSFT")
- Canadian stocks (TSX): add .TO suffix (e.g., "RY.TO" for Royal Bank of Canada, "SHOP.TO" for Shopify on TSX)
- Canadian stocks (TSX Venture): add .V suffix (e.g., "XYZ.V")
- London Stock Exchange: add .L suffix (e.g., "HSBA.L")
- Tokyo Stock Exchange: add .T suffix (e.g., "7203.T" for Toyota)
- Hong Kong: add .HK suffix (e.g., "0700.HK")
- Frankfurt: add .DE suffix (e.g., "BMW.DE")
- Paris: add .PA suffix (e.g., "MC.PA" for LVMH)
- Australian: add .AX suffix (e.g., "CBA.AX")

For companies listed on multiple exchanges, prefer their home country exchange.

If it is NOT publicly traded (private company), return "PRIVATE".

Return ONLY the ticker symbol (with suffix if needed) or "PRIVATE", nothing else."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a financial expert. Return only the ticker symbol with appropriate exchange suffix, or PRIVATE."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    result = response.choices[0].message.content.strip().upper()
    return None if result == "PRIVATE" else result


def fetch_stock_data(ticker):
    """Use yfinance to fetch stock data for a given ticker."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Get historical data for 1-year return calculation
        hist = stock.history(period="1y")
        year_return = None
        if len(hist) >= 2:
            start_price = hist['Close'].iloc[0]
            end_price = hist['Close'].iloc[-1]
            year_return = ((end_price - start_price) / start_price) * 100

        # Get last trade time
        last_trade_time = None
        market_time = info.get("regularMarketTime")
        if market_time:
            last_trade_time = datetime.fromtimestamp(market_time).strftime("%b %d, %I:%M %p")

        # Get exchange and currency info
        exchange = info.get("exchange", "")
        currency = info.get("currency", "USD")

        # Map exchange codes to friendly names
        exchange_names = {
            "NMS": "NASDAQ",
            "NYQ": "NYSE",
            "NGM": "NASDAQ",
            "TOR": "TSX",
            "TSX": "TSX",
            "VAN": "TSX-V",
            "LSE": "LSE",
            "LON": "LSE",
            "FRA": "Frankfurt",
            "PAR": "Euronext Paris",
            "HKG": "HKEX",
            "JPX": "Tokyo",
            "TYO": "Tokyo",
            "ASX": "ASX",
        }
        exchange_display = exchange_names.get(exchange, exchange)

        # Currency symbols (use $ for USD and CAD since users know TSX is in CAD)
        currency_symbols = {
            "USD": "$",
            "CAD": "$",
            "GBP": "£",
            "EUR": "€",
            "JPY": "¥",
            "HKD": "HK$",
            "AUD": "A$",
            "CHF": "CHF ",
        }
        currency_symbol = currency_symbols.get(currency, f"{currency} ")

        return {
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "year_return": year_return,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "employees": info.get("fullTimeEmployees"),
            "dividend_yield": info.get("trailingAnnualDividendYield") or (info.get("dividendYield") / 100 if info.get("dividendYield") and info.get("dividendYield") > 1 else info.get("dividendYield")),
            "beta": info.get("beta"),
            "revenue": info.get("totalRevenue"),
            "profit_margin": info.get("profitMargins"),
            "ticker": ticker,
            "last_trade_time": last_trade_time,
            "exchange": exchange_display,
            "currency": currency,
            "currency_symbol": currency_symbol
        }
    except Exception as e:
        st.warning(f"Could not fetch stock data: {e}")
        return None


def format_market_cap(value):
    """Format large numbers as '$150.2B' style strings."""
    if value is None:
        return "N/A"
    if value >= 1e12:
        return f"${value/1e12:.2f}T"
    elif value >= 1e9:
        return f"${value/1e9:.2f}B"
    elif value >= 1e6:
        return f"${value/1e6:.2f}M"
    else:
        return f"${value:,.0f}"


def format_number(value, prefix="", suffix="", decimals=2):
    """Format numbers with optional prefix/suffix."""
    if value is None:
        return "N/A"
    return f"{prefix}{value:,.{decimals}f}{suffix}"


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


def generate_swot(company_name, search_summary, website_content, stock_data=None):
    """Generate sophisticated investment analysis using gpt-4o for deeper insights."""

    # Build stock context if available
    stock_context = ""
    if stock_data:
        curr_sym = stock_data.get('currency_symbol', '$')
        low_52 = stock_data.get('fifty_two_week_low')
        high_52 = stock_data.get('fifty_two_week_high')
        range_str = f"{curr_sym}{low_52:.2f} - {curr_sym}{high_52:.2f}" if low_52 and high_52 else "N/A"
        price = stock_data.get('current_price')
        price_str = f"{curr_sym}{price:.2f}" if price else "N/A"
        stock_context = f"""
FINANCIAL METRICS (Live Market Data):
- Stock Ticker: {stock_data.get('ticker', 'N/A')}
- Current Price: {price_str}
- Market Cap: {format_market_cap(stock_data.get('market_cap'))}
- 1-Year Return: {format_number(stock_data.get('year_return'), suffix='%') if stock_data.get('year_return') else 'N/A'}
- P/E Ratio: {format_number(stock_data.get('pe_ratio'), decimals=1) if stock_data.get('pe_ratio') else 'N/A'}
- 52-Week Range: {range_str}
- Sector: {stock_data.get('sector', 'N/A')}
- Industry: {stock_data.get('industry', 'N/A')}
- Employees: {f"{stock_data.get('employees'):,}" if stock_data.get('employees') else 'N/A'}
- Beta: {format_number(stock_data.get('beta'), decimals=2) if stock_data.get('beta') else 'N/A'}
"""
    else:
        stock_context = "\nNote: This is a PRIVATE company - no public stock data available.\n"

    prompt = f"""You are a senior partner at a top-tier venture capital firm with 20+ years of experience evaluating companies.
You are preparing an investment memo for {company_name} that will be presented to sophisticated investors, LPs, and board members.

Your analysis must be:
- Deeply analytical with specific evidence and reasoning
- Nuanced, avoiding generic statements
- Focused on strategic implications and competitive positioning
- Forward-looking with clear risk assessment
- Professional and investment-grade quality

Based on the following information, provide a comprehensive investment analysis.
{stock_context}
SEARCH CONTEXT & MARKET DATA:
{search_summary}

WEBSITE CONTENT:
{website_content[:4000]}

Return valid JSON with the following structure:
{{
    "executive_summary": "A 3-4 sentence executive summary that captures the investment thesis, key value drivers, and primary risks",
    "risk_rating": "One of: LOW, MEDIUM, or HIGH - based on your overall assessment of investment risk",
    "investment_verdict": "One of: BUY, HOLD, SELL, or WATCH - your recommendation for investors",
    "strengths": [
        "Each strength should be specific, evidence-based, and explain WHY it matters strategically (3-5 items)"
    ],
    "weaknesses": [
        "Each weakness should be specific and explain the strategic implications (3-5 items)"
    ],
    "opportunities": [
        "Each opportunity should be specific, addressable, and explain the potential impact (3-5 items)"
    ],
    "threats": [
        "Each threat should be specific and explain the potential impact on the business (3-5 items)"
    ],
    "market_analysis": "2-3 sentences on the company's market position, competitive landscape, and market dynamics",
    "strategic_recommendations": [
        "3-4 specific, actionable strategic recommendations based on your analysis"
    ],
    "investment_considerations": "2-3 sentences on key factors an investor should consider (valuation, timing, risk profile, etc.)"
}}

IMPORTANT:
- Be specific and evidence-based. Cite specific products, metrics, or news when possible.
- Each SWOT item should be 1-2 sentences with clear strategic implications.
- Your risk_rating and investment_verdict should be consistent with your analysis.
- For public companies, factor in the financial metrics provided."""

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


def save_pdf(company_name, swot_data, stock_data=None):
    """Use FPDF to create a clean PDF with SWOT analysis and financial metrics."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    effective_width = pdf.w - 2 * pdf.l_margin

    # Format company name with title case
    display_name = company_name.title()

    # Title with exchange:ticker for public companies
    pdf.set_font("Arial", "B", 20)
    if stock_data and stock_data.get('ticker'):
        exchange = stock_data.get('exchange', '')
        ticker_display = stock_data.get('ticker', '')
        ticker_clean = ticker_display.split('.')[0] if '.' in ticker_display else ticker_display
        ticker_info = f"{exchange}: {ticker_clean}" if exchange else ticker_clean
        pdf.cell(effective_width, 10, sanitize_text(f"Investment Memo: {display_name} ({ticker_info})"), new_x="LMARGIN", new_y="NEXT", align="C")
    else:
        pdf.cell(effective_width, 10, sanitize_text(f"Investment Memo: {display_name}"), new_x="LMARGIN", new_y="NEXT", align="C")

    # Generation date
    pdf.set_font("Arial", "I", 10)
    pdf.cell(effective_width, 6, f"Generated: {datetime.now().strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(8)

    # Investment Verdict & Risk Rating
    risk_rating = swot_data.get('risk_rating', 'N/A')
    investment_verdict = swot_data.get('investment_verdict', 'N/A')
    pdf.set_font("Arial", "B", 12)
    pdf.cell(effective_width, 8, sanitize_text(f"Investment Verdict: {investment_verdict}  |  Risk Rating: {risk_rating}"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    # Financial Metrics Section (for public companies)
    if stock_data and stock_data.get('current_price'):
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(0, 51, 102)  # Dark blue
        pdf.cell(effective_width, 10, "Financial Metrics", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)  # Reset to black
        pdf.set_font("Arial", "", 11)

        # Get currency symbol
        curr_sym = stock_data.get('currency_symbol', '$')

        # Create a metrics summary line
        exchange = stock_data.get('exchange', '')
        ticker_display = stock_data.get('ticker', '')
        ticker_clean = ticker_display.split('.')[0] if '.' in ticker_display else ticker_display
        ticker_info = f"{exchange}: {ticker_clean}" if exchange else ticker_clean
        metrics_line1 = f"Ticker: {ticker_info}  |  Price: {curr_sym}{stock_data.get('current_price', 'N/A'):.2f}  |  Market Cap: {format_market_cap(stock_data.get('market_cap'))}"
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_width, 6, sanitize_text(metrics_line1))

        year_return = stock_data.get('year_return')
        pe_ratio = stock_data.get('pe_ratio')
        metrics_line2 = f"1-Year Return: {year_return:.1f}%" if year_return else "1-Year Return: N/A"
        metrics_line2 += f"  |  P/E Ratio: {pe_ratio:.1f}" if pe_ratio else "  |  P/E Ratio: N/A"
        metrics_line2 += f"  |  Sector: {stock_data.get('sector', 'N/A')}"
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_width, 6, sanitize_text(metrics_line2))

        low_52 = stock_data.get('fifty_two_week_low')
        high_52 = stock_data.get('fifty_two_week_high')
        div_yield = stock_data.get('dividend_yield')
        if low_52 and high_52:
            metrics_line3 = f"52-Week Range: {curr_sym}{low_52:.2f} - {curr_sym}{high_52:.2f}  |  Industry: {stock_data.get('industry', 'N/A')}"
            if div_yield:
                metrics_line3 += f"  |  Dividend Yield: {div_yield*100:.2f}%"
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(effective_width, 6, sanitize_text(metrics_line3))
        pdf.ln(5)
    else:
        # Private company indicator
        pdf.set_font("Arial", "I", 11)
        pdf.cell(effective_width, 8, "Private Company - No public stock data available", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)

    # Executive Summary
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(0, 51, 102)  # Dark blue
    pdf.cell(effective_width, 10, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)  # Reset to black
    pdf.set_font("Arial", "", 11)
    pdf.set_x(pdf.l_margin)
    executive_summary = swot_data.get('executive_summary', swot_data.get('summary', 'No summary available.'))
    pdf.multi_cell(effective_width, 6, sanitize_text(executive_summary))
    pdf.ln(5)

    # Market Analysis
    market_analysis = swot_data.get('market_analysis', '')
    if market_analysis:
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(0, 51, 102)  # Dark blue
        pdf.set_x(pdf.l_margin)
        pdf.cell(effective_width, 10, "Market Analysis", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)  # Reset to black
        pdf.set_font("Arial", "", 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_width, 6, sanitize_text(market_analysis))
        pdf.ln(5)
    
    # Strengths (Green header)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(34, 139, 34)  # Forest green
    pdf.set_x(pdf.l_margin)
    pdf.cell(effective_width, 10, "Strengths", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 11)
    for strength in swot_data.get('strengths', []):
        pdf.set_x(pdf.l_margin)
        sanitized_strength = sanitize_text(f"- {strength}")
        if sanitized_strength.strip():
            pdf.multi_cell(effective_width, 6, sanitized_strength)
    pdf.ln(5)

    # Weaknesses (Red header)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(178, 34, 34)  # Firebrick red
    pdf.set_x(pdf.l_margin)
    pdf.cell(effective_width, 10, "Weaknesses", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 11)
    for weakness in swot_data.get('weaknesses', []):
        pdf.set_x(pdf.l_margin)
        sanitized_weakness = sanitize_text(f"- {weakness}")
        if sanitized_weakness.strip():
            pdf.multi_cell(effective_width, 6, sanitized_weakness)
    pdf.ln(5)

    # Opportunities (Blue header)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(30, 144, 255)  # Dodger blue
    pdf.set_x(pdf.l_margin)
    pdf.cell(effective_width, 10, "Opportunities", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 11)
    for opportunity in swot_data.get('opportunities', []):
        pdf.set_x(pdf.l_margin)
        sanitized_opportunity = sanitize_text(f"- {opportunity}")
        if sanitized_opportunity.strip():
            pdf.multi_cell(effective_width, 6, sanitized_opportunity)
    pdf.ln(5)

    # Threats (Orange header)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(255, 140, 0)  # Dark orange
    pdf.set_x(pdf.l_margin)
    pdf.cell(effective_width, 10, "Threats", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
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
        pdf.set_text_color(0, 51, 102)  # Dark blue
        pdf.set_x(pdf.l_margin)
        pdf.cell(effective_width, 10, "Strategic Recommendations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
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
        pdf.set_text_color(0, 51, 102)  # Dark blue
        pdf.set_x(pdf.l_margin)
        pdf.cell(effective_width, 10, "Investment Considerations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "", 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(effective_width, 6, sanitize_text(investment_considerations))

    filename = f"{company_name}_Memo.pdf"
    pdf.output(filename)
    return filename


# The Sidebar
st.sidebar.header("💰 Scott's Company Analysis")
company_name = st.sidebar.text_input('Company Name', placeholder='Enter company name...')
generate_button = st.sidebar.button('Generate Memo', type='primary')


# The Main Area (Logic)
if generate_button:
    if not company_name:
        st.error('Please enter a company name')
    else:
        # Show progress with status spinner
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # Step 1: Check if company is publicly traded
            status_text.text('Checking if company is publicly traded...')
            progress_bar.progress(10)
            ticker = get_ticker_symbol(company_name)

            # Step 2: Fetch stock data if public
            stock_data = None
            if ticker:
                status_text.text(f'Fetching stock data for {ticker}...')
                progress_bar.progress(20)
                stock_data = fetch_stock_data(ticker)

            # Step 3: Get company info
            status_text.text('Searching for company information...')
            progress_bar.progress(35)
            url, search_summary = get_company_info(company_name)

            if not url:
                st.error(f'Could not find website for {company_name}')
            else:
                # Step 4: Analyze website
                status_text.text('Scraping company website...')
                progress_bar.progress(55)
                website_content = analyze_website(url)

                # Step 5: Generate Analysis with stock context
                status_text.text('Analyzing data and generating company analysis...')
                progress_bar.progress(75)
                swot_data = generate_swot(company_name, search_summary, website_content, stock_data)

                progress_bar.progress(100)
                status_text.text('Analysis complete!')
                progress_bar.empty()
                status_text.empty()

                # Format company name with title case
                display_name = company_name.title()

                # Display company name as title (with exchange:ticker for public companies) in styled header
                if stock_data and stock_data.get('ticker'):
                    exchange = stock_data.get('exchange', '')
                    ticker_display = stock_data.get('ticker', '')
                    # Remove suffix from ticker for cleaner display (e.g., SHOP.TO -> SHOP)
                    ticker_clean = ticker_display.split('.')[0] if '.' in ticker_display else ticker_display
                    # Format as "Exchange: TICKER" (e.g., "TSX: SHOP")
                    ticker_info = f"{exchange}: {ticker_clean}" if exchange else ticker_clean
                    st.markdown(f"""
                    <div style="background-color: rgba(128, 128, 128, 0.1); padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid rgba(128, 128, 128, 0.2);">
                        <h1 style="margin: 0;">{display_name} <span style="font-weight: normal; font-size: 0.5em; opacity: 0.7;">({ticker_info})</span></h1>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background-color: rgba(128, 128, 128, 0.1); padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid rgba(128, 128, 128, 0.2);">
                        <h1 style="margin: 0;">{display_name}</h1>
                    </div>
                    """, unsafe_allow_html=True)

                # Display Stock Metrics (for public companies)
                if stock_data and stock_data.get('current_price'):
                    st.markdown("### Financial Metrics")
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        price = stock_data.get('current_price')
                        last_trade = stock_data.get('last_trade_time')
                        currency_symbol = stock_data.get('currency_symbol', '$')
                        price_label = f"{currency_symbol}{price:.2f}" if price else "N/A"
                        st.metric("Stock Price", price_label)
                        if last_trade:
                            st.caption(f"Last updated: {last_trade}")
                    with m2:
                        st.metric("Market Cap", format_market_cap(stock_data.get('market_cap')))
                    with m3:
                        yr = stock_data.get('year_return')
                        delta_color = "normal" if yr and yr >= 0 else "inverse"
                        st.metric("1-Year Return", f"{yr:.1f}%" if yr else "N/A",
                                  delta=f"{yr:.1f}%" if yr else None,
                                  delta_color=delta_color if yr else "off")
                    with m4:
                        pe = stock_data.get('pe_ratio')
                        st.metric("P/E Ratio", f"{pe:.1f}" if pe else "N/A")

                    # Expandable Market Details
                    with st.expander("More Market Details"):
                        d1, d2, d3 = st.columns(3)
                        with d1:
                            low = stock_data.get('fifty_two_week_low')
                            high = stock_data.get('fifty_two_week_high')
                            curr_sym = stock_data.get('currency_symbol', '$')
                            # Use HTML entity &#36; for $ to avoid LaTeX interpretation
                            curr_sym_html = curr_sym.replace('$', '&#36;')
                            if low and high:
                                st.markdown(f"<b>52-Week Range:</b> {curr_sym_html}{low:.2f} - {curr_sym_html}{high:.2f}", unsafe_allow_html=True)
                            else:
                                st.markdown("<b>52-Week Range:</b> N/A", unsafe_allow_html=True)
                            st.markdown(f"<b>Sector:</b> {stock_data.get('sector', 'N/A')}", unsafe_allow_html=True)
                            st.markdown(f"<b>Industry:</b> {stock_data.get('industry', 'N/A')}", unsafe_allow_html=True)
                        with d2:
                            div_yield = stock_data.get('dividend_yield')
                            st.markdown(f"<b>Dividend Yield:</b> {div_yield*100:.2f}%" if div_yield else "<b>Dividend Yield:</b> N/A", unsafe_allow_html=True)
                            beta = stock_data.get('beta')
                            st.markdown(f"<b>Beta:</b> {beta:.2f}" if beta else "<b>Beta:</b> N/A", unsafe_allow_html=True)
                            fwd_pe = stock_data.get('forward_pe')
                            st.markdown(f"<b>Forward P/E:</b> {fwd_pe:.1f}" if fwd_pe else "<b>Forward P/E:</b> N/A", unsafe_allow_html=True)
                        with d3:
                            emp = stock_data.get('employees')
                            st.markdown(f"<b>Employees:</b> {emp:,}" if emp else "<b>Employees:</b> N/A", unsafe_allow_html=True)
                            rev = stock_data.get('revenue')
                            st.markdown(f"<b>Revenue:</b> {format_market_cap(rev)}" if rev else "<b>Revenue:</b> N/A", unsafe_allow_html=True)
                            margin = stock_data.get('profit_margin')
                            st.markdown(f"<b>Profit Margin:</b> {margin*100:.1f}%" if margin else "<b>Profit Margin:</b> N/A", unsafe_allow_html=True)
                else:
                    # Private company indicator
                    st.info("**Private Company** - This company is not publicly traded. No stock data available.")

                st.markdown("---")

                # Styled Executive Summary with blue border
                executive_summary = swot_data.get('executive_summary', swot_data.get('summary', 'No summary available.'))
                st.markdown(f"""
                <div style="border-left: 5px solid #1E90FF; padding: 15px; background-color: rgba(30, 144, 255, 0.1); border-radius: 5px;">
                    <h4 style="margin-top: 0;">Executive Summary</h4>
                    <p>{executive_summary}</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("")

                # Display Market Analysis if available
                market_analysis = swot_data.get('market_analysis', '')
                if market_analysis:
                    st.markdown("### Market Analysis")
                    st.markdown(market_analysis)

                st.markdown("---")

                # Display the SWOT analysis in a 2x2 grid with colored backgrounds
                st.markdown("### SWOT Analysis")

                # Row 1: Strengths and Weaknesses
                row1_col1, row1_col2 = st.columns(2)

                with row1_col1:
                    st.markdown("""
                    <div style="background-color: rgba(40, 167, 69, 0.2); padding: 10px 15px; border-radius: 8px 8px 0 0;">
                        <span style="color: #28a745; font-weight: bold;">✅ Strengths</span>
                    </div>
                    """, unsafe_allow_html=True)
                    strengths = swot_data.get('strengths', [])
                    if strengths:
                        for strength in strengths:
                            st.markdown(f"• {strength}")
                    else:
                        st.markdown("*No strengths listed*")

                with row1_col2:
                    st.markdown("""
                    <div style="background-color: rgba(220, 53, 69, 0.2); padding: 10px 15px; border-radius: 8px 8px 0 0;">
                        <span style="color: #dc3545; font-weight: bold;">⚠️ Weaknesses</span>
                    </div>
                    """, unsafe_allow_html=True)
                    weaknesses = swot_data.get('weaknesses', [])
                    if weaknesses:
                        for weakness in weaknesses:
                            st.markdown(f"• {weakness}")
                    else:
                        st.markdown("*No weaknesses listed*")

                st.markdown("")

                # Row 2: Opportunities and Threats
                row2_col1, row2_col2 = st.columns(2)

                with row2_col1:
                    st.markdown("""
                    <div style="background-color: rgba(0, 123, 255, 0.2); padding: 10px 15px; border-radius: 8px 8px 0 0;">
                        <span style="color: #007bff; font-weight: bold;">🚀 Opportunities</span>
                    </div>
                    """, unsafe_allow_html=True)
                    opportunities = swot_data.get('opportunities', [])
                    if opportunities:
                        for opportunity in opportunities:
                            st.markdown(f"• {opportunity}")
                    else:
                        st.markdown("*No opportunities listed*")

                with row2_col2:
                    st.markdown("""
                    <div style="background-color: rgba(255, 193, 7, 0.2); padding: 10px 15px; border-radius: 8px 8px 0 0;">
                        <span style="color: #ffc107; font-weight: bold;">🛡️ Threats</span>
                    </div>
                    """, unsafe_allow_html=True)
                    threats = swot_data.get('threats', [])
                    if threats:
                        for threat in threats:
                            st.markdown(f"• {threat}")
                    else:
                        st.markdown("*No threats listed*")

                st.markdown("---")

                # Display Strategic Recommendations in expandable section
                strategic_recs = swot_data.get('strategic_recommendations', [])
                if strategic_recs:
                    with st.expander("Strategic Recommendations", expanded=True):
                        for rec in strategic_recs:
                            st.markdown(f"- {rec}")

                # Display Investment Considerations if available
                investment_considerations = swot_data.get('investment_considerations', '')
                if investment_considerations:
                    st.markdown("### Investment Considerations")
                    st.markdown(investment_considerations)
                    st.markdown("---")

                # Display Stock Price Chart (for public companies)
                if stock_data and stock_data.get('ticker'):
                    st.markdown("### Stock Price History (1 Year)")
                    try:
                        ticker_symbol = stock_data.get('ticker')
                        stock_chart = yf.Ticker(ticker_symbol)
                        hist_data = stock_chart.history(period="1y")

                        if not hist_data.empty:
                            # Use Streamlit's line chart with the Close price
                            chart_data = hist_data[['Close']].copy()
                            chart_data.columns = ['Price']
                            st.line_chart(chart_data, use_container_width=True)

                            # Show period stats
                            period_high = hist_data['Close'].max()
                            period_low = hist_data['Close'].min()
                            curr_sym = stock_data.get('currency_symbol', '$')
                            curr_sym_html = curr_sym.replace('$', '&#36;')
                            st.markdown(f"<small style='color: #666;'>52-week range: {curr_sym_html}{period_low:.2f} - {curr_sym_html}{period_high:.2f}</small>", unsafe_allow_html=True)
                        else:
                            st.info("Stock price history not available.")
                    except Exception as e:
                        st.warning(f"Could not load stock chart: {e}")
                    st.markdown("---")

                # Generate the PDF in the background
                with st.spinner('Generating PDF...'):
                    pdf_filename = save_pdf(company_name, swot_data, stock_data)

                    # Read the PDF file
                    with open(pdf_filename, 'rb') as pdf_file:
                        pdf_bytes = pdf_file.read()

                # Show a large 'Download PDF' button using st.download_button
                st.download_button(
                    label='Download Investment Memo PDF',
                    data=pdf_bytes,
                    file_name=pdf_filename,
                    mime='application/pdf',
                    use_container_width=True
                )

        except Exception as e:
            st.error(f'Error: {str(e)}')
            progress_bar.empty()
            status_text.empty()

else:
    # Initial state - show welcome message
    st.title("💰 Scott's Company Analysis")
    st.markdown("""
    ### Welcome to Scott's Company Analysis Memo Generator! 📊
    
    **Instructions:**
    1. Enter a company name in the sidebar
    2. Click "Generate Memo" to create a comprehensive company analysis
    3. Review the analysis and download the PDF memo
    
    Get started by entering a company name in the sidebar! 👈
    """)
