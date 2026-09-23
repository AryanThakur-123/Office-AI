import os
import json
import sqlite3
import pandas as pd
import time
from google import genai
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

load_dotenv()

# Use environment variable for API Key, otherwise fallback to user input logic or a dummy
api_key = os.getenv("GEMINI_API_KEY", "")
if api_key:
    client = genai.Client(api_key=api_key)
else:
    client = None

def setup_database():
    """Loads CSVs into an in-memory SQLite database and returns the connection."""
    conn = sqlite3.connect(':memory:')
    try:
        sales_data = pd.read_csv('sales_data.csv')
        sales_data.to_sql('sales_data', conn, index=False, if_exists='replace')
        
        targets_data = pd.read_csv('targets.csv')
        targets_data.to_sql('targets', conn, index=False, if_exists='replace')
    except Exception as e:
        print(f"Error loading CSVs into database: {e}")
    return conn

def load_data_dictionary():
    """Loads the data dictionary from JSON."""
    try:
        with open('data_dictionary.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data dictionary: {e}")
        return {}

def build_prompt(query: str, data_dictionary: dict) -> str:
    """Builds the prompt for the LLM."""
    schema_str = json.dumps(data_dictionary, indent=2)
    prompt = f"""
You are an intelligent data analytics query engine. 
Given a natural language query and a data dictionary mapping business logic to data fields, 
your task is to generate a valid SQLite query to answer the question.

### Database Schema Details:
There are two tables:
1. `sales_data`
   - Columns: order_id, order_date (YYYY-MM-DD), region, country, city, customer_id, customer_segment, product_category, product_subcategory, product_name, quantity, unit_price, discount, shipping_cost, profit

2. `targets`
   - Columns: region, month (YYYY-MM), target_revenue

### Data Dictionary / Business Logic:
{schema_str}

### Rules
1. Only use the tables and columns provided. Use the provided business logic for calculations. For example, revenue is calculated as `SUM(quantity * unit_price * (1 - discount))`.
2. Return your answer as a JSON object with the following keys exactly:
   - "sql_query": The SQLite executable query. Use standard SQLite functions. To extract month in YYYY-MM format from `order_date`, use `strftime('%Y-%m', order_date)`.
   - "confidence_score": A float between 0.0 and 1.0 indicating how confident you are.
   - "understanding": A string explaining what you understood the user's query to mean and how you mapped it to business logic.
   - "explanation": A string explaining the logic of the generated SQL query.
3. Your output MUST be ONLY valid JSON, with NO markdown formatting, NO markdown code blocks (e.g. ```json), and NO extra text before or after.
4. Handle complex queries: 
   - For 'Top N within groups', use window functions like RANK() OVER (PARTITION BY ... ORDER BY ...).
   - For 'Sales contribution %', calculate the percentage out of the total.
   - For 'Comparisons with targets', join `sales_data` and `targets` on `region` AND month. Match `strftime('%Y-%m', sales_data.order_date)` with `targets.month`.
   - 'YoY growth' may require self joins or window functions like LAG() OVER (...). If no previous year data exists, compute it generally.
   - Nested logic should be handled by CTEs (WITH clause).

### User Query
{query}
"""
    return prompt

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(5))
def call_llm(client, prompt):
    return client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config={
            'temperature': 0.0,
            'response_mime_type': 'application/json',
        }
    )

def generate_logic(query: str, data_dictionary: dict) -> dict:
    """Calls the LLM to generate the SQL query and metadata."""
    if not client:
        return {
            "sql_query": "SELECT 'Missing GEMINI_API_KEY' as error",
            "confidence_score": 0.0,
            "understanding": "Cannot process without API key.",
            "explanation": "No API key provided."
        }
    
    prompt = build_prompt(query, data_dictionary)
    
    try:
        response = call_llm(client, prompt)
        
        # Extract the JSON block
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].strip()
            
        llm_output = json.loads(text)
    except Exception as e:
        print(f"LLM API Error: {e}")
        llm_output = {
            "sql_query": "SELECT 'LLM Error' as error",
            "confidence_score": 0.0,
            "understanding": "Failed to process query due to LLM error.",
            "explanation": str(e)
        }

    return llm_output

def execute_sql(conn: sqlite3.Connection, sql: str) -> str:
    """Executes the SQL query and returns the results as a JSON string."""
    if not sql:
        return "No SQL query generated."
    if "error" in sql.lower() and "missing" in sql.lower():
        return "[]"
    
    try:
        df = pd.read_sql_query(sql, conn)
        return df.to_json(orient="records")
    except Exception as e:
        return f"Execution Error: {str(e)}"

def process_query(conn: sqlite3.Connection, data_dictionary: dict, query_obj: dict) -> dict:
    """Processes a single query end-to-end."""
    nl_query = query_obj.get("query", "")
    
    # 1. Generate logic
    llm_output = generate_logic(nl_query, data_dictionary)
    
    # 2. Execute logic
    result = execute_sql(conn, llm_output.get("sql_query", ""))
    
    # 3. Format output based on requirements
    final_output = {
        "query": nl_query,
        "generated_logic": llm_output.get("sql_query", ""),
        "result": result,
        "confidence_score": llm_output.get("confidence_score", 0.0),
        "explanation": f"Understood: {llm_output.get('understanding', '')}. Logic: {llm_output.get('explanation', '')}"
    }
    return final_output

def main():
    conn = setup_database()
    data_dictionary = load_data_dictionary()
    
    try:
        with open('nl_queries.json', 'r') as f:
            queries = json.load(f)
    except Exception as e:
        print(f"Error loading queries: {e}")
        queries = []
    
    results = []
    for q_obj in queries:
        print(f"Processing query: {q_obj.get('query')}", flush=True)
        result_json = process_query(conn, data_dictionary, q_obj)
        results.append(result_json)
        
        # Save incrementally
        with open('output_results.json', 'w') as f:
            json.dump(results, f, indent=4)
            
    
    print("\nAll queries processed. Results saved to output_results.json", flush=True)
    conn.close()

if __name__ == "__main__":
    main()
