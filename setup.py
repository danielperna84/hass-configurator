# pylint: disable=missing-docstring
from os import path
from setuptools import setup

NAME = "hass-configurator"
PACKAGE_NAME = "hass_configurator"
VERSION = "0.3.6"

# read the contents of your README file
THIS_DIRECTORY = path.abspath(path.dirname(__file__))
with open(path.join(THIS_DIRECTORY, 'README.md'), encoding='utf-8') as f:
    LONG_DESCRIPTION = f.read()

setup(name=NAME,
      version=VERSION,
      description='HASS-Configurator',
      long_description=LONG_DESCRIPTION,
      long_description_content_type='text/markdown',
      url='http://github.com/danielperna84/hass-configurator',
      project_urls={
          'Documentation': 'https://github.com/danielperna84/hass-configurator',
          'Tracker': 'https://github.com/danielperna84/hass-configurator/issues'
      },
      download_url='https://github.com/danielperna84/hass-configurator/tarball/'+VERSION,
      author='Daniel Perna',
      author_email='danielperna84@gmail.com',
      license='MIT',
      install_requires=['pyotp', 'gitpython'],
      packages=[PACKAGE_NAME],
      include_package_data=True,
      entry_points={
          'console_scripts': [
              'hass-configurator = hass_configurator.configurator:main'
          ]
      },
      keywords='home-assistant',
      platforms='any',
      python_requires='>=3',
      classifiers=[
          'Programming Language :: Python :: 3',
          'Operating System :: OS Independent',
          'Topic :: Text Editors'],
      zip_safe=False)
