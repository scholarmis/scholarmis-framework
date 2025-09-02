import click # type: ignore
from .exceptions import WizardExit, WizardRestart


def ask(prompt, default=None, type=str, validator=None):
    """Prompt user and handle 'exit' or 'restart' commands."""
    while True:
        value = click.prompt(prompt, default=default, type=type)
        cmd = value.strip().lower()
        if cmd == "exit":
            raise WizardExit()
        if cmd == "restart":
            raise WizardRestart()
        if validator:
            try:
                return validator(value)
            except click.BadParameter as e:
                click.secho(f"{e}", fg="red")
        else:
            return value


def choose(prompt: str, options: list[str], default: int | None = None) -> str:
    """
    Generic numbered-choice selector.

    - Displays options with numbers.
    - User enters a number.
    - Supports 'exit' and 'restart'.
    - If user presses Enter with a default, returns default.
    """
    while True:
        click.echo(f"\n{prompt}")
        for i, option in enumerate(options, start=1):
            click.echo(f"  {i}. {option}")

        # Prepare default for click.prompt
        default_display = default
        raw_choice = ask(f"Enter the number of your choice", default=str(default_display) if default else None)

        # Convert choice to integer
        try:
            choice_int = int(raw_choice)
        except ValueError:
            click.secho("Invalid selection. Enter a valid number.", fg="red")
            continue

        if 1 <= choice_int <= len(options):
            return options[choice_int - 1]
        else:
            click.secho(f"Number out of range. Enter 1-{len(options)}.", fg="red")
