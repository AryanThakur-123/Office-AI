import http.server
import socketserver
import os
import json
from engine import setup_database, load_data_dictionary, process_query

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Initialize engine dependencies globally for the server
print("Initializing database and loading data dictionary...")
conn = setup_database()
data_dictionary = load_data_dictionary()
print("Engine initialized successfully.")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
        
    def end_headers(self):
        # Disable caching to ensure the dashboard always loads the latest JSON
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_POST(self):
        if self.path == '/api/query':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                query_text = data.get('query', '')
                
                query_obj = {"query": query_text}
                result = process_query(conn, data_dictionary, query_obj)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_resp = {"error": str(e)}
                self.wfile.write(json.dumps(error_resp).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Dashboard Server is running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        conn.close()
