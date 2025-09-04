import os
from uuid import uuid4
from PIL import Image
from django.core.files.storage import default_storage # type: ignore


def save_uploaded_file(uploaded_file, upload_path="uploads", rename=True):
    # Create upload directory inside MEDIA_ROOT
    base_path = upload_path.strip("/")

    filename = uploaded_file.name
    if rename:
        ext = filename.split('.')[-1]
        filename = '{}.{}'.format(uuid4(), ext)

    full_path = os.path.join(base_path, filename)

    # Save the file
    saved_path = default_storage.save(full_path, uploaded_file)

    # Return the relative path (relative to MEDIA_ROOT)
    return saved_path


def remove_uploaded_file(file_path):
    if os.path.exists(file_path):
        try:
            # Delete the file from the file system
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")


def resize_image(image_path, size, format='PNG', quality=90):
    with Image.open(image_path) as img:
        img = img.convert("RGB")  # Ensure image is in the correct format
        img.thumbnail(size)  # Resize the image to fit within the specified size
        img.save(image_path, format=format, quality=90)  # Save resized image


def get_import_feedback():
    message = "The file has been uploaded successfully and is now being processed."
    return message


def get_export_feedback():
    message = "The export process has started, and your records are being exported."
    return message

