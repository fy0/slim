"""
setup.py for slim
https://github.com/fy0/slim
"""

from setuptools import setup, find_packages


def description():
    return """A Web framework provides instant restful api for your database."""


def long_desc():
    try:
        txt = open("readme.md", 'r', encoding='utf-8').read()
        return txt.replace('artworks/logo-full.png', 'https://raw.githubusercontent.com/fy0/slim/master/artworks/logo-full.png')
    except:
        return description()


setup(
    name='slim',
    version='0.7.0a1',

    description=description(),
    long_description=long_desc(),
    long_description_content_type='text/markdown',
    url="https://github.com/fy0/slim",

    author='fy',
    author_email='fy0748@gmail.com',
    license='zlib',

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Software Development :: Libraries :: Python Modules',

        'Framework :: AsyncIO',

        'License :: OSI Approved :: zlib/libpng License',
        'Operating System :: OS Independent',

        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],

    keywords='slim web framework model asgi asyncpg peewee',
    packages=find_packages(exclude=['tests']) + ['slim_cli',
                                                 'slim_cli.template',
                                                 'slim_cli.template.permissions',
                                                 'slim_cli.template.permissions.roles',
                                                 'slim_cli.template.permissions.tables',
                                                 'slim_cli.template.api',
                                                 'slim_cli.template.api.validate',
                                                 'slim_cli.template.tools',
                                                 'slim_cli.template.model'],
    package_dir={
        'slim_cli.template': 'slim_cli/template',
    },
    include_package_data=True,
    platforms='any',

    install_requires=[
        'schematics>=2.1.0,<2.2.0',
        'typing_extensions>=3.6.5',
        'dataclasses',
        'multidict>=4.5,<5.0',
        'yarl>=1.0,<1.5',
        'uvicorn>0.11.0,<0.12.0',
        'click>=7.0,<8.0',
        'aiofiles>=0.4.0,<0.6',
        'python-multipart==0.0.5',
        'msgpack>=0.5.6,<2.0'],

    python_requires='>=3.6.9',

    extras_require={
        'full': ['peewee', 'asyncpg', 'msgpack', 'psycopg2-binary'],
        'peewee': ['peewee', 'psycopg2-binary'],
        'asyncpg': ['asyncpg'],
        'dev': ['pytest', 'pytest-cov', 'pytest-asyncio', 'peewee', 'asyncpg', 'msgpack', 'psycopg2-binary']
    },

    entry_points={
        'console_scripts': [
            'slim=slim_cli.main:cli',
        ],
    }
)
