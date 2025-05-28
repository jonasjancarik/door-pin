#!/bin/bash

# Setup dummy RPi package for development environments
# This script creates a mock RPi.GPIO module to avoid import errors
# when developing on machines that don't support the actual RPi.GPIO library

echo "Setting up dummy RPi package for development..."

# Create RPi directory
mkdir -p RPi

# Create __init__.py
touch RPi/__init__.py

# Create GPIO.py with dummy functions
cat > RPi/GPIO.py << 'EOF'
def setmode(a):
    print(a)


def setup(a, b):
    print(a)


def output(a, b):
    print(a)


def cleanup():
    print("a")


def setwarnings(flag):
    print("False")


def LOW():
    print("LOW")


def HIGH():
    print("HIGH")


def BCM():
    print("BCM")


def OUT():
    print("OUT")
EOF

echo "Dummy RPi package created successfully!"
echo "You can now run the door-pin application in development mode." 