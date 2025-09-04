import os
import re
import mimetypes
import random
import string
import uuid
import base64
from datetime import datetime
from random import randint
from django.contrib import admin # type: ignore
from django.contrib.admin.sites import NotRegistered # type: ignore
from django.core.validators import URLValidator # type: ignore
from django.db.models import Model # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from django.urls import reverse, NoReverseMatch # type: ignore
from urllib.parse import urljoin, urlparse # type: ignore
from django.http import HttpRequest, HttpResponse, Http404 # type: ignore
from django.conf import settings # type: ignore
from django.shortcuts import redirect, render # type: ignore
from django.templatetags.static import static # type: ignore



def safe_unregister(model):
    try:
        admin.site.unregister(model)
    except NotRegistered:
        pass


def get_task_feedback(message=None):
    if message:
        return message
    return "The task has started, and you will be notified once it is complete."


def get_domain_name():
    domain = getattr(settings, 'DJANGO_HOST')
    return f"{domain}"


def get_host_name(host_name=None, port=None):
    # Determine the scheme based on whether SSL redirection is enabled
    is_secure = getattr(settings, 'SECURE_SSL_REDIRECT', False)
    scheme = 'https' if is_secure else 'http'

    # Use the provided host name or fall back to the setting
    host_name = host_name or getattr(settings, 'DJANGO_HOST', 'localhost')
    port = port or getattr(settings, 'DJANGO_PORT', None)

    # Include the port if specified and not using HTTPS
    port_part = f":{port}" if port and not is_secure else ''

    # Construct the full host name
    return f"{scheme}://{host_name}{port_part}"

def redirect_back(request: HttpRequest):
    referer = request.META.get("HTTP_REFERER")
    return redirect(referer)

def get_socket_host(host_name=None, port=None):
     # Determine the scheme based on whether SSL redirection is enabled
    is_secure = getattr(settings, 'SECURE_SSL_REDIRECT', False)
    scheme = 'wss' if is_secure else 'ws'

    # Use the provided host name or fall back to the setting
    host_name = host_name or getattr(settings, 'DJANGO_HOST', 'localhost')
    port = port or getattr(settings, 'DJANGO_SOCKET_PORT', None)

    # Include the port if specified and not using HTTPS
    port_part = f":{port}" if port and not is_secure else ''

    # Construct the full host name
    return f"{scheme}://{host_name}{port_part}"


def get_absolute_uri(view_name:str, host_name:str=None):
    relative_url = reverse(view_name)
    host = get_host_name(host_name)
    absolute_url = build_absolute_uri(host, relative_url)
    return absolute_url


def build_absolute_uri(host:str, relative_url:str):
    uri = urljoin(f"{host.rstrip('/')}/", relative_url.lstrip('/'))
    return uri


def get_app_name(normalize=False):
    name = getattr(settings, "APP_NAME")
    if normalize:
        return str(name).capitalize()
    return name


def get_admin_app_title():
    app_name = get_app_name()
    return f"{app_name} Admin"


def get_default_site_logo():
    logo = getattr(settings, "SITE_LOGO")
    return static(logo)


def get_default_site_icon():
    logo = getattr(settings, "SITE_ICON")
    return static(logo)
   

def get_template_name(template_path, app_name=None):
    if app_name:
        return os.path.join(app_name, template_path)
    else:
        return template_path


def get_user_from_context(context):
    request = context['request']
    user = request.user
    try:
        user_is_anonymous = user.is_anonymous()
    except TypeError:
        user_is_anonymous = user.is_anonymous

    if user_is_anonymous:
        return None
    return user
        
    
def get_file_path(file_name, app_name=None):
    if app_name is None:
        return file_name
    else:
        return f"{app_name}/{file_name}"
    

def get_view_name(view_name, app_name=None):
    if app_name is None:
        return view_name
    else:
        return f"{app_name}:{view_name}" 
    

def menu_action(app_name, action):
    view_name = get_view_name(action, app_name)
    return reverse(view_name)


