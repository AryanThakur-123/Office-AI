# Intelligent Analytics Query Engine

## Approach
This project is an end-to-end intelligent analytics query engine that takes natural language queries and maps them to executable SQL logic against an in-memory SQLite database. It leverages Google's Gemini GenAI to understand user intent, map business logic defined in `data_dictionary.json`, and output structured JSON results.

## Architecture
1. **Data Ingestion Layer**: 
    - `sales_data.csv` and `targets.csv` are dynamically loaded into an in-memory SQLite database using `pandas`. This ensures we have a fast, safe, and easily queryable execution environment.
2. **GenAI Orchestration**:
    - The LLM (`gemini-1.5-pro`) is provided with a strict prompt combining the user's natural language query, the database schema, and the business logic mappings from `data_dictionary.json`.
    - It is constrained to return a structured JSON response containing the SQL query, explanation, understanding, and a confidence score.
3. **Execution Engine**:
    - The generated SQL query is executed directly against the in-memory SQLite database.
    - Errors in generation or execution are caught and returned within the JSON payload.
4. **Output Formatter**:
    - Generates the final required JSON schema including the query, generated logic, execution result, confidence score, and explanation.

## Tradeoffs
1. **SQL vs. Pandas**: The engine uses SQL (SQLite) rather than Python (Pandas) for logic execution. Executing dynamically generated Python code can be extremely unsafe and prone to runtime errors. SQL is sandboxed, robust, and much better at complex aggregations, window functions, and joins.
2. **In-Memory SQLite vs. Persistent DB**: We load CSVs into an in-memory SQLite database on every run. While this is fast for small datasets, it won't scale to gigabytes of data. For production, the database would persist, and the engine would simply query it.
3. **LLM Hallucinations**: Prompt engineering relies on the LLM adhering strictly to JSON format. Fallbacks (like stripping Markdown backticks) are implemented, but structured output configuration (like Gemini's `response_mime_type="application/json"`) drastically reduces parse errors.

## How to Run

1. Ensure you have Python 3.9+ installed.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your Google Gemini API key as an environment variable:
   - On Windows: `set GEMINI_API_KEY=your_api_key_here`
   - On Linux/Mac: `export GEMINI_API_KEY=your_api_key_here`
4. Run the engine:
   ```bash
   python engine.py
   ```
5. The processed results will be saved in `output_results.json` in the same directory.
