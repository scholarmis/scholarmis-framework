import os
import logging
from django.conf import settings # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from django.core.validators import validate_email # type: ignore
from django.core.mail import EmailMessage # type: ignore
from django.template.loader import render_to_string # type: ignore
from premailer import transform  # type: ignore


logger = logging.getLogger(__name__)


class BaseEmail:
    template = None  # Subclass must define (HTML file, text file, or plain text)
    subject = None  # Subclass must define (plain text or path to .txt file)
    attachments = []  # List of file paths or File objects to attach

    def send(self, recipients, context: dict = None):
        """
        Sends an email using the provided template, subject, and optional attachments.

        Args:
            recipients (str, list): Single email address, list of email addresses, single user instance, or list of user instances.
            context (dict): Context for rendering the templates.
        """
        if not self.template or not self.subject:
            raise ValueError("Both 'template' and 'subject' must be defined in the subclass.")
        

        # Render the subject
        subject = self._get_subject(context)

        # Render and process the HTML or plain text message
        content = self._get_content(context)
        body = transform(content)

        # Prepare email message
        from_email = self.get_from_email()
        recipients = self._resolve_recipients(recipients)
        email_message = EmailMessage(
            subject=subject, 
            body=body, 
            from_email=from_email, 
            to=recipients
        )
        email_message.content_subtype = "html"

        # Add file attachments
        self.add_attachments(email_message)

        try:
            # Send the email
            email_message.send()
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)} ")

    def _get_subject(self, context):
        """
        Retrieves the subject text. If it's a file, render it with context.
        """
        if self.subject.endswith(".txt"):
            subject = render_to_string(self.subject, context)
        else:
            subject = self.subject
        return " ".join(subject.splitlines()).strip()  # Clean up whitespace

    def _get_content(self, context):
        """
        Retrieves the message template. Supports HTML, text files, and plain text.
        """
        if self.template.endswith(".html") or self.template.endswith(".txt"):
            # If the template is an HTML or text file, render it with context
            template = render_to_string(self.template, context)
        else:
            # If it's plain text, just use the provided template
            template = self.template
        return template

    def _resolve_recipients(self, recipients):
        """
        Extracts and validates emails from the recipients input.
        Recipients can be:
        - A single email string
        - A list of valid email strings
        - A single user instance with an 'email' attribute
        - A list of user instances with 'email' attributes
        """
        if isinstance(recipients, str):
            if is_valid_email(recipients):
                return [recipients]
            else:
                raise ValueError(f"Invalid email address: {recipients}")

        if isinstance(recipients, list):
            if all(isinstance(r, str) and is_valid_email(r) for r in recipients):  # List of valid emails
                return recipients
            elif all(hasattr(r, 'email') and is_valid_email(r.email) for r in recipients):  # List of user instances
                return [r.email for r in recipients]
            else:
                raise ValueError("Recipients list must contain only valid email strings or user instances with a valid 'email' attribute.")

        if hasattr(recipients, 'email') and is_valid_email(recipients.email):  # Single user instance
            return [recipients.email]

        raise ValueError("Recipients must be a valid email string, list of valid emails, or user instances with an 'email' attribute.")

    def get_from_email(self):
        """
        Returns the default 'from' email address.
        Override this method if needed.
        """
        return getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")

    def add_attachments(self, email_message):
        """
        Adds attachments to the email if any are defined. Supports file paths and uploaded files.
        
        Args:
            email_message (EmailMessage): The email message to attach files to.
        """
        if not self.attachments:
            return
        
        for attachment in self.attachments:
            if isinstance(attachment, str):  # Check if it's a file path
                if os.path.exists(attachment):
                    email_message.attach_file(attachment)
                else:
                    raise FileNotFoundError(f"Attachment file not found: {attachment}")
            elif hasattr(attachment, 'read'):  # Check if it's a file-like object (e.g. uploaded file)
                # Attach the file using the filename attribute from the uploaded file
                email_message.attach(attachment.name, attachment.read(), attachment.content_type)
            else:
                raise ValueError("Attachment must be either a file path or a file-like object.")

    def set_template(self, template):
        """
        Sets the message template for the email. This could be a plain text, HTML file, or HTML template.

        Args:
            template (str): Can be a path to an HTML file or text file, or plain text template.
        """
        self.template = template

    def set_subject(self, subject):
        """
        Sets the subject text for the email. This can be a plain text or the path to a subject text file.

        Args:
            subject (str): The subject text or path to a .txt file containing the subject.
        """
        self.subject = subject

    def set_attachments(self, attachments):
        """
        Sets the attachments for the email. Accepts a list of file paths or File-like objects.

        Args:
            attachments (list): List of file paths or File-like objects (e.g., uploaded files).
        """
        if not isinstance(attachments, list):
            raise ValueError("Attachments should be provided as a list.")
        self.attachments = attachments


class DefaultEmail(BaseEmail):
    pass


def is_valid_email(email: str) -> bool:
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


def send_email(email, subject, template, context={}, attachments=[]):
    try:
        sender = DefaultEmail()
        sender.set_subject(subject)
        sender.set_template(template)
        sender.set_attachments(attachments)
        sender.send(email, context)
    except Exception as e:
        logger.error(f"Failed to send email: {e}")