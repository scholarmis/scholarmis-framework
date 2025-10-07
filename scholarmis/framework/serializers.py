from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import models
from django.core.exceptions import ImproperlyConfigured


class NestedSerializer(serializers.ModelSerializer):
    class Meta:
        abstract = True
        serializers = {}  # Optional override

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attach_nested_fields()

    def _attach_nested_fields(self):
        model = getattr(getattr(self, "Meta", None), "model", None)
        if model is None:
            raise ImproperlyConfigured(f"{self.__class__.__name__} must define Meta.model")

        meta_fields = list(getattr(self.Meta, "fields", []))
        nested_map = getattr(self.Meta, "serializers", {})

        for field in model._meta.get_fields():
            if not isinstance(field, (models.ForeignKey, models.OneToOneField, models.ManyToManyField)):
                continue

            field_name = field.name
            serializer_class = nested_map.get(field_name)

            if serializer_class is None:
                serializer_class_name = f"{field_name.capitalize()}Serializer"
                serializer_class = globals().get(serializer_class_name)
                if serializer_class is None:
                    continue

            # Read-only nested
            if isinstance(field, models.ManyToManyField):
                self.fields[field_name] = serializer_class(many=True, read_only=True)
            else:
                self.fields[field_name] = serializer_class(read_only=True)

            if field_name not in meta_fields:
                meta_fields.append(field_name)

            model_class = getattr(getattr(serializer_class, "Meta", None), "model", None)
            if model_class is None:
                raise ImproperlyConfigured(f"Cannot derive queryset for {serializer_class.__name__}. Ensure it defines Meta.model.")

            # Write fields
            if isinstance(field, models.ManyToManyField):
                if field.remote_field.through._meta.auto_created:
                    self.fields[field_name + "_ids"] = serializers.PrimaryKeyRelatedField(
                        many=True, queryset=model_class.objects.all(),
                        source=field_name, write_only=True, required=False
                    )
                    meta_fields.append(field_name + "_ids")
                else:
                    self.fields[field_name + "_nested"] = serializer_class(
                        many=True, write_only=True, required=False
                    )
                    meta_fields.append(field_name + "_nested")
            else:
                self.fields[field_name + "_id"] = serializers.PrimaryKeyRelatedField(
                    queryset=model_class.objects.all(),
                    source=field_name, write_only=True, required=False
                )
                meta_fields.append(field_name + "_id")

        self.Meta.fields = meta_fields

    def _extract_nested_data(self, validated_data):
        nested_data = {}
        for key in list(validated_data.keys()):
            if key.endswith("_nested"):
                nested_data[key] = validated_data.pop(key)
        return nested_data

    def _handle_nested_m2m(self, instance, nested_data):
        for field_name, items in nested_data.items():
            actual_field = field_name.replace("_nested", "")
            rel_manager = getattr(instance, actual_field)
            serializer_class = self.fields[actual_field].child

            related_instances = []
            for item in items:
                obj_id = item.get('id')
                if obj_id:
                    # Update existing related object
                    obj = serializer_class.Meta.model.objects.get(id=obj_id)
                    for attr, value in item.items():
                        setattr(obj, attr, value)
                    obj.save()
                else:
                    obj = serializer_class.Meta.model.objects.create(**item)
                related_instances.append(obj)
            rel_manager.set(related_instances)

    def _handle_nested_fk_o2o(self, validated_data):
        for field in self.Meta.model._meta.get_fields():
            if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                continue
            field_name = field.name
            nested_field = field_name + "_nested"
            if nested_field in validated_data:
                data = validated_data.pop(nested_field)
                if data is None:
                    continue
                serializer_class = self.fields[field_name].child if hasattr(self.fields[field_name], 'child') else self.fields[field_name]
                obj_id = data.get('id')
                if obj_id:
                    obj = serializer_class.Meta.model.objects.get(id=obj_id)
                    for attr, value in data.items():
                        setattr(obj, attr, value)
                    obj.save()
                else:
                    obj = serializer_class.Meta.model.objects.create(**data)
                validated_data[field_name] = obj

    def create(self, validated_data):
        self._handle_nested_fk_o2o(validated_data)
        nested_data = self._extract_nested_data(validated_data)
        instance = super().create(validated_data)
        self._handle_nested_m2m(instance, nested_data)
        return instance

    def update(self, instance, validated_data):
        self._handle_nested_fk_o2o(validated_data)
        nested_data = self._extract_nested_data(validated_data)
        instance = super().update(instance, validated_data)
        self._handle_nested_m2m(instance, nested_data)
        return instance


class OptionModelSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        abstract = True


class BulkDeleteMixin:
    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request, *args, **kwargs):
        """
        Delete multiple objects by IDs.
        Example payload: { "ids": [1, 2, 3] }
        """
        ids = request.data.get("ids", [])
        if not isinstance(ids, list) or not ids:
            return Response({"detail": "Invalid or empty ids list."},
                            status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(id__in=ids)
        deleted_count = queryset.count()
        queryset.delete()

        return Response({"deleted": deleted_count}, status=status.HTTP_200_OK)
