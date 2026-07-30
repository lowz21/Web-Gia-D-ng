"""
Vercel Serverless Function Entry Point
This file serves as the entry point for Vercel deployment of the Flask application.
"""
import sys
import os

# Add the parent directory to the path so we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# Create the Flask app instance
app = create_app()

# Vercel requires the app to be exposed as a WSGI application
# The app instance is already WSGI-compatible
app = app

# For Vercel, we need to handle the ASGI/WSGI interface
# Flask apps are WSGI by default, which works with Vercel's Python runtime
