from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from db import db
import sys

'''
def signup():
    if request.method == 'POST':
        try:
            users_collection = db.get_users_collection()
            if not users_collection:
                flash('Database connection failed. Please try again later.', 'error')
                return render_template('signup.html'), 500

            # Get form data
            full_name = request.form['full-name']
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['confirm-password']

            # Validate form data
            if not full_name or not email or not password or not confirm_password:
                flash('All fields are required.', 'error')
                return render_template('signup.html'), 400

            if password != confirm_password:
                flash('Passwords do not match. Please try again.', 'error')
                return render_template('signup.html'), 400

            # Check if email already exists
            if users_collection.find_one({'email': email}):
                flash('Email already registered. Please use a different email.', 'error')
                return render_template('signup.html'), 409

            # Hash the password for security
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

            # Store user data in MongoDB
            user = {
                'full_name': full_name,
                'email': email,
                'password': hashed_password,
                'created_at': datetime.now()
            }
            users_collection.insert_one(user)

            # Flash success message and redirect
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error during registration: {e}', 'error')
            return render_template('signup.html'), 500

    # Render the signup page for GET requests
    return render_template('signup.html')
'''

def signup():
    if request.method == 'POST':
        try:

            # Get form data
            full_name = request.form.get('full-name')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm-password')
            print(f"Form data: full_name={full_name}, email={email}, password={password}, confirm_password={confirm_password}", file=sys.stderr)

            # Validate form data
            if not all([full_name, email, password, confirm_password]):
                flash('All fields are required.', 'error')
                print("Validation failed: Missing fields", file=sys.stderr)
                return render_template('signup.html'), 400

            if password != confirm_password:
                flash('Passwords do not match. Please try again.', 'error')
                print("Validation failed: Passwords do not match", file=sys.stderr)
                return render_template('signup.html'), 400

            # Check if email already exists
            existing_user = db.users_collection.find_one({'email': email})
            print(f"Existing user check result: {existing_user}", file=sys.stderr)
            if existing_user is not None:
                flash('Email already registered. Please use a different email.', 'error')
                print(f"Email {email} already exists", file=sys.stderr)
                return render_template('signup.html'), 409

            # Hash the password
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            print(f"Hashed password generated: {hashed_password}", file=sys.stderr)

            # Store user data
            user = {
                'full_name': full_name,
                'email': email,
                'password': hashed_password,
                'created_at': datetime.now()
            }
            try:
                result = db.users_collection.insert_one(user)
                if result.inserted_id:
                    print(f"User inserted successfully with ID: {result.inserted_id}", file=sys.stderr)
                else:
                    print("Insert operation returned no ID", file=sys.stderr)
                    raise Exception("Insert operation failed")
            except Exception as e:
                print(f"Insert error: {e}", file=sys.stderr)
                flash(f'Failed to save user: {e}', 'error')
                return render_template('signup.html'), 500

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Exception in signup: {e}", file=sys.stderr)
            flash(f'Error during registration: {e}', 'error')
            return render_template('signup.html'), 500

    return render_template('signup.html')

def login():
    if request.method == 'POST':
        try:
            # Retrieve users_collection with try-except
            try:
                users_collection = db.get_users_collection()
                print(f"users_collection retrieved: {users_collection}", file=sys.stderr)
            except Exception as e:
                flash('Failed to connect to database. Ensure MongoDB is running.', 'error')
                print(f"Exception getting users_collection: {e}", file=sys.stderr)
                return render_template('login.html'), 500

            # Test collection usability
            try:
                users_collection.find_one()  # Lightweight test
            except Exception as e:
                flash('Database operation failed. Ensure MongoDB is running.', 'error')
                print(f"Database operation error: {e}", file=sys.stderr)
                return render_template('login.html'), 500

            email = request.form.get('email')
            password = request.form.get('password')

            user = users_collection.find_one({'email': email})
            if user and check_password_hash(user['password'], password):
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            flash('Invalid email or password.', 'error')
            return render_template('login.html'), 401
        except Exception as e:
            print(f"Exception in login: {e}", file=sys.stderr)
            flash(f'Error during login: {e}', 'error')
            return render_template('login.html'), 500

    return render_template('login.html')
