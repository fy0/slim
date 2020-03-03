import os
import random

import click
import base64
import shutil
from os.path import join

src_dir = os.path.dirname(os.path.abspath(__file__))


class ReplaceManager:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        fp = open(self.path, encoding='utf-8')
        txt = fp.read()
        fp.close()
        self.txt = txt
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        fp = open(self.path, 'w+', encoding='utf-8')
        fp.write(self.txt)
        fp.close()
        return True


def gen(project_dir, project_name):
    shutil.copytree(join(src_dir, 'template'), project_dir)
    port = '9%03d' % random.randint(0, 999)

    with ReplaceManager(join(project_dir, 'config.py')) as r:
        txt = r.txt.replace('PORT = 9999', 'PORT = ' + port)
        txt = txt.replace("PROJECT_NAME = 'SlimApplication'", "PROJECT_NAME = '%s'" % project_name.title())
        txt = txt.replace(' = b"6aOO5ZC55LiN5pWj6ZW/5oGo77yM6Iqx5p+T5LiN6YCP5Lmh5oSB44CC"', ' = %r' % base64.b64encode(os.urandom(48)))
        r.txt = txt

    with ReplaceManager(join(project_dir, 'tools', 'request.py')) as r:
        txt = r.txt.replace('localhost:9999', 'localhost:' + port)
        r.txt = txt

    with ReplaceManager(join(project_dir, 'requirements.txt')) as r:
        import slim
        r.txt = r.txt.replace('SLIM_VERSION', slim.__version__)

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
