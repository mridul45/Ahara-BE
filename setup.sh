#!/bin/bash

# Define virtual environment name
VENV_NAME="env"

# 1. Set up virtual environment if not exists
if [ ! -d "$VENV_NAME" ]; then
    echo "Creating virtual environment '$VENV_NAME'..."
    python3 -m venv $VENV_NAME
else
    echo "Virtual environment '$VENV_NAME' already exists."
fi

# Activate the virtual environment
source $VENV_NAME/bin/activate

# 2. Install requirements
echo "Installing requirements..."
pip install --upgrade pip
if [ -f "requirements/base.txt" ]; then
    pip install -r requirements/base.txt
fi
if [ -f "requirements/local.txt" ]; then
    pip install -r requirements/local.txt
fi
if [ -f "requirements/production.txt" ]; then
    pip install -r requirements/production.txt
fi

# 3. Run tests
echo "Running tests..."
# We use python -m pytest to ensure we use the one installed in the venv
python -m pytest

# Check if tests passed
if [ $? -ne 0 ]; then
    echo "Tests failed! Stopping setup."
    exit 1
fi

# 4. Run server
echo "Starting Django development server..."
python manage.py runserver
