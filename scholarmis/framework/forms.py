from django import forms # type: ignore
from django.db.models import QuerySet # type: ignore
from django.core.validators import FileExtensionValidator # type: ignore

# Allowed document types
DOC_EXTENSIONS = ["pdf", "doc", "docx"]

# MIME types
DOC_MIMETYPES = ",".join([
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
])


class DocumentField(forms.FileField):

    def __init__(self, allowed_extensions=None, accepted_mimetypes=None, label=None, required=False, **kwargs):
        self.allowed_extensions = allowed_extensions or DOC_EXTENSIONS
        accepted_mimetypes = accepted_mimetypes or DOC_MIMETYPES

        kwargs["widget"] = forms.FileInput(attrs={"accept": DOC_MIMETYPES})
        kwargs["validators"] = [FileExtensionValidator(allowed_extensions=self.allowed_extensions)]

        super().__init__(label=label, required=required, **kwargs)


class MultipleDocumentsField(forms.FileField):

    def __init__(self, allowed_extensions=None, accepted_mimetypes=None, label=None, required=False, **kwargs):
        self.allowed_extensions = allowed_extensions or DOC_EXTENSIONS
        accepted_mimetypes = accepted_mimetypes or DOC_MIMETYPES

        kwargs["widget"] = forms.TextInput(attrs={"type": "file", "multiple": "True"})
        kwargs["validators"] = [FileExtensionValidator(allowed_extensions=self.allowed_extensions)]

        super().__init__(label=label, required=required, **kwargs)


class FormFieldsMixin:
   
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filtered_fields()  # Apply field-specific filtering after initialization

    def set_field_queryset(self, field_name: str, queryset: QuerySet):
        """
        Sets the queryset of a specified form field to a filtered queryset.

        Args:
            field_name (str): The name of the form field whose queryset needs to be set.
            queryset (QuerySet): The filtered queryset to be assigned to the form field.
        """
        if field_name in self.fields:
            self.fields[field_name].queryset = queryset

    def set_field_value(self, field_name: str, value):
        """
        Sets the value of a specified form field.

        Args:
            field_name (str): The name of the form field whose queryset needs to be set.
            value (any): The value to be assigned to the form field.
        """
        if field_name in self.fields:
            self.fields[field_name].initial = value

    def filtered_fields(self):
        """
        A placeholder method meant to be overridden in subclasses to specify field-specific
        filtering logic.

        This method should contain logic to filter specific fields using `global_filter` 
        and `set_field_queryset`. For example, fields like `ModelChoiceField` can have 
        their querysets dynamically filtered based on user access.
        
        Example Usage in Subclass:
            def filtered_fields(self):
                # Filter the queryset for a specific field
                self.set_field_queryset("program_type", self.global_filter(ProgramType.objects.all()))

        """
        pass
