# Nile University Admin Portal - Setup Guide

This folder contains the full Nile Admin Portal. To run it correctly, follow these steps:

## Step 1: Extract the folder
Make sure you have unzipped this entire folder. **Do not run the files directly from inside a ZIP.**

## Step 2: Open Terminal / Command Prompt
You must change your directory to this specific folder before running any commands.

### On Mac/Linux:
```bash
cd "/path/to/extracted/Send"
```

### On Windows:
```bash
cd "C:\path\to\extracted\Send"
```

## Step 3: Install Dependencies
Run the following command to install the required libraries (Flask, Supabase, etc.):
```bash
pip install -r requirements.txt
```
*(If you have both Python 2 and 3, use `pip3` instead of `pip`)*

## Step 4: Run the App
Launch the Flask server:
```bash
python app.py
```
*(If you have both Python 2 and 3, use `python3` instead of `python`)*

## Step 5: Access the Portal
Open your web browser and go to:
**http://127.0.0.1:5001**

---

### Critical Notes:
1. **The .env file**: This folder contains a hidden `.env` file with the database credentials. If you are copying these files manually, ensure you include the `.env` file.
2. **Database**: The app connects to the live Supabase project. No local database setup is required.
3. **Seeded Data**: Use the `seed_50_students.sql` in the Supabase SQL editor if you need to regenerate the 50 students.
