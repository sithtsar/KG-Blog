#!/bin/bash

set -e

echo "Creating virtual environment..."
uv venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Setting up dependencies..."
uv sync

echo "Starting Neo4j..."
docker-compose up -d

echo "Generating BAML client..."
baml-cli generate

echo "Starting the app..."
uv run python app.py