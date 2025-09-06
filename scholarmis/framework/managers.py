from django.db import models, connection # type: ignore


class SequenceManager(models.Manager):

    def bulk_create(self, objs, **kwargs):
        if not objs:
            return super().bulk_create(objs, **kwargs)

        model = objs[0].__class__
        sequence_name = f"{model._meta.app_label}_{model._meta.model_name.lower()}_seq_number"

        with connection.cursor() as cursor:
            # Ensure the sequence exists
            cursor.execute(f"CREATE SEQUENCE IF NOT EXISTS {sequence_name} START 1;")

            # Assign sequence numbers to objects
            for obj in objs:
                if getattr(obj, 'seq_number', None) is None:
                    cursor.execute(f"SELECT nextval('{sequence_name}')")
                    obj.seq_number = cursor.fetchone()[0]

        return super().bulk_create(objs, **kwargs)
    