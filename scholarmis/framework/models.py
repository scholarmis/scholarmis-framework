import os
import semver # type: ignore
from slugify import slugify
from django.db import connection, models # type: ignore
from django.core.exceptions import ValidationError # type: ignore
from django_countries.fields import CountryField # type: ignore
from model_utils.models import TimeStampedModel, UUIDModel # type: ignore
from .choices import GENDER_LIST, MARITAL_LIST, TITLE_LIST
from .managers import SequenceManager


class DirtyFields(models.Model):
    """
    A mixin to track changes (dirty fields) in a Django model and retrieve
    both old and new values for updated fields.
    """
    _original_state = None

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._store_original_state()

    def _store_original_state(self):
        """
        Stores the current state of the instance when it"s loaded or saved.
        """
        if self.pk:  # Only for saved instances
            self._original_state = self._get_current_state_from_db()

    def _get_current_state_from_db(self):
        """
        Retrieves the current state of the instance from the database.
        """
        return self.__class__.objects.filter(pk=self.pk).values(*[field.name for field in self._meta.fields]).first()

    # ------------------ Dirty Field Tracking ------------------

    def get_dirty_fields(self):
        """
        Returns a dictionary of fields that have changed, with their old and new values.
        """
        if not self._original_state:
            return {}

        dirty_fields = {}
        for field in self._meta.fields:
            if self._is_field_dirty(field):
                field_name = field.name
                dirty_fields[field_name] = {
                    "old": self._original_state.get(field_name),
                    "new": getattr(self, field_name),
                }
        return dirty_fields
    
    def get_old_value(self, field_name):
        """
        Returns the old value of a specific field if it"s dirty.
        """
        dirty_fields = self.get_dirty_fields()
        return dirty_fields.get(field_name, {}).get("old")

    def get_new_value(self, field_name):
        """
        Returns the new value of a specific field if it"s dirty.
        """
        dirty_fields = self.get_dirty_fields()
        return dirty_fields.get(field_name, {}).get("new")

    def _is_field_dirty(self, field):
        """
        Checks if a given field has been updated compared to the original state.
        """
        current_value = getattr(self, field.name)
        original_value = self._original_state.get(field.name) if self._original_state else None
        return current_value != original_value

    def is_dirty(self, field_name):
        """
        Checks if a specific field is dirty (updated).
        """
        return field_name in self.get_dirty_fields()

    def save(self, *args, **kwargs):
        """
        Saves the instance and updates the original state after saving.
        """
        super().save(*args, **kwargs)
        self._store_original_state()