def download(path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        file_name = os.path.basename(file_path)
        with open(file_path, 'rb') as fh:
            content = fh.read()
            response = HttpResponse(content, content_type=mime_type)
            response['Content-Disposition'] = 'inline; filename=' + file_name
            return response
    raise Http404


def format_number(amount, decimal_places=0, thousand_separator=','):
    # Format the number with specified decimal places and thousand separators
    return f"{amount:,.{decimal_places}f}".replace(",", thousand_separator)

def random_number(length):
    return str(randint(0, 10**length-1)).zfill(length)


def random_string(length):
    letters = string.ascii_uppercase
    random_string = ''.join(random.choice(letters) for i in range(length))
    return random_string


def reference_number(length=16, date_format='%Y%m%d'):
    # Generate a UUID and convert it to a base64 string
    unique_id = uuid.uuid4()
    ref_number = base64.urlsafe_b64encode(unique_id.bytes).decode('utf-8').rstrip('=\n').replace('-', '').replace('_', '')

    # Add the date prefix to the reference number
    date_str = datetime.now().strftime(date_format)
    combined_ref = date_str + ref_number.upper()

    # Return the reference number up to the specified length
    return combined_ref[:length]


def normalize(phrase: str) -> str:
    lowercase_words = {
        "a", "an", "the", "and", "but", "or", "nor", "on", "in", 
        "is", "with", "at", "to", "from", "by", "for", "of"
    }
    
    roman_numeral_pattern = re.compile(
        r"^(?=[MDCLXVI])M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$", 
        re.IGNORECASE
    )
    
    words = phrase.split()
    normalized_words = []
    for i, word in enumerate(words):
        if (
            word.isdigit() or 
            roman_numeral_pattern.fullmatch(word) or 
            re.fullmatch(r"\([A-Z]+\)", word)
        ):
            normalized_words.append(word)
        else:
            if i == 0 or word.lower() not in lowercase_words:
                normalized_words.append(word.capitalize())
            else:
                normalized_words.append(word.lower())
    
    interim_phrase = " ".join(normalized_words)
    
    def title_case_no_parentheses(segment: str) -> str:
        words_in_seg = segment.split()
        normalized_seg_words = []
        for j, w in enumerate(words_in_seg):
            if w.isdigit() or roman_numeral_pattern.fullmatch(w):
                normalized_seg_words.append(w)
            else:
                if j == 0 or w.lower() not in lowercase_words:
                    normalized_seg_words.append(w.capitalize())
                else:
                    normalized_seg_words.append(w.lower())
        return " ".join(normalized_seg_words)
    
    def replace_func(match: re.Match) -> str:
        content = match.group(1)
        if content.isupper():
            return f"({content})"
        else:
            return f"({title_case_no_parentheses(content)})"
    
    result = re.sub(r"\((.*?)\)", replace_func, interim_phrase)
    return result


def year_choices(min_value = None):
    if not min_value:
        min_value = 1920
    return [(r, r) for r in range(min_value, datetime.today().year+1)]


def show_feedback(request, message, title=None, redirect_url=None, success=True, app_name=None):
    if not app_name:
        template = "scholarmis/feedback.html"
    else:
        template = get_template_name("feedback.html", app_name)
    context = {
        'message': str(message),
        'success': success,
        'title': title,
        'redirect_url': redirect_url
    }
    return render(request, template, context)


def show_success(request, message, redirect_url=None, app_name=None):
    title = "Operation successful!"
    return show_feedback(request=request, message=message, title=title, redirect_url=redirect_url, app_name=app_name)


def get_choice_index(selected_value, choices):
    for index, (value, label) in enumerate(choices, start=1):
        if value == selected_value:
            return index
    return None


def convert_to_bool(value):
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ['true', '1', 'yes']:
            return True
        elif value in ['false', '0', 'no']:
            return False
    elif isinstance(value, (int, bool)):
        return bool(value)
    return None


def get_valid_url(url):
    validate = URLValidator()
    
    # Parse the URL to determine if it's absolute or relative
    parsed_url = urlparse(url)

    # If the URL has a scheme and netloc, it's an absolute URL
    if parsed_url.scheme and parsed_url.netloc:
        try:
            validate(url)  # Validate the absolute URL
            return url  # Return the absolute URL as it is
        except ValidationError:
            return url  # If the absolute URL is invalid, return it as is
        
    # Handle root-relative URLs (with or without trailing slashes)
    if url.startswith('/'):
        return url  # Return the root-relative URL as is
    
    # Try to resolve the URL as a Django view name
    try:
        # If it's a valid view name, reverse it to get the URL
        return reverse(url)
    except NoReverseMatch:
        pass  # If no matching view name, continue to validate as relative URL
    
    # Finally, validate and return the relative URL
    try:
        validate(url)  # Check if it's a valid relative URL
        return url
    except ValidationError:
        return url  # If not valid, return as is or handle accordingly


def get_instance(model_class:Model, instance):
    """
    Retrieves an instance of the given model class. If the provided instance is not of the 
    model_class type, it assumes the instance is an ID and attempts to fetch the object by its primary key.
    """
    if instance:
        if not isinstance(instance, model_class):
            # If instance is not of model_class type, assume it's a primary key and fetch the object
            return model_class.objects.get(pk=instance)
        return instance  # Return the object if it's already an instance of model_class
    return None  # Return None if the instance is None


def calculate_check_digits(bban: str) -> str:
    """
    Calculate ISO 7064 mod-97-10 checksum (IBAN style).
    Accepts BBAN with letters or digits.
    A=10, ..., Z=35 before calculating.
    """
    # Step 1: Add placeholder check digits "00"
    temp = bban.upper() + "00"

    # Step 2: Convert letters to numbers (A=10...Z=35)
    converted = []
    for ch in temp:
        if ch.isalpha():
            converted.append(str(ord(ch) - 55))  # ord('A')=65 → 10
        else:
            converted.append(ch)
    numeric_str = "".join(converted)

    # Step 3: Mod 97
    remainder = int(numeric_str) % 97
    check_digits = 98 - remainder

    # Step 4: Return two-digit checksum
    return str(check_digits).zfill(2)


def alphanum_to_digits(value: str, width: int = 0) -> int:
        """
        Encode value so that:
        Letters: A=1, B=2, ... Z=26
        Digits: stay as they are
        Then remove leading zeros, truncate to fixed width, and pad if shorter.
        """
        value = value.upper()
        encoded_parts = []
        for char in value:
            if char.isalpha():
                encoded_parts.append(str(ord(char) - ord('A') + 1))
            elif char.isdigit():
                encoded_parts.append(char)

        encoded_str = "".join(encoded_parts).lstrip("0") or "0"

        if width > 0:
            if len(encoded_str) > width:
                encoded_str = encoded_str[:width]
            encoded_str = encoded_str.zfill(width)

        return encoded_str
