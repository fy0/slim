import click


@click.group()
def cli():
    pass


@cli.command()
@click.option('--name', prompt='Project Name', default=None)
def init(name):
    click.echo('Start a web application.')


if __name__ == '__main__':
    cli()
