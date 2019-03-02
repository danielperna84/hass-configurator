# pylint: disable=missing-docstring
from setuptools import setup

setup(name='hass-configurator',
      version='0.3.4',
      description='HASS-Configurator',
      url='http://github.com/danielperna84/hass-configurator',
      project_urls={
          'Documentation': 'https://github.com/danielperna84/hass-configurator',
          'Tracker': 'https://github.com/danielperna84/hass-configurator/issues'
      },
      author='Daniel Perna',
      author_email='danielperna84@gmail.com',
      license='MIT',
      install_requires=['pyotp', 'gitpython'],
      packages=['hass_configurator'],
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
