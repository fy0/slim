import os
import click
import base64
import shutil
from os.path import join

src_dir = os.path.dirname(os.path.abspath(__file__))


def gen(project_dir, project_name):
    shutil.copytree(join(src_dir, 'template'), project_dir)

    config_file = join(project_dir, 'config.py')
    fp = open(config_file, encoding='utf-8')
    txt = fp.read()
    fp.close()
    txt = txt.replace("PROJECT_NAME = 'SlimApplication'", "PROJECT_NAME = '%s'" % project_name.title())
    txt = txt.replace(' = b"6aOO5ZC55LiN5pWj6ZW/5oGo77yM6Iqx5p+T5LiN6YCP5Lmh5oSB44CC"', ' = %r' % base64.b64encode(os.urandom(48)))
    fp = open(config_file, 'w+', encoding='utf-8')
    fp.write(txt)
    fp.close()
    return True


@click.group()
def cli():
    pass


@cli.command(help='generate a new project from template')
@click.option('--name', prompt='Project Name', default=None)
def init(name):
    click.echo('Start a web application.')

    project_dir = name
    if os.path.exists(project_dir):
        print('Already Exists!')
        return
    if gen(project_dir, name):
        print('OK!')


if __name__ == '__main__':
    cli()
