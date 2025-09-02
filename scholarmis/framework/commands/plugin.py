import tempfile
import zipfile
import click # type: ignore
from pathlib import Path
from scholarmis.framework.plugins import plugin_installer
from scholarmis.framework.plugins.generator import PluginGenerator, PluginConfig
from .exceptions import WizardExit, WizardRestart
from .prompts import ask, choose
from .validate import validate_email, validate_name, validate_version


@click.group()
def plugin():
    """Manages scholarly plugins."""


@click.command("createplugin")
@click.argument("name", required=False)
@click.argument("path", required=False)
@click.option("--official", is_flag=True, help="Mark this as an official plugin.")
@click.option("--editable/--no-editable", default=None, help="Editable mode (default: ask).")
def createplugin(name: str, path: str, official: bool, editable: bool):
    while True:  # loop for restart
        try:
            click.secho("Scholarmis Plugin Generator", fg="cyan", bold=True)
            click.echo("Type 'exit' at any prompt to cancel or 'restart' to start over.\n")

            if not name:
                name = ask("1 Enter plugin name", validator=validate_name)
            if not path:
                path = ask("2 Enter output path", default="packages")
            path = Path(path)

            version = ask("3 Enter version", default="0.1.0", validator=validate_version)
            author = ask("4 Enter author name", default="Scholarmis Team")
            author_email = ask("5 Enter author email", default="dev@scholarmis.com", validator=validate_email)
            licenses = ["MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause", "Proprietary", "Other"]
            license_name = choose("6 Choose license", licenses, 1)

            if editable is None:
                editable = click.confirm("7 Do you want the plugin in editable mode?", default=True)
            if not official:
                official = click.confirm("8 Is this an official plugin?", default=False)

            # Collect metadata
            config = PluginConfig(
                name=name,
                version=version,
                author=author,
                author_email=author_email,
                license=license_name,
                official=official,
                editable=editable,
                output_dir=path,
            )

            # Summary
            click.secho("\nPlugin Summary", fg="yellow", bold=True)
            for field, value in config.__dict__.items():
                click.echo(f"   {field.capitalize()}: {value}")

            if not click.confirm("\nConfirm and generate plugin?", default=True):
                click.secho("Plugin generation cancelled.", fg="red")
                return

            # Generate plugin
            stubs_dir = Path(__file__).parent / "stubs" / "plugin"
            generator = PluginGenerator(config, stubs_dir)

            click.echo(f"Generating plugin '{config.name}' (v{config.version})...")

            generator.generate()

            click.secho("Plugin created successfully!", fg="green", bold=True)
            return

        except WizardRestart:
            click.secho("\nRestarting wizard...\n", fg="yellow")
            name = path = None  # reset inputs
            continue
        except WizardExit:
            click.secho("Wizard cancelled. Goodbye!", fg="red")
            return
        except Exception as e:
            raise click.ClickException(f"An unexpected error occurred: {e}")


@plugin.command("install")
@click.argument("source", required=True)
@click.argument("name", required=False)
def install(source, name=None):
    """
    Installs a plugin from a PyPI, Git, or a URL.
    """
    try:
        plugin_installer.install(source, name)
    except Exception as e:
        raise click.ClickException(f"An unexpected error occurred during installation: {e}")

    
@plugin.command("remove")
@click.argument("name", required=True)
def remove(name):
    """
    Removes an installed plugin and its entry from the lock file.
    """
    if plugin_installer.uninstall(name):
        click.echo(f"Removed {name}")


@plugin.command("upgrade")
@click.argument("name", required=False)
@click.option("--all", "all_", is_flag=True, help="Upgrade all pinned plugins.")
def upgrade(name, all_):
    """
    Upgrades one or all pinned plugins.
    """
    if all_:
        plugin_installer.upgrade_all()
    elif name:
        plugin_installer.upgrade(name)
    else:
        raise click.ClickException("Provide a plugin name or use --all to upgrade all.")


@plugin.command("publish")
@click.argument("path", type=click.Path(exists=True))
def publish(path):
    p = Path(path)
    tmp = tempfile.mkdtemp()
    zip_path = Path(tmp) / f"{p.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in p.rglob("*"):
            z.write(f, f.relative_to(p))
    # placeholder: upload to marketplace
    click.echo(f"Packaged plugin to {zip_path}. Upload step is a placeholder.")


@plugin.command("check")
def check():
    """
    Validate that environment matches plugins.lock.
    """

    errors, warnings = plugin_installer.check_plugins()
   
    if not errors and not warnings:
        click.echo("Scholarmis Doctor: environment matches plugins.lock")
    else:
        if errors:
            click.echo("Errors:")
            for e in errors:
                click.echo("  " + e)
        if warnings:
            click.echo("Warnings:")
            for w in warnings:
                click.echo("  " + w)
        raise click.ClickException("Scholarmis Doctor found issues")

