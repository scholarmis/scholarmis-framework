from django.db import models

class BillingRate(models.TextChoices):
    FLAT = "Flat"
    PER_USER = "Per User"
    PER_MODULE = "Per Module"


class BillingType(models.TextChoices):
    PREPAID = "Prepaid"
    POSTPAID = "Postpaid"


class BillingCycle(models.TextChoices):
    ONETIME = "One Time"
    PER_MONTH = "Per Month"
    PER_QUARTER = "Per Quarter"
    PER_TRIMESTER = "Per Trimester"
    PER_SEMESTER = "Per Semester"
    PER_YEAR = "Per Year"
