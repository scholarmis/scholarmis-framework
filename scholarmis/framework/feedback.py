
def get_task_feedback(message=None):
    if message:
        return message
    return "The task has started, and you will be notified once it is complete."


def get_import_feedback():
    message = "The file has been uploaded successfully and is now being processed."
    return message

def get_export_feedback():
    message = "The export process has started, and your records are being exported."
    return message
