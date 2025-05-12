from flask import Flask, Response, render_template, request, send_file
from pdf_parser import PdfParser, TableExtractor
import pandas as pd
from io import BytesIO
import os
import queue
from dotenv import load_dotenv

from utils import log_queue

_ = load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

tables_cache = []

@app.route('/', methods=['GET', 'POST'])
def index():
    global tables_cache
    tables_cache = []
    logs = None

    if request.method == 'POST':
        uploaded_file = request.files['pdf']
        if uploaded_file.filename != '':
            open("app.log", "w").close()
            
            file_bytes = uploaded_file.read()
            parser = PdfParser(file_bytes=file_bytes)

            pages = parser.raw_text.split("\n------------\n")
            extractor = TableExtractor()
            tables_cache = extractor.extract_from_pages(pages_text=pages)

            try:
                with open("app.log", "r") as f:
                    lines = f.readlines()
                    logs = ''.join(lines[-100:])  # Last 100 lines
            except Exception as e:
                logs = f"⚠️ Failed to read log file: {e}"

            return render_template(
                'index.html',
                tables=[
                    (i, df.to_html(classes="table table-bordered", index=False))
                    for i, df in enumerate(tables_cache)
                ],
                logs=logs
            )

    return render_template('index.html', tables=[
        (i, df.to_html(classes="table table-bordered", index=False))
        for i, df in enumerate(tables_cache)
    ])

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            try:
                message = log_queue.get(timeout=10)
                yield f"data: {message}\n\n"
            except queue.Empty:
                continue
    return Response(event_stream(), content_type='text/event-stream')

@app.route('/download/<int:table_id>')
def download(table_id):
    df = tables_cache[table_id]
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f'table_{table_id}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=80)
