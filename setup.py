try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def description():
    return """github: https://github.com/fy0/slim"""


def long_desc():
    try:
        return open("desc", 'r', encoding='utf-8').read()
    except:
        return description()


setup(name='slim',
    version='0.0.4',
    license='zlib',
    description=description(),
    long_description=long_desc(),
    author='fy',
    author_email='fy0748@gmail.com',
    install_requires=['aiohttp'],
    url="https://github.com/fy0/slim",
    packages=['slim', 'slim.base', 'slim.support', 'slim.support.peewee', 'slim.support.asyncpg'],
    classifiers=[
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Software Development :: Libraries :: Python Modules'

        'Framework :: AsyncIO',
        'Framework :: Pytest',

        'Intended Audience :: Developers',
        'License :: OSI Approved :: zlib/libpng License',
        'Operating System :: OS Independent',

        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
