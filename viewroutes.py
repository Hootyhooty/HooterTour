from flask import render_template, flash

def home():
    try:
        return render_template('index.html')
    except Exception as e:
        flash(f'Error rendering home page: {e}', 'error')
        return render_template('error.html'), 500

def destination():
    try:
        return render_template('destination.html')
    except Exception as e:
        flash(f'Error rendering destination page: {e}', 'error')
        return render_template('error.html'), 500

def about():
    try:
        return render_template('about.html')
    except Exception as e:
        flash(f'Error rendering about page: {e}', 'error')
        return render_template('error.html'), 500

def contact():
    try:
        return render_template('contact.html')
    except Exception as e:
        flash(f'Error rendering contact page: {e}', 'error')
        return render_template('error.html'), 500

def service():
    try:
        return render_template('service.html')
    except Exception as e:
        flash(f'Error rendering service page: {e}', 'error')
        return render_template('error.html'), 500

def error():
    try:
        return render_template('error.html')
    except Exception as e:
        flash(f'Error rendering 404 page: {e}', 'error')
        return render_template('error.html'), 500

def package():
    try:
        return render_template('package.html')
    except Exception as e:
        flash(f'Error rendering package page: {e}', 'error')
        return render_template('error.html'), 500

def booking():
    try:
        return render_template('booking.html')
    except Exception as e:
        flash(f'Error rendering booking page: {e}', 'error')
        return render_template('error.html'), 500

def team():
    try:
        return render_template('team.html')
    except Exception as e:
        flash(f'Error rendering team page: {e}', 'error')
        return render_template('error.html'), 500

def testimonial():
    try:
        return render_template('testimonial.html')
    except Exception as e:
        flash(f'Error rendering testimonial page: {e}', 'error')
        return render_template('error.html'), 500

