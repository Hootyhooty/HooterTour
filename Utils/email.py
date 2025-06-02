import os
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import jinja2
import html2text
from flask import current_app

# Load environment variables
load_dotenv()

# Configure Jinja2 environment for email templates
template_loader = jinja2.FileSystemLoader(searchpath="templates/email")
template_env = jinja2.Environment(loader=template_loader)

class Email:
    def __init__(self, user, url):
        self.to = user.email
        self.first_name = user.name.split(' ')[0] if user.name else "User"
        self.url = url
        self.from_email = os.getenv('EMAIL_FROM', 'Natours <no-reply@natours.com>')
        self.smtp_host = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('EMAIL_PORT', 587))
        self.smtp_user = os.getenv('EMAIL_USERNAME')
        self.smtp_pass = os.getenv('EMAIL_PASSWORD')

    def _new_transport(self):
        """
        Create an SMTP transport based on environment.
        """
        if os.getenv('FLASK_ENV') == 'production':
            # SendGrid configuration
            return smtplib.SMTP('smtp.sendgrid.net', 587)
        else:
            # Development configuration
            return smtplib.SMTP(self.smtp_host, self.smtp_port)

    def send(self, template, subject):
        """
        Send an email using the specified template and subject.
        """
        try:
            # 1) Render HTML based on a Jinja2 template
            template_obj = template_env.get_template(f"{template}.html")
            html = template_obj.render(
                first_name=self.first_name,
                url=self.url,
                subject=subject
            )

            # 2) Define email options
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = self.to
            msg['Subject'] = subject

            # Attach HTML and plain text versions
            msg.attach(MIMEText(html, 'html'))
            msg.attach(MIMEText(html2text.html2text(html), 'plain'))

            # 3) Create a transport and send email
            with self._new_transport() as server:
                server.connect(self.smtp_host, self.smtp_port)  # Explicitly connect
                if os.getenv('FLASK_ENV') != 'production':
                    server.starttls()  # Enable TLS for development
                    if self.smtp_user and self.smtp_pass:
                        server.login(self.smtp_user, self.smtp_pass)
                else:
                    # SendGrid requires login even in production
                    server.starttls()
                    server.login(os.getenv('EMAIL_USERNAME'), os.getenv('EMAIL_PASSWORD'))
                server.send_message(msg)
        except Exception as e:
            raise Exception(f"Email sending failed: {str(e)}")

    def send_welcome(self):
        """
        Send a welcome email to the user.
        """
        self.send('welcome', 'Welcome to the Natours Family!')

    def send_password_reset(self):
        """
        Send a password reset email to the user.
        """
        self.send('passwordReset', 'Your password reset token (valid for only 10 minutes)')