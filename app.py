# -*- coding: utf-8 -*-
"""
Koyeb Health Check Server
Bu dosya Koyeb'in health check'ini geçmek için gerekli.
Bot ayrı bir process olarak çalışır.
"""

from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def health():
    return '✅ Münazara Bot Aktif!'

@app.route('/health')
def health_check():
    return 'OK', 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
