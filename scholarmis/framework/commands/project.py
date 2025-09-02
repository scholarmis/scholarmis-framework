import click # type: ignore
from pathlib import Path
from scholarmis.framework.plugins.generator import ProjectGenerator


@click.command("createproject")
@click.argument("path", required=False, type=click.Path(file_okay=False, writable=True, path_type=Path))
def createproject(path):
    try:
        stubs_dir = Path(__file__).parent / "stubs" / "project"
        
        generator = ProjectGenerator(path, stubs_dir)
        generator.generate()

        click.echo(f"Scholarmis project created at {generator.output_dir.resolve()}")

        click.echo(f" pip install -r requirements.txt")
        click.echo(f" scholarmis system migrate")
        click.echo(f" scholarmis system runserver")

    except Exception as e:
        raise click.ClickException(f"An unexpected error occurred during generation: {e}")

