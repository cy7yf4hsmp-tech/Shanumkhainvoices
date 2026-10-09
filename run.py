"""Start the app:  python run.py   then open http://127.0.0.1:8765"""
import os

from invoicer import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8765))  # not 5000: macOS AirPlay Receiver uses that port
    if os.environ.get("FLASK_DEBUG") == "1":
        app.run(host=host, port=port, debug=True)
    else:
        from waitress import serve
        print(f"Shanumkha Invoices is running at http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}")
        serve(app, host=host, port=port, threads=8)
