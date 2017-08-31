
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
      version='0.0.3',
      license = 'BSD',
      description=description(),
      long_description=long_desc(),
      author = 'fy',
      author_email = 'fy0748@gmail.com',
      install_requires = ['aiohttp', 'msgpack'],
      url="https://github.com/fy0/slim",
      packages=['.'],
      classifiers = [
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],

)

