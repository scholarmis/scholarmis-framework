import os
from uuid import uuid4
from PIL import Image
from django.utils.deconstruct import deconstructible # type: ignore
from .storage import MediaStorage


@deconstructible
class FileUploadPath:

    def __init__(self, sub_path):
        self.path = sub_path

    def __call__(self, instance, filename):
        ext = filename.split('.')[-1]
        # set filename as random string
        filename = '{}.{}'.format(uuid4(), ext)
        # return the whole path to the file
        return os.path.join(self.path, filename)
        

def save_uploaded_file(request, uploaded_file, upload_path="uploads", rename=True):
    file_upload = MediaStorage()
    saved_file_path = file_upload.upload(uploaded_file, upload_path, rename)
    return saved_file_path


def remove_uploaded_file(file_path):
    if os.path.exists(file_path):
        try:
            # Delete the file from the file system
            os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")

def storage_path(path):
    media = MediaStorage()
    return media.storage_path(path)


def resize_image(image_path, size, format='PNG', quality=90):
    with Image.open(image_path) as img:
        img = img.convert("RGB")  # Ensure image is in the correct format
        img.thumbnail(size)  # Resize the image to fit within the specified size
        img.save(image_path, format=format, quality=90)  # Save resized image

