"""
setup.py for slim
https://github.com/fy0/slim
"""

from setuptools import setup, find_packages


def description():
    return """github: https://github.com/fy0/slim"""


def long_desc():
    try:
        return open("desc", 'r', encoding='utf-8').read()
    except:
        return description()


setup(
    name='slim',
    version='0.2.14',

    description=description(),
    long_description=long_desc(),
    url="https://github.com/fy0/slim",

    author='fy',
    author_email='fy0748@gmail.com',
    license='zlib',

    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Software Development :: Libraries :: Python Modules',

        'Framework :: AsyncIO',

        'License :: OSI Approved :: zlib/libpng License',
        'Operating System :: OS Independent',

        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='slim web framework model aiohttp asyncpg peewee',
    packages=find_packages(exclude=['tests']) + ['slim_cli', 'slim_cli.template', 'slim_cli.template.view',
                                                 'slim_cli.template.model'],
    package_dir={
        'slim_cli.template': 'slim_cli/template',
    },
    include_package_data=True,
    platforms='any',

    install_requires=['aiohttp', 'aiohttp_cors', 'click'],
    python_requires='>=3.5',

    extras_require={
        'full': ['peewee', 'asyncpg', 'msgpack'],
        'peewee': ['peewee'],
        'asyncpg': ['asyncpg']
    },

    entry_points={
        'console_scripts': [
            'slim=slim_cli.main:cli',
        ],
    }
)