class FileFields(models.Model):
    """
    A mixin that provides file deletion capabilities for image and file fields.
    """
    class Meta:
        abstract = True

    def _delete_file(self, file_field):
        """Delete the file associated with the given file field if it exists."""
        if file_field and os.path.isfile(file_field.path):
            try:
                os.remove(file_field.path)
            except:
                pass

    def _handle_file(self, old_instance):
        """Handle deletion of old files if they are updated or cleared."""
        for field in self._get_file_fields():
            old_file = getattr(old_instance, field)
            new_file = getattr(self, field)

            # Delete the old file if it"s being updated or cleared
            if old_file and (old_file != new_file or new_file is None):
                self._delete_file(old_file)

    def _get_file_fields(self):
        """Return a list of image and file fields in the model."""
        return [
            field.name for field in self._meta.fields 
            if isinstance(field, (models.ImageField, models.FileField))
        ]
    
    def save(self, *args, **kwargs):
        # If updating an existing profile, handle file deletions
        if self.pk:
            old_instance = self.__class__.objects.filter(pk=self.pk).first()
            if old_instance:
                self._handle_file(old_instance)

        # Proceed with the regular save process
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete associated files when the instance is deleted."""
        for field in self._get_file_fields():
            self._delete_file(getattr(self, field))

        # Call the parent class delete method
        super().delete(*args, **kwargs)


class SequenceField(models.Model):
    seq_number = models.BigIntegerField(blank=True, null=True, db_index=True, editable=False)

    objects = SequenceManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Only generate sequence if creating a new object
        if self._state.adding and self.seq_number is None:
            self.seq_number = self._generate_sequence_number()
        super().save(*args, **kwargs)

    def _generate_sequence_number(self):
        """
        Thread-safe sequence generation using PostgreSQL sequences.
        """
        sequence_name = f"{self._meta.app_label}_{self._meta.model_name.lower()}_seq_number"

        with connection.cursor() as cursor:
            # Create sequence if it doesn't exist
            cursor.execute(f"CREATE SEQUENCE IF NOT EXISTS {sequence_name} START 1;")
            # Get next value atomically
            cursor.execute(f"SELECT nextval('{sequence_name}')")
            next_seq = cursor.fetchone()[0]

        return next_seq


class BaseModel(UUIDModel, TimeStampedModel, DirtyFields, FileFields):
    class Meta:
        abstract = True


class OptionModel(BaseModel, SequenceField):
    SEPARATOR = "_"
    name = models.CharField(max_length=255, unique=True)
    value = models.CharField(max_length=255, blank=True, null=True)
    slug = models.SlugField(max_length=255, blank=True, null=True)
    code = models.CharField(max_length=255, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    is_visible = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["seq_number"]

    def __str__(self) -> str:
        if self.description:
            return self.description
        else:
            return self.value

    
    def __getattr__(self, name):
        option = self.get_option(name)
        return option
    
    def equals(self, option):
        if isinstance(option, OptionModel):
            return self.pk == option.pk
        elif isinstance(option, str):
            if self.name.lower() == option.lower():
                return True
            
            try:
                option_instance = self.get_option(option)
                if isinstance(option_instance, OptionModel):
                    return self.pk == option_instance.pk
                else:
                    # Handle the case where option_instance is not an OptionModel
                    raise ValueError(f"The provided option '{option}' is not a valid OptionModel instance.")
            except Exception as e:
                # Handle potential errors from get_option method
                raise ValueError(f"Error getting option instance: {e}")
        else:
            # If option is neither OptionModel nor string
            raise TypeError(f"Expected OptionModel or string, got {type(option).__name__} instead.")

    
    def save(self, *args, **kwargs):
        self.slug = slugify(self.name, separator=self.SEPARATOR)
        self.name = str(self.name).upper()
        if not self.value:
            # Convert NAME_CONSTANT to human-readable value
            self.value = self.name.replace("_", " ").title()
        super().save(*args, **kwargs)

    @classmethod
    def get_option(cls, name):
        # Attempt to find an object by name
        instance = cls.objects.filter(name=name).first()

        if instance:
            return instance

        # If not found, try to find by slug
        instance = cls.objects.filter(slug=name).first()

        if instance:
            return instance
        
        # If not found, try to find by code
        instance = cls.objects.filter(code=name).first()

        if instance:
            return instance

        # If still not found, generate slug and search again
        slug = slugify(name, separator=cls.SEPARATOR)
        instance = cls.objects.filter(slug=slug).first()

        if instance:
            return instance

        # If no instance is found, raise an AttributeError
        raise AttributeError(f"{cls.__name__} object has no option '{name}'")

    @classmethod
    def get_value(cls, name):
        option = cls.get_option(name)
        return option.value
    
    @classmethod
    def get_choices(cls):
        return cls.objects.all()
    
    @classmethod
    def get_active_choices(cls):
        return cls.objects.filter(is_visible=True)


class Versionable(BaseModel):
    version = models.CharField(max_length=20, help_text="Version format should be in the form 'X.Y.Z' (example: 1.0.0)")
    version_label = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True  # Mark this as an abstract class

    @classmethod
    def get_active(cls):
        return cls.objects.filter(is_active=True).first()

    @classmethod
    def get_latest(cls, exclude_pk=None, **kwargs):
        """
        Get the latest version of the record based on any filter criteria using semver-aware sorting.
        Optionally exclude a specific primary key from the results.
        """
        queryset = cls.objects.filter(**kwargs).exclude(version__isnull=True)
        
        if exclude_pk:
            queryset = queryset.exclude(pk=exclude_pk)

        all_versions = list(queryset)

        if not all_versions:
            return None

        try:
            # Sort using semver-aware comparison
            all_versions.sort(
                key=lambda obj: semver.VersionInfo.parse(obj.version),
                reverse=True
            )
            return all_versions[0]
        except ValueError as e:
            raise ValidationError(f"Invalid version format found in database: {e}")

    def clean(self):
        """
        Custom validation to ensure version follows the correct format.
        """
        if self.version:
            try:
                # Parse the version to check if it"s valid
                semver.VersionInfo.parse(self.version)
            except ValueError:
                raise ValidationError(f"Version {self.version} is not a valid semantic version. It should be in the form 'X.Y.Z' ")
    
    def activate(self):
        self.is_active = True
        self.save()

    def deactivate(self):
        self.is_active = False
        self.save()
    
    def get_previous(self, index=0):
        previous = self.__class__.objects.filter(created__lt=self.created).order_by("-created")
        try:
            if index < len(previous):
                return previous[index]
        except IndexError:
            pass
        return None
    
    def increment_version(self, bump_type="patch"):
        """
        Increment the version based on the bump_type.
        :param bump_type: str, one of ["major", "minor", "patch"]
        """
        kwargs = self.get_version_filter()
        try:
            latest_record = self.__class__.get_latest(exclude_pk=self.pk, **kwargs)
            if latest_record:
                current_version = semver.VersionInfo.parse(latest_record.version)
                if bump_type == "major":
                    self.version = current_version.bump_major()
                elif bump_type == "minor":
                    self.version = current_version.bump_minor()
                else:  # default to patch bump
                    self.version = current_version.bump_patch()
            else:
                self.version = "1.0.0"  # Start with the initial version if no previous version exists
        except Exception as e:
            raise ValidationError(f"Error incrementing version: {str(e)}")

    def get_version_filter(self):
        """
        Define the filter criteria for determining the latest version.
        Override this in subclasses to customize the filter criteria.
        """
        return {}

    def save(self, *args, **kwargs):
        # Allow manual version override, but still run validation
        if not self.version:
            self.increment_version(kwargs.pop("bump_type", "patch"))

        # Run the custom validation before saving
        self.full_clean()  # Calls the clean() method

        super().save(*args, **kwargs)


class Person(BaseModel):
    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    other_name = models.CharField(max_length=255, blank=True, null=True)
    national_id = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=255, choices=TITLE_LIST, blank=True, null=True)
    gender = models.CharField(max_length=255, choices=GENDER_LIST, blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    marital_status = models.CharField(max_length=255, choices=MARITAL_LIST, blank=True, null=True)
    contact_address = models.CharField(max_length=255, blank=True, null=True)
    physical_address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = CountryField(blank_label="(Select country)", blank=True, null=True)


    REQUIRED_PROFILE_FIELDS = [
        "first_name",
        "last_name",
        "national_id",
        "title",
        "gender",
        "phone",
        "email",
        "date_of_birth",
        "marital_status",
        "contact_address",
        "physical_address",
        "city",
        "country",
    ]

    class Meta:
        abstract = True

