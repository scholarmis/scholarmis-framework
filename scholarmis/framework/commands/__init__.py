import click # type: ignore
from scholarmis.framework.commands.project import createproject
from scholarmis.framework.commands.plugin import createplugin
from scholarmis.framework.commands.plugin import plugin
from scholarmis.framework.commands.system import system

@click.group()
def cli():
    """Scholarmis CLI"""
    pass

cli.add_command(createproject)
cli.add_command(createplugin)
cli.add_command(plugin)
cli.add_command(system)

if __name__ == "__main__":
    cli()