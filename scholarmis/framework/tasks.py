from typing import Optional
import yaml
from pathlib import Path
from django.conf import settings # type: ignore
from celery.schedules import crontab # type: ignore
from django_celery_beat.models import CrontabSchedule, PeriodicTask # type: ignore


class TaskLoader:
    DEFAULT_DIR = "celery"
    DEFAULT_FILE = "tasks.yml"

    def __init__(self, app_name: str, tasks_dir: Optional[str] = None, tasks_file: Optional[str] = None):
        self.app_name = app_name

        self.tasks_dir = tasks_dir or self.DEFAULT_DIR
        self.tasks_file = tasks_file or self.DEFAULT_FILE

        self.base_dir = Path(getattr(settings, "BASE_DIR"))
        self.app_path = self.base_dir / app_name.replace(".", "/")
        self.tasks_file_path = self.app_path / self.tasks_dir / self.tasks_dir

    def validate_schedule_format(self, schedule: str):
        """Validate and convert a cron schedule string to a Celery crontab."""
        parts = schedule.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid schedule format: {schedule}")
        return crontab(
            minute=parts[0],
            hour=parts[1],
            day_of_month=parts[2],
            month_of_year=parts[3],
            day_of_week=parts[4],
        )

    def load_tasks(self):
        """Load and register tasks from the YAML file."""
        if not self.tasks_file_path.exists():
            raise FileNotFoundError(f"YAML Tasks file not found: {self.tasks_file_path}")

        with self.tasks_file_path.open("r", encoding="utf-8") as file:
            tasks = yaml.safe_load(file) or {}

        for name, details in tasks.items():
            try:
                if not isinstance(details, dict):
                    raise ValueError(f"Task '{name}' must be a dictionary, got {type(details)}")

                if "task" not in details or "schedule" not in details:
                    raise ValueError(f"Missing 'task' or 'schedule' in task: {name}")

                # Parse schedule
                schedule = self.validate_schedule_format(details["schedule"])

                # Get or create crontab schedule
                crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
                    minute=schedule.minute,
                    hour=schedule.hour,
                    day_of_month=schedule.day_of_month,
                    month_of_year=schedule.month_of_year,
                    day_of_week=schedule.day_of_week,
                )

                # Create or update the periodic task
                PeriodicTask.objects.update_or_create(
                    name=name,
                    defaults={
                        "task": details["task"],
                        "crontab": crontab_schedule,
                    },
                )
            except Exception as e:
                print(f"Error processing task '{name}': {e}")


def load_tasks(app_name: str, tasks_dir: Optional[str] = None, tasks_file: Optional[str] = None):
    """Convenience class method to load tasks for a given app."""
    loader = TaskLoader(app_name, tasks_dir, tasks_file)
    try:
        loader.load_tasks()
    except Exception as e:
        print(f"Error loading tasks from {loader.tasks_file_path}: {e}")
