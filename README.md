# Project Setup Guide

## 1. Install Python Libraries

Make sure you have Python 3.11+ installed. To install all required libraries, run:

```
pip install -r requirements.txt
```

## 2. Set Up Environment Variables

1. Copy the `env_template` file to `.env`:
   
   - On Windows:
     - In File Explorer: Copy and rename `env_template` to `.env` in the same folder.
     - Or in terminal:
       ```
       copy env_template .env
       ```
   - On Linux/macOS:
       ```
       cp env_template .env
       ```

2. Open `.env` and fill in the required values for each variable.


## 3. Create and Activate Virtual Environment (Recommended)

If you do not have a virtual environment yet, create one:

- On Windows (cmd or PowerShell):
  ```
  python -m venv test_env
  ```
- On Linux/macOS:
  ```
  python3 -m venv test_env
  ```

Then activate the virtual environment:

- On Windows (cmd):
  ```
  test_env\Scripts\activate.bat
  ```
- On Windows (PowerShell):
  ```
  .\test_env\Scripts\Activate.ps1
  ```
- On Linux/macOS:
  ```
  source test_env/bin/activate
  ```

## 4. Run Your Project

You are now ready to run your Python scripts or Jupyter notebooks!