'''
def signup():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            if not email or '@' not in email:
                flash('Please enter a valid email address.', 'error')
                return render_template('auth.html'), 400

            users_collection = db.get_users_collection()
            if users_collection is None:
                flash('Database connection failed. Please try again later.', 'error')
                print("Users collection is None", file=sys.stderr)
                return render_template('auth.html'), 500

            # Check if email already exists
            existing_user = users_collection.find_one({'email': email})
            if existing_user is not None:  # Explicitly check for document
                flash('Email already registered. Please use a different email.', 'error')
                print(f"Email {email} already exists", file=sys.stderr)
                return render_template('login.html'), 409

            session['temp_email'] = email
            print(f"Session set: temp_email={email}", file=sys.stderr)
            return redirect(url_for('name'))
        except Exception as e:
            print(f"Exception in auth: {e}", file=sys.stderr)
            print('f')
            flash(f'Error processing email: {e}', 'error')
            return render_template('auth.html'), 500

    return render_template('auth.html')

def name():
    if request.method == 'POST':
        try:
            first_name = request.form.get('first-name')
            last_name = request.form.get('last-name')
            promo_updates = request.form.get('promo-updates') == 'on'

            if not first_name or not last_name:
                flash('Please enter both first and last name.', 'error')
                return render_template('name.html'), 400

            session['temp_first_name'] = first_name
            session['temp_last_name'] = last_name
            session['temp_promo_updates'] = promo_updates
            return redirect(url_for('password'))
        except Exception as e:
            print(f"Exception in name: {e}", file=sys.stderr)
            flash(f'Error during name step: {e}', 'error')
            return render_template('name.html'), 500

    return render_template('name.html')


def password():
    if request.method == 'POST':
        try:
            # Get all form and session data
            email = session.get('temp_email')
            first_name = session.get('temp_first_name')
            last_name = session.get('temp_last_name')
            promo_updates = session.get('temp_promo_updates', False)
            password = request.form.get('password')
            confirm_password = request.form.get('confirm-password')

            print(f"Form and session data: email={email}, first_name={first_name}, last_name={last_name}, promo_updates={promo_updates}, password={password}, confirm_password={confirm_password}", file=sys.stderr)

            # Validate all data together, mimicking the old signup
            if not all([email, first_name, last_name, password, confirm_password]):
                flash('All fields are required.', 'error')
                print("Validation failed: Missing fields", file=sys.stderr)
                return render_template('password.html'), 400

            if password != confirm_password:
                flash('Passwords do not match. Please try again.', 'error')
                print("Validation failed: Passwords do not match", file=sys.stderr)
                return render_template('password.html'), 400

            users_collection = db.get_users_collection()
            if users_collection is None:
                flash('Database connection failed. Please try again later.', 'error')
                print("Database collection not available", file=sys.stderr)
                return render_template('password.html'), 500

            # Hash the password
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            print(f"Hashed password generated: {hashed_password}", file=sys.stderr)

            # Save user to MongoDB
            user = {
                'full_name': f"{first_name} {last_name}",
                'email': email,
                'password': hashed_password,
                'created_at': datetime.now(),
                'promo_updates': promo_updates
            }
            result = users_collection.insert_one(user)
            if result.inserted_id:
                print(f"User inserted successfully with ID: {result.inserted_id}", file=sys.stderr)
            else:
                print("Insert operation returned no ID", file=sys.stderr)
                raise Exception("Insert operation failed")

            # Clear session data
            session.pop('temp_email', None)
            session.pop('temp_first_name', None)
            session.pop('temp_last_name', None)
            session.pop('temp_promo_updates', None)
            print("Session cleared successfully", file=sys.stderr)

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Exception in password: {e}", file=sys.stderr)
            flash(f'Error during password step: {e}', 'error')
            return render_template('password.html'), 500

    return render_template('password.html')

def password():
    if request.method == 'POST':
        try:
            password = request.form.get('password')
            confirm_password = request.form.get('confirm-password')

            print(f"Form data received: password={password}, confirm_password={confirm_password}", file=sys.stderr)
            if not password or not confirm_password or password != confirm_password:
                flash('Passwords do not match or are empty. Please try again.', 'error')
                print("Validation failed: Passwords do not match or are empty", file=sys.stderr)
                return render_template('password.html'), 400

            # Retrieve session data with debug
            email = session.get('temp_email')
            first_name = session.get('temp_first_name')
            last_name = session.get('temp_last_name')
            promo_updates = session.get('temp_promo_updates', False)
            print(f"Session data: email={email}, first_name={first_name}, last_name={last_name}, promo_updates={promo_updates}", file=sys.stderr)

            if not all([email, first_name, last_name]):
                flash('Missing session data. Please start over.', 'error')
                print("Validation failed: Missing session data", file=sys.stderr)
                return redirect(url_for('signup')), 400

            # Hash the password
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            print(f"Hashed password generated: {hashed_password}", file=sys.stderr)

            # Save user to MongoDB
            users_collection = db.get_users_collection()
            user = {
                'full_name': f"{first_name} {last_name}",
                'email': email,
                'password': hashed_password,
                'created_at': datetime.now(),
                'promo_updates': promo_updates
            }
            result = users_collection.insert_one(user)
            if result.inserted_id:
                print(f"User inserted successfully with ID: {result.inserted_id}", file=sys.stderr)
            else:
                print("Insert operation failed", file=sys.stderr)
                raise Exception("Failed to insert user into database")

            # Clear session data
            session.pop('temp_email', None)
            session.pop('temp_first_name', None)
            session.pop('temp_last_name', None)
            session.pop('temp_promo_updates', None)
            print("Session cleared successfully", file=sys.stderr)

            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Exception in password: {e}", file=sys.stderr)
            flash(f'Error during password step: {e}', 'error')
            return render_template('password.html'), 500

    return render_template('password.html')'''